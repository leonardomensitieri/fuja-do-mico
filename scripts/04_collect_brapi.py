"""
SCRIPT 04 — Dados Financeiros (Brapi)
=======================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? SIM → Worker with API

O que faz:
  - Busca múltiplos financeiros das ações configuradas em TICKERS
  - Salva em data/brapi_raw.json para uso pelo agente de conteúdo (script 06)

Campos retornados pelo plano gratuito Brapi:
  - Cotação: preço, variação %, máx/mín 52 semanas
  - Valuation: P/L (trailingPE), P/VP (priceToBook), PEG Ratio, Market Cap
  - Rentabilidade: ROE, ROA, FCL, Lucro líquido, margens
  - Perfil: setor, indústria, descrição da empresa

NÃO disponível no plano gratuito: Dividend Yield, Dívida/PL, dados de analistas.

Credenciais necessárias (GitHub Secrets):
  - BRAPI_TOKEN : token em https://brapi.dev
  - TICKERS     : lista separada por vírgula (ex: "PETR4,VALE3,ITUB4")
                  Se ausente, usa TICKERS_PADRAO

Função auxiliar buscar_tickers() pode ser importada por outros scripts
para consulta on-demand de qualquer ticker dos 1.842 disponíveis na B3.
"""

import os
import json
import requests
from pathlib import Path


# Tickers monitorados por padrão se TICKERS não estiver configurado
TICKERS_PADRAO = "PETR4,VALE3,ITUB4,BBDC4,WEGE3"

BRAPI_BASE_URL = "https://brapi.dev/api"
MODULOS = "summaryProfile,financialData,defaultKeyStatistics"


def buscar_tickers(tickers: list, token: str) -> list:
    """
    Busca dados financeiros de uma lista de tickers na API Brapi.
    Pode ser importada e chamada por outros scripts para consulta on-demand.

    Args:
        tickers: lista de strings com os códigos (ex: ["PETR4", "WEGE3"])
        token: BRAPI_TOKEN

    Returns:
        lista de dicts com os múltiplos financeiros de cada ação
    """
    tickers_str = ','.join(tickers)
    url = f"{BRAPI_BASE_URL}/quote/{tickers_str}"
    params = {'modules': MODULOS, 'token': token}

    try:
        resposta = requests.get(url, params=params, timeout=30)
        resposta.raise_for_status()
        dados = resposta.json()
    except Exception as e:
        print(f"  ⚠️  Erro ao chamar Brapi ({tickers_str}): {e}")
        return []

    acoes = []
    for resultado in dados.get('results', []):
        fd = resultado.get('financialData', {}) or {}
        dk = resultado.get('defaultKeyStatistics', {}) or {}
        sp = resultado.get('summaryProfile', {}) or {}

        acao = {
            # Identificação
            'ticker':    resultado.get('symbol', ''),
            'nome':      resultado.get('longName') or resultado.get('shortName', ''),
            'setor':     sp.get('sector', ''),
            'industria': sp.get('industry', ''),
            'descricao': sp.get('longBusinessSummary', ''),

            # Cotação
            'preco':          resultado.get('regularMarketPrice'),
            'variacao_pct':   resultado.get('regularMarketChangePercent'),
            'min_52s':        resultado.get('fiftyTwoWeekLow'),
            'max_52s':        resultado.get('fiftyTwoWeekHigh'),

            # Valuation (campos corretos do plano gratuito)
            'pl':        dk.get('trailingPE'),       # P/L — campo correto
            'pvp':       dk.get('priceToBook'),      # P/VP
            'peg':       dk.get('pegRatio'),          # PEG Ratio (Lynch)
            'lpa':       dk.get('trailingEps'),       # Lucro por ação
            'vpa':       dk.get('bookValue'),         # Valor patrimonial por ação
            'market_cap': dk.get('marketCap'),

            # Rentabilidade
            'roe':            fd.get('returnOnEquity'),   # Retorno sobre PL
            'roa':            fd.get('returnOnAssets'),   # Retorno sobre ativos
            'margem_liquida': fd.get('profitMargins'),
            'margem_bruta':   fd.get('grossMargins'),
            'fcl':            fd.get('freeCashflow'),     # Fluxo de caixa livre
            'lucro_liquido':  dk.get('netIncomeToCommon'),
            'receita':        fd.get('totalRevenue'),

            # Crescimento
            'crescimento_lucro':  fd.get('earningsGrowth'),
            'crescimento_receita': fd.get('revenueGrowth'),
        }

        # Remove campos None para deixar o JSON limpo
        acao = {k: v for k, v in acao.items() if v is not None}
        acoes.append(acao)

        pl_str = f"{acao['pl']:.1f}x" if 'pl' in acao else 'N/D'
        roe_str = f"{acao['roe']*100:.1f}%" if 'roe' in acao else 'N/D'
        print(f"  {acao['ticker']}: P/L={pl_str}, ROE={roe_str}, Preço=R${acao.get('preco', 'N/D')}")

    return acoes


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
    print("📊 Iniciando coleta Brapi...")

    token = os.environ.get('BRAPI_TOKEN')
    tickers_raw = os.environ.get('TICKERS', TICKERS_PADRAO)
    tickers = [t.strip() for t in tickers_raw.split(',') if t.strip()]

    if not token:
        print("⚠️  BRAPI_TOKEN não configurado. Salvando lista vazia.")
        salvar_resultado([], 'brapi_raw.json')
        return

    print(f"  Buscando: {', '.join(tickers)}")
    acoes = buscar_tickers(tickers, token)

    salvar_resultado(acoes, 'brapi_raw.json')
    print(f"✅ {len(acoes)} ações salvas em data/brapi_raw.json")


if __name__ == '__main__':
    main()
