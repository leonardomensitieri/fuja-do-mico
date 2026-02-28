"""
SCRIPT 12 — Triagem Automática do Pool conteudo_raw
=====================================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? SIM → Worker with API

O que faz:
  1. Busca itens com processado=false em conteudo_raw (batch de 20)
  2. Envia batch para Claude Haiku com prompt de triagem (mesmo critério do 05_triage.py)
  3. Para cada resultado: atualiza status_triagem, linha_editorial_sugerida, clone_sugerido
  4. Marca processado=true independente do resultado
  5. Repete até não restar itens processado=false
  6. Encerra silenciosamente se pool estiver vazio

Credenciais necessárias (GitHub Secrets):
  - SUPABASE_URL        : URL do projeto Supabase
  - SUPABASE_SERVICE_KEY: chave de serviço para leitura/escrita em conteudo_raw
  - ANTHROPIC_API_KEY   : chave da API da Anthropic (Haiku)
"""

import os
import json
from pathlib import Path

import anthropic

TAMANHO_BATCH = 20

# Mapeamento de relevancia (prompt) → status_triagem (banco)
MAPA_STATUS = {
    'ALTO': 'APROVADO',
    'MEDIO': 'APROVADO',
    'BAIXO': 'DESCARTADO',
    'PENDENTE': 'PENDENTE',
}


def carregar_prompt_base() -> str:
    """Carrega o prompt de triagem de prompts/01-triage.md."""
    return Path('prompts/01-triage.md').read_text(encoding='utf-8')


def buscar_batch(supabase) -> list:
    """Busca até TAMANHO_BATCH itens não processados, mais recentes primeiro."""
    res = (
        supabase.table('conteudo_raw')
        .select('*')
        .eq('processado', False)
        .order('data_captura', desc=True)
        .limit(TAMANHO_BATCH)
        .execute()
    )
    return res.data or []


def atualizar_item(supabase, item_id: str, resultado: dict):
    """Atualiza um item em conteudo_raw com o resultado da triagem."""
    supabase.table('conteudo_raw').update({
        'processado': True,
        'status_triagem': resultado.get('status_triagem', 'DESCARTADO'),
        'linha_editorial_sugerida': resultado.get('linha_editorial_sugerida'),
        'clone_sugerido': resultado.get('clone_sugerido'),
    }).eq('id', item_id).execute()


def _construir_prompt_batch(prompt_base: str, batch: list) -> str:
    """
    Constrói o prompt de triagem em batch para conteudo_raw.
    Solicita status_triagem, linha_editorial_sugerida e clone_sugerido por item.
    Reutiliza a lógica do 05_triage.py adaptada para o pool.
    """
    itens_formatados = []
    for i, item in enumerate(batch):
        conteudo = item.get('conteudo_texto', '') or ''
        titulo = item.get('url_original', '') or item.get('conta_origem', '') or f'item-{i}'
        itens_formatados.append(
            f'[{i}] ORIGEM: {titulo[:100]}\nCONTEÚDO: {conteudo[:1500]}'
        )

    lista_itens = '\n\n---\n\n'.join(itens_formatados)

    instrucao_batch = (
        f'Você receberá {len(batch)} itens para triagem do pool de conteúdo. '
        'Para cada item, aplique os critérios acima.\n\n'
        'Responda EXCLUSIVAMENTE com um JSON array válido, '
        f'com exatamente {len(batch)} objetos na mesma ordem dos itens:\n'
        '[\n'
        '  {"indice": 0, "relevancia": "ALTO|MEDIO|BAIXO|PENDENTE", '
        '"status_triagem": "APROVADO|DESCARTADO|PENDENTE", '
        '"linha_editorial_sugerida": "analise_financeira|noticia|mentalidade|macro|erros|narrativa|null", '
        '"clone_sugerido": "graham|buffett|barsi|damodaran|lynch|null", '
        '"justificativa": "..."},\n'
        '  ...\n'
        ']\n\n'
        'Regras de mapeamento:\n'
        '  ALTO → status_triagem: APROVADO\n'
        '  MEDIO → status_triagem: APROVADO\n'
        '  BAIXO → status_triagem: DESCARTADO\n'
        '  PENDENTE → status_triagem: PENDENTE (ambíguo ou requer revisão humana)\n\n'
        '## Itens para Triagem\n\n'
        f'{lista_itens}'
    )

    return prompt_base.replace('{{CONTEUDO}}', instrucao_batch)


def triar_batch(cliente: anthropic.Anthropic, prompt_base: str, batch: list) -> list:
    """
    Envia um batch de até TAMANHO_BATCH itens ao Haiku e retorna resultados de triagem.
    Fallback: erro no batch → todos recebem DESCARTADO e processado=true.
    """
    # Itens com conteúdo muito curto são descartados sem chamar a API
    validos = []
    resultados = []

    for i, item in enumerate(batch):
        conteudo = item.get('conteudo_texto', '') or ''
        if len(conteudo) < 50:
            resultados.append({
                'id': item['id'],
                'status_triagem': 'DESCARTADO',
                'linha_editorial_sugerida': None,
                'clone_sugerido': None,
            })
        else:
            validos.append((i, item))

    if not validos:
        return resultados

    itens_validos = [item for _, item in validos]
    prompt = _construir_prompt_batch(prompt_base, itens_validos)

    try:
        resposta = cliente.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=4096,
            messages=[{'role': 'user', 'content': prompt}]
        )

        texto = resposta.content[0].text.strip()
        inicio = texto.find('[')
        fim = texto.rfind(']') + 1
        if inicio < 0 or fim <= inicio:
            raise ValueError('Resposta não contém JSON array válido')

        triagens = json.loads(texto[inicio:fim])

        for j, (_, item) in enumerate(validos):
            triagem = triagens[j] if j < len(triagens) else {}
            relevancia = triagem.get('relevancia', 'BAIXO')
            status = triagem.get('status_triagem') or MAPA_STATUS.get(relevancia, 'DESCARTADO')
            resultados.append({
                'id': item['id'],
                'status_triagem': status,
                'linha_editorial_sugerida': triagem.get('linha_editorial_sugerida') or None,
                'clone_sugerido': triagem.get('clone_sugerido') or None,
            })

    except Exception as e:
        print(f'  ⚠️  Erro na triagem do batch: {e} — marcando todos como DESCARTADO')
        for _, item in validos:
            resultados.append({
                'id': item['id'],
                'status_triagem': 'DESCARTADO',
                'linha_editorial_sugerida': None,
                'clone_sugerido': None,
            })

    return resultados


def main():
    print('🔍 Iniciando triagem automática do pool conteudo_raw...')

    # Verifica credenciais obrigatórias
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')
    api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not supabase_url or not supabase_key:
        print('⚠️  SUPABASE_URL ou SUPABASE_SERVICE_KEY não configurados — encerrando.')
        return

    if not api_key:
        print('⚠️  ANTHROPIC_API_KEY não configurado — encerrando.')
        return

    from db_provider import get_client
    supabase = get_client()
    if not supabase:
        print('⚠️  Falha ao conectar ao Supabase — encerrando.')
        return

    cliente = anthropic.Anthropic(api_key=api_key)
    prompt_base = carregar_prompt_base()

    total_aprovados = 0
    total_descartados = 0
    total_pendentes = 0
    total_batches = 0

    while True:
        batch = buscar_batch(supabase)

        if not batch:
            if total_batches == 0:
                print('  Pool vazio ou sem itens para processar — encerrando.')
            break

        total_batches += 1
        print(f'  [Batch {total_batches}] Triando {len(batch)} itens...')

        resultados = triar_batch(cliente, prompt_base, batch)

        for resultado in resultados:
            atualizar_item(supabase, resultado['id'], resultado)
            status = resultado['status_triagem']
            if status == 'APROVADO':
                total_aprovados += 1
            elif status == 'PENDENTE':
                total_pendentes += 1
            else:
                total_descartados += 1

        print(f'    → APROVADO: {sum(1 for r in resultados if r["status_triagem"] == "APROVADO")}, '
              f'DESCARTADO: {sum(1 for r in resultados if r["status_triagem"] == "DESCARTADO")}, '
              f'PENDENTE: {sum(1 for r in resultados if r["status_triagem"] == "PENDENTE")}')

    if total_batches > 0:
        print(f'\n  📊 Total: APROVADO={total_aprovados}, '
              f'DESCARTADO={total_descartados}, PENDENTE={total_pendentes}')
        print('✅ Triagem do pool concluída.')


if __name__ == '__main__':
    main()
