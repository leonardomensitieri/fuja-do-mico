"""
Node Notícias — Deep Research Semanal
======================================
Decision Tree: Criatividade? NÃO → Algoritmo? NÃO → External API? SIM → ReActAgent com WebSearch

O que faz:
  1. Lê queries de config/deep_research_queries.json
  2. Para cada query: executa ReActAgent com WebSearch (EXA) — max 5 iterações
  3. Grava resultado em conteudo_raw individualmente

Credenciais necessárias (GitHub Secrets):
  - EXA_API_KEY         : busca web via EXA API
  - ANTHROPIC_API_KEY   : Claude Sonnet para o ReActAgent
  - SUPABASE_URL        : URL do projeto Supabase
  - SUPABASE_SERVICE_KEY: chave de serviço

Execução: domingo às 6h UTC — antes do pipeline de segunda-feira 8h Brasília (11h UTC).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# fuja-do-mico-gh/ no path → permite 'from scripts.react.*'
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
# scripts/ no path → permite 'from db_provider import get_client'
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.react.agent import ReActAgent
from scripts.react.belt.web_search import WebSearchTool
from scripts.react.criteria import ReActStopCriteria

CONFIG_QUERIES_PATH = Path('config/deep_research_queries.json')

SYSTEM_PROMPT = """Você é um pesquisador especializado em mercado financeiro brasileiro.
Sua tarefa é pesquisar informações atualizadas e relevantes sobre o tema fornecido,
usando a ferramenta de busca web disponível.

Diretrizes:
- Foque em fatos, dados e tendências recentes (últimos 7 dias preferentemente)
- Cite as fontes encontradas (URLs) ao estruturar o resultado
- Sintetize o que encontrou em uma análise concisa (300-500 palavras)
- Priorize fontes confiáveis: Valor Econômico, InfoMoney, BTG, XP, Banco Central, B3
- Idioma: português brasileiro

Ao finalizar, retorne sua análise completa sobre o tema pesquisado."""


def carregar_queries() -> list[str]:
    """Carrega queries de pesquisa do arquivo de configuração externo."""
    if not CONFIG_QUERIES_PATH.exists():
        print(f'  ⚠️  {CONFIG_QUERIES_PATH} não encontrado — encerrando.')
        return []
    config = json.loads(CONFIG_QUERIES_PATH.read_text(encoding='utf-8'))
    return config.get('queries', [])


def gravar_resultado(supabase, query: str, conteudo: str, iteracoes: int) -> None:
    """Grava resultado de uma pesquisa em conteudo_raw."""
    if not supabase:
        return
    try:
        supabase.table('conteudo_raw').insert({
            'fonte': 'research',
            'plataforma': 'web',
            'tipo_conteudo': 'research',
            'conta_origem': 'deep_research',
            'conteudo_texto': conteudo[:8000],
            'url_original': None,
            'data_publicacao': datetime.now(tz=timezone.utc).isoformat(),
            'processado': False,
            'metadata': {
                'query': query,
                'iteracoes': iteracoes,
                'data_pesquisa': datetime.now(tz=timezone.utc).isoformat(),
            },
        }).execute()
    except Exception as e:
        print(f'  ⚠️  Erro ao gravar resultado em conteudo_raw ({e}) — continuando')


def main():
    print('🔍 Iniciando Node Notícias — Deep Research Semanal...')

    if not os.environ.get('EXA_API_KEY'):
        print('⚠️  EXA_API_KEY não configurada — encerrando.')
        return

    if not os.environ.get('ANTHROPIC_API_KEY'):
        print('⚠️  ANTHROPIC_API_KEY não configurada — encerrando.')
        return

    # Supabase: opcional — sem ele, resultados são apenas logados
    supabase = None
    if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY'):
        try:
            from db_provider import get_client
            supabase = get_client()
        except Exception as e:
            print(f'  ⚠️  Falha ao conectar ao Supabase ({e}) — resultados não serão persistidos')
    else:
        print('  ℹ️  Supabase não configurado — resultados apenas logados')

    queries = carregar_queries()
    if not queries:
        print('  Pool de queries vazio — encerrando.')
        return

    # Configura critérios de parada conforme AC 4
    criterios = ReActStopCriteria(
        max_iterations=5,
        confidence_threshold=0.80,
        min_iterations=1,
        timeout_seconds=120,
        agent_id='deep_research',
    )

    # Instancia o agente com WebSearchTool (EXA) — AC 3 e AC 4
    agente = ReActAgent(
        agent_id='deep_research',
        system_prompt=SYSTEM_PROMPT,
        criteria=criterios,
        tool_belt=[WebSearchTool()],
        model='claude-sonnet-4-6',
    )

    total = 0
    for query in queries:
        print(f'\n  🔎 Pesquisando: "{query}"')
        try:
            resultado = agente.run(
                task=f'Pesquise sobre: {query}',
                context={'data_pesquisa': datetime.now(tz=timezone.utc).isoformat()},
            )

            # Extrai texto do output (pode ser str ou dict)
            if isinstance(resultado.output, str):
                conteudo = resultado.output
            elif isinstance(resultado.output, dict):
                conteudo = json.dumps(resultado.output, ensure_ascii=False)
            else:
                conteudo = str(resultado.output) if resultado.output else ''

            iteracoes = len(resultado.trace.iterations)
            print(f'    Stop reason: {resultado.stop_reason} | Iterações: {iteracoes} | Confiança: {resultado.confidence:.2f}')
            print(f'    Conteúdo ({len(conteudo)} chars): {conteudo[:120]}...')

            gravar_resultado(supabase, query, conteudo, iteracoes)
            total += 1

        except Exception as e:
            print(f'  ⚠️  Erro ao pesquisar "{query}": {e} — continuando')

    print(f'\n✅ Total: {total} pesquisas gravadas em conteudo_raw.')


if __name__ == '__main__':
    main()
