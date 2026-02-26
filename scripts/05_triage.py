"""
SCRIPT 05 — Triagem de Conteúdo (IA)
======================================
Clone com Heurísticas (Finance/Invest — triagem editorial)
Heurísticas: critérios ALTO/MÉDIO/BAIXO definidos em prompts/01-triage.md

O que faz:
  - Lê todos os conteúdos coletados (Gmail + RSS + YouTube)
  - Envia cada item para o Claude com o prompt de triagem
  - Mantém apenas os classificados como ALTO ou MEDIO
  - Salva em data/conteudo_triado.json

Credenciais necessárias (GitHub Secrets):
  - ANTHROPIC_API_KEY : chave da API da Anthropic
"""

import os
import json
import anthropic
from pathlib import Path


def carregar_prompt_triagem() -> str:
    """Carrega o prompt de triagem do arquivo .md"""
    return Path('prompts/01-triage.md').read_text(encoding='utf-8')


def carregar_todo_conteudo() -> list[dict]:
    """Junta todos os conteúdos coletados num único array."""
    todos = []

    for arquivo in ['data/newsletters_raw.json', 'data/rss_raw.json', 'data/youtube_raw.json']:
        path = Path(arquivo)
        if path.exists():
            itens = json.loads(path.read_text())
            todos.extend(itens)
            print(f"  Carregado: {arquivo} ({len(itens)} itens)")

    return todos


def triar_item(cliente: anthropic.Anthropic, prompt_base: str, item: dict) -> dict:
    """
    Envia um item de conteúdo para triagem pelo Claude.
    Retorna o item original enriquecido com o resultado da triagem.
    """
    conteudo = item.get('conteudo', '') or item.get('resumo', '')
    if len(conteudo) < 50:
        return {**item, 'triagem': {'relevancia': 'BAIXO', 'justificativa': 'Conteúdo muito curto'}}

    prompt_completo = prompt_base.replace('{{CONTEUDO}}', conteudo[:3000])

    try:
        resposta = cliente.messages.create(
            model="claude-haiku-4-5-20251001",  # Usa Haiku para triagem (mais rápido/barato)
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt_completo}]
        )

        texto = resposta.content[0].text.strip()

        # Extrai o JSON da resposta
        inicio = texto.find('{')
        fim = texto.rfind('}') + 1
        if inicio >= 0 and fim > inicio:
            triagem = json.loads(texto[inicio:fim])
        else:
            triagem = {'relevancia': 'BAIXO', 'justificativa': 'Resposta inválida da IA'}

    except Exception as e:
        print(f"    ⚠️  Erro na triagem: {e}")
        triagem = {'relevancia': 'BAIXO', 'justificativa': f'Erro: {str(e)}'}

    return {**item, 'triagem': triagem}


def salvar_resultado(dados: list, arquivo: str):
    """
    Persiste resultado localmente e no banco (se configurado).
    Extensível: adicionar provider de banco aqui no futuro.
    """
    Path('data').mkdir(exist_ok=True)
    Path(f'data/{arquivo}').write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    # Persistência no banco (futuro):
    # if os.environ.get('DATABASE_URL'):
    #     db_client.save(collection=arquivo, data=dados)


def main():
    print("🤖 Iniciando triagem de conteúdo...")

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY não configurado!")

    cliente = anthropic.Anthropic(api_key=api_key)
    prompt_base = carregar_prompt_triagem()
    conteudos = carregar_todo_conteudo()

    print(f"  Total para triar: {len(conteudos)} itens")

    triados = []
    alto = 0
    medio = 0
    baixo = 0

    for i, item in enumerate(conteudos):
        print(f"  [{i+1}/{len(conteudos)}] Triando: {item.get('titulo', item.get('assunto', 'sem título'))[:60]}...")
        resultado = triar_item(cliente, prompt_base, item)
        relevancia = resultado['triagem'].get('relevancia', 'BAIXO')

        if relevancia == 'ALTO':
            alto += 1
            triados.append(resultado)
        elif relevancia == 'MEDIO':
            medio += 1
            triados.append(resultado)
        else:
            baixo += 1

    print(f"\n  📊 Resultado: ALTO={alto}, MEDIO={medio}, BAIXO={baixo} (descartados)")
    print(f"  ✅ {len(triados)} itens passaram na triagem")

    salvar_resultado(triados, 'conteudo_triado.json')
    print("✅ Conteúdo triado salvo em data/conteudo_triado.json")


if __name__ == '__main__':
    main()
