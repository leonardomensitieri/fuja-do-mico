"""
SCRIPT 05 — Triagem de Conteúdo (IA)
======================================
Clone com Heurísticas (Finance/Invest — triagem editorial)
Heurísticas: critérios ALTO/MÉDIO/BAIXO definidos em prompts/01-triage.md

O que faz:
  - Lê todos os conteúdos coletados (Gmail + RSS + YouTube)
  - Envia itens em batches de 20 para o Claude Haiku (Story 3.1)
  - Mantém apenas os classificados como ALTO ou MEDIO
  - Salva em data/conteudo_triado.json

Decision tree:
  1. Carregar todos os conteúdos coletados dos arquivos JSON
  2. Agrupar em batches de 20 itens
  3. Para cada batch: uma única chamada ao Haiku com lista de itens
  4. Parsear array de resultados e enriquecer itens originais
  5. Filtrar ALTO e MEDIO; descartar BAIXO
  6. Salvar resultado

Credenciais necessárias (GitHub Secrets):
  - ANTHROPIC_API_KEY : chave da API da Anthropic
"""

import os
import json
import anthropic
from pathlib import Path

# Tamanho do batch para chamadas ao Haiku (Story 3.1 — escala para conteudo_raw)
TAMANHO_BATCH = 20


def carregar_prompt_triagem() -> str:
    """Carrega o prompt de triagem do arquivo .md"""
    return Path('prompts/01-triage.md').read_text(encoding='utf-8')


def carregar_todo_conteudo() -> list[dict]:
    """Junta todos os conteúdos coletados num único array."""
    todos = []

    for arquivo in ['data/newsletters_raw.json', 'data/rss_raw.json', 'data/youtube_raw.json', 'data/social_raw.json']:  # social_raw.json — Story 2.1
        path = Path(arquivo)
        if path.exists():
            itens = json.loads(path.read_text())
            todos.extend(itens)
            print(f"  Carregado: {arquivo} ({len(itens)} itens)")

    return todos


def _construir_prompt_batch(prompt_base: str, batch: list[dict]) -> str:
    """
    Constrói o prompt para triagem em batch.
    Substitui {{CONTEUDO}} por lista numerada de itens.
    Solicita array JSON com resultado por índice.
    """
    itens_formatados = []
    for i, item in enumerate(batch):
        conteudo = item.get('conteudo', '') or item.get('resumo', '')
        titulo = item.get('titulo', item.get('assunto', 'sem título'))
        itens_formatados.append(
            f'[{i}] TÍTULO: {titulo[:100]}\nCONTEÚDO: {conteudo[:1500]}'
        )

    lista_itens = '\n\n---\n\n'.join(itens_formatados)

    # Remove o placeholder {{CONTEUDO}} original e injeta instrução de batch
    instrucao_batch = (
        f'Você receberá {len(batch)} itens para triagem. '
        'Para cada item, aplique os critérios acima.\n\n'
        'Responda EXCLUSIVAMENTE com um JSON array válido, '
        f'com exatamente {len(batch)} objetos na mesma ordem dos itens:\n'
        '[\n'
        '  {"indice": 0, "relevancia": "ALTO|MEDIO|BAIXO", "justificativa": "...", '
        '"temas_identificados": [], "angulo_potencial_para_newsletter": "", "resumo_em_3_linhas": ""},\n'
        '  ...\n'
        ']\n\n'
        '## Itens para Triagem\n\n'
        f'{lista_itens}'
    )

    return prompt_base.replace('{{CONTEUDO}}', instrucao_batch)


def triar_em_batch(cliente: anthropic.Anthropic, prompt_base: str, batch: list[dict]) -> list[dict]:
    """
    Processa até TAMANHO_BATCH itens em uma única chamada ao Haiku.
    Retorna lista de itens enriquecidos com resultado da triagem.
    Interface compatível com o retorno anterior de triar_item().
    """
    # Filtra itens com conteúdo muito curto antes de enviar ao modelo
    resultados = []
    batch_valido = []
    indices_curtos = {}

    for i, item in enumerate(batch):
        conteudo = item.get('conteudo', '') or item.get('resumo', '')
        if len(conteudo) < 50:
            indices_curtos[i] = item
        else:
            batch_valido.append((i, item))

    # Itens curtos recebem BAIXO direto — sem chamada à API
    for i, item in indices_curtos.items():
        resultados.append((i, {**item, 'triagem': {'relevancia': 'BAIXO', 'justificativa': 'Conteúdo muito curto'}}))

    if not batch_valido:
        return [r for _, r in sorted(resultados, key=lambda x: x[0])]

    # Monta batch apenas com itens válidos
    itens_validos = [item for _, item in batch_valido]
    prompt_completo = _construir_prompt_batch(prompt_base, itens_validos)

    try:
        resposta = cliente.messages.create(
            model="claude-haiku-4-5-20251001",  # Haiku para triagem (mais rápido/barato)
            max_tokens=4096,                     # Aumentado para suportar N respostas
            messages=[{"role": "user", "content": prompt_completo}]
        )

        texto = resposta.content[0].text.strip()

        # Extrai o JSON array da resposta
        inicio = texto.find('[')
        fim = texto.rfind(']') + 1
        if inicio >= 0 and fim > inicio:
            triagens = json.loads(texto[inicio:fim])
        else:
            raise ValueError('Resposta não contém JSON array válido')

        # Mapeia resultado de volta para os itens originais do batch
        for j, (i_original, item) in enumerate(batch_valido):
            if j < len(triagens):
                triagem = triagens[j]
                # Garante que o campo relevancia existe
                if 'relevancia' not in triagem:
                    triagem['relevancia'] = 'BAIXO'
            else:
                triagem = {'relevancia': 'BAIXO', 'justificativa': 'Item sem resposta no batch'}
            resultados.append((i_original, {**item, 'triagem': triagem}))

    except Exception as e:
        print(f"    ⚠️  Erro na triagem do batch: {e}")
        # Fallback: marca todos os itens do batch como BAIXO
        for i_original, item in batch_valido:
            resultados.append((i_original, {**item, 'triagem': {
                'relevancia': 'BAIXO',
                'justificativa': f'Erro no batch: {str(e)}'
            }}))

    # Retorna na ordem original do batch
    return [r for _, r in sorted(resultados, key=lambda x: x[0])]


def salvar_resultado(dados: list, arquivo: str, edicao_id: str = None):
    """
    Persiste resultado localmente e no banco (se configurado).
    Retrocompatível: sem SUPABASE_URL, apenas salva o arquivo JSON.
    """
    Path('data').mkdir(exist_ok=True)
    Path(f'data/{arquivo}').write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    # Persistência no banco — ativa com SUPABASE_URL (Story 2.2)
    if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY'):
        try:
            from db_provider import get_client, _rotear_para_supabase
            supabase = get_client()
            if supabase:
                edicao_id = edicao_id or os.environ.get('EDICAO_ID')
                _rotear_para_supabase(supabase, dados, arquivo, edicao_id)
        except Exception as e:
            print(f'  ⚠️  Supabase indisponível ({e}) — continuando sem persistência')


def main():
    print("🤖 Iniciando triagem de conteúdo...")

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY não configurado!")

    cliente = anthropic.Anthropic(api_key=api_key)
    prompt_base = carregar_prompt_triagem()
    conteudos = carregar_todo_conteudo()

    print(f"  Total para triar: {len(conteudos)} itens")
    num_batches = (len(conteudos) + TAMANHO_BATCH - 1) // TAMANHO_BATCH
    print(f"  Processando em {num_batches} batch(es) de até {TAMANHO_BATCH} itens")

    triados = []
    alto = 0
    medio = 0
    baixo = 0

    # Processa em batches de TAMANHO_BATCH itens por chamada ao Haiku
    for b in range(0, len(conteudos), TAMANHO_BATCH):
        batch = conteudos[b:b + TAMANHO_BATCH]
        num_batch = b // TAMANHO_BATCH + 1
        print(f"  [Batch {num_batch}/{num_batches}] Triando {len(batch)} itens...")

        resultados_batch = triar_em_batch(cliente, prompt_base, batch)

        for resultado in resultados_batch:
            relevancia = resultado['triagem'].get('relevancia', 'BAIXO')
            titulo = resultado.get('titulo', resultado.get('assunto', 'sem título'))[:60]

            if relevancia == 'ALTO':
                alto += 1
                triados.append(resultado)
                print(f"    ✅ ALTO: {titulo}")
            elif relevancia == 'MEDIO':
                medio += 1
                triados.append(resultado)
                print(f"    🔶 MEDIO: {titulo}")
            else:
                baixo += 1

    print(f"\n  📊 Resultado: ALTO={alto}, MEDIO={medio}, BAIXO={baixo} (descartados)")
    print(f"  ✅ {len(triados)} itens passaram na triagem")

    salvar_resultado(triados, 'conteudo_triado.json')
    print("✅ Conteúdo triado salvo em data/conteudo_triado.json")


if __name__ == '__main__':
    main()
