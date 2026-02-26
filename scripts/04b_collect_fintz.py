"""
SCRIPT 04b — Dados Financeiros Complementares (Fintz)
=====================================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? SIM → Worker with API

O que faz:
  - Busca indicadores financeiros completos por ticker (P/L, DY, ROE, P/VP, EV/EBITDA...)
  - Busca histórico recente de proventos (dividendos + JCP, últimos 12 meses)
  - Busca dados do Tesouro Direto (lista de títulos + preços atuais)
  - Salva em data/fintz_raw.json para uso pelo agente de conteúdo (script 06)

Campos adicionais vs Brapi gratuito:
  - Dividend Yield (DY) — ausente no Brapi gratuito
  - EV/EBITDA, P/EBITDA, Dívida Bruta/PL
  - Histórico real de proventos (pagamentos, datas, valores)
  - Tesouro Direto: yields, preços, vencimentos

Credenciais necessárias (GitHub Secrets):
  - FINTZ_API_KEY         : chave primária em https://fintz.com.br
  - FINTZ_API_KEY_FALLBACK: chave de fallback (opcional) — usada automaticamente
                            se a primária falhar (cota esgotada, erro 429/401)
  - TICKERS               : lista separada por vírgula (ex: "PETR4,VALE3,ITUB4")
                            Se ausente, usa TICKERS_PADRAO (mesmo do script 04)

Função auxiliar buscar_dados_fintz() pode ser importada por outros scripts
para consulta on-demand de indicadores e proventos de qualquer ticker.
"""

import os
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


# Tickers monitorados por padrão (espelho do script 04)
TICKERS_PADRAO = "PETR4,VALE3,ITUB4,BBDC4,WEGE3"

FINTZ_BASE_URL = "https://api.fintz.com.br"

# Códigos HTTP que indicam cota esgotada ou chave inválida → acionar fallback
ERROS_FALLBACK = {401, 403, 429}


def _headers(token: str) -> dict:
    """Monta os headers de autenticação Fintz."""
    return {"x-api-key": token}


def _resolver_token(token_primario: str, token_fallback: Optional[str]) -> str:
    """
    Verifica se o token primário está funcional com uma chamada de diagnóstico.
    Se retornar código de erro de cota/autenticação e existir fallback, usa o fallback.
    """
    if not token_fallback:
        return token_primario

    url = f"{FINTZ_BASE_URL}/bolsa/b3/avista/indicadores/por-ticker/"
    try:
        resp = requests.get(
            url, headers=_headers(token_primario),
            params={"ticker": "PETR4"}, timeout=10
        )
        if resp.status_code in ERROS_FALLBACK:
            print(f"  ⚠️  Token primário retornou {resp.status_code} — usando fallback")
            return token_fallback
        return token_primario
    except Exception:
        # Em caso de timeout na verificação, mantém o primário
        return token_primario


def buscar_indicadores(ticker: str, token: str) -> dict:
    """
    Busca todos os indicadores financeiros de um ticker na Fintz.
    Retorna um dict {indicador: valor} com o valor mais recente de cada um.

    Indicadores disponíveis (nomes reais da API):
      P_L, P_VP, DividendYield, ROE, ROA, EV_EBITDA, P_EBITDA,
      DividaBruta_PatrimonioLiquido, MargemEBITDA, MargemLiquida,
      DividaLiquida_EBITDA, LPA, VPA, ValorDeMercado, ROIC, etc.
    """
    url = f"{FINTZ_BASE_URL}/bolsa/b3/avista/indicadores/por-ticker/"
    params = {"ticker": ticker}

    try:
        resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
        resp.raise_for_status()
        dados = resp.json()
    except Exception as e:
        print(f"  ⚠️  Erro ao buscar indicadores Fintz ({ticker}): {e}")
        return {}

    # A API retorna lista de {ticker, indicador, valor, data} — campo = "indicador"
    indicadores = {}
    for item in dados:
        nome = item.get("indicador", "")
        valor = item.get("valor")
        if nome and valor is not None:
            indicadores[nome] = valor

    return indicadores


def buscar_proventos(ticker: str, token: str, meses: int = 12) -> list:
    """
    Busca histórico de proventos (dividendos + JCP) dos últimos N meses.
    Retorna lista de dicts com {dataCom, dataPagamento, valor, tipo}.

    Campos reais da API Fintz:
      dataCom, dataPagamento, dataAprovacao, valor, tipo
      tipo: "DIVIDENDO" | "JRS CAP PROPRIO"
    """
    data_inicio = (datetime.today() - timedelta(days=meses * 30)).strftime("%Y-%m-%d")
    url = f"{FINTZ_BASE_URL}/bolsa/b3/avista/proventos/"
    params = {"ticker": ticker, "dataInicio": data_inicio}

    try:
        resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
        resp.raise_for_status()
        dados = resp.json()
    except Exception as e:
        print(f"  ⚠️  Erro ao buscar proventos Fintz ({ticker}): {e}")
        return []

    proventos = []
    for item in dados:
        proventos.append({
            "data_com":       item.get("dataCom", ""),
            "data_pagamento": item.get("dataPagamento", ""),
            "valor":          item.get("valor"),
            "tipo":           item.get("tipo", ""),   # "DIVIDENDO" | "JRS CAP PROPRIO"
        })

    return proventos


def buscar_tesouro(token: str, apenas_investiveis: bool = True) -> list:
    """
    Busca títulos do Tesouro Direto disponíveis.
    Útil para contextualizar yield dos títulos vs. ações (Selic, IPCA+, Prefixado).

    Endpoint real: /titulos-publicos/tesouro/ (com paginação)
    Campos reais: codigo, nome, dataVencimento, vencido, possivelInvestir, possivelResgatar
    """
    url = f"{FINTZ_BASE_URL}/titulos-publicos/tesouro/"
    params = {"tamanho": 50}  # Pega os primeiros 50 títulos
    try:
        resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
        resp.raise_for_status()
        dados = resp.json()
    except Exception as e:
        print(f"  ⚠️  Erro ao buscar Tesouro Direto Fintz: {e}")
        return []

    titulos = []
    for item in dados.get("dados", []):
        # Filtrar apenas investíveis se solicitado
        if apenas_investiveis and not item.get("possivelInvestir", False):
            continue
        titulos.append({
            "codigo":        item.get("codigo", ""),
            "nome":          item.get("nome", ""),
            "vencimento":    item.get("dataVencimento", ""),
            "investivel":    item.get("possivelInvestir", False),
        })

    # Ordenar por nome para facilitar leitura
    titulos.sort(key=lambda t: t["nome"])
    return titulos


def buscar_dados_fintz(tickers: list, token: str) -> dict:
    """
    Busca dados completos (indicadores + proventos) para uma lista de tickers.
    Pode ser importada e chamada por outros scripts para consulta on-demand.

    Args:
        tickers: lista de strings com os códigos (ex: ["PETR4", "WEGE3"])
        token: FINTZ_API_KEY

    Returns:
        dict com:
          - "acoes": lista de dicts por ticker com indicadores e proventos
          - "tesouro": lista de títulos do Tesouro Direto
    """
    acoes = []

    for ticker in tickers:
        print(f"  Buscando {ticker}...")

        indicadores = buscar_indicadores(ticker, token)
        proventos = buscar_proventos(ticker, token)

        # Extrai indicadores-chave com nomes normalizados
        # Nomes reais da API Fintz usam underscore: P_L, P_VP, DividendYield, etc.
        acao = {
            "ticker": ticker,

            # Valuation
            "pl":          indicadores.get("P_L"),
            "pvp":         indicadores.get("P_VP"),
            "dy":          indicadores.get("DividendYield"),   # Ausente no Brapi gratuito
            "ev_ebitda":   indicadores.get("EV_EBITDA"),
            "p_ebitda":    indicadores.get("P_EBITDA"),
            "p_receita":   indicadores.get("P_SR"),
            "lpa":         indicadores.get("LPA"),
            "vpa":         indicadores.get("VPA"),
            "valor_mercado": indicadores.get("ValorDeMercado"),

            # Rentabilidade
            "roe":             indicadores.get("ROE"),
            "roa":             indicadores.get("ROA"),
            "roic":            indicadores.get("ROIC"),
            "margem_ebitda":   indicadores.get("MargemEBITDA"),
            "margem_ebit":     indicadores.get("MargemEBIT"),
            "margem_bruta":    indicadores.get("MargemBruta"),
            "margem_liquida":  indicadores.get("MargemLiquida"),

            # Endividamento
            "divida_bruta_pl":   indicadores.get("DividaBruta_PatrimonioLiquido"),
            "divida_liq_ebitda": indicadores.get("DividaLiquida_EBITDA"),
            "liquidez_corrente": indicadores.get("LiquidezCorrente"),

            # Proventos recentes (últimos 12 meses)
            "proventos_12m": proventos,
            "proventos_total_12m": sum(
                p["valor"] for p in proventos if p.get("valor") is not None
            ),
        }

        # Remove campos None para manter o JSON limpo
        acao = {k: v for k, v in acao.items() if v is not None}
        # Garante que proventos_12m sempre existe (mesmo vazio)
        if "proventos_12m" not in acao:
            acao["proventos_12m"] = []

        dy_str  = f"{acao['dy']*100:.1f}%"  if "dy"  in acao else "N/D"
        pl_str  = f"{acao['pl']:.1f}x"      if "pl"  in acao else "N/D"
        roe_str = f"{acao['roe']*100:.1f}%"  if "roe" in acao else "N/D"
        print(f"    → DY={dy_str}, P/L={pl_str}, ROE={roe_str}")

        acoes.append(acao)

    # Tesouro Direto (uma única chamada independente de tickers)
    print("  Buscando Tesouro Direto...")
    tesouro = buscar_tesouro(token)
    print(f"    → {len(tesouro)} títulos encontrados")

    return {"acoes": acoes, "tesouro": tesouro}


def salvar_resultado(dados: dict, arquivo: str):
    """
    Persiste resultado localmente e no banco (se configurado).
    Extensível: adicionar provider de banco aqui no futuro.
    """
    Path("data").mkdir(exist_ok=True)
    Path(f"data/{arquivo}").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Persistência no banco (futuro):
    # if os.environ.get('DATABASE_URL'):
    #     db_client.save(collection=arquivo, data=dados)


def main():
    print("💰 Iniciando coleta Fintz...")

    token_primario = os.environ.get("FINTZ_API_KEY")
    token_fallback = os.environ.get("FINTZ_API_KEY_FALLBACK")
    tickers_raw = os.environ.get("TICKERS", TICKERS_PADRAO)
    tickers = [t.strip() for t in tickers_raw.split(",") if t.strip()]

    if not token_primario:
        print("⚠️  FINTZ_API_KEY não configurado. Salvando estrutura vazia.")
        salvar_resultado({"acoes": [], "tesouro": []}, "fintz_raw.json")
        return

    # Resolve qual token usar (primário ou fallback)
    token = _resolver_token(token_primario, token_fallback)
    usando_fallback = token != token_primario
    if usando_fallback:
        print("  ℹ️  Usando chave de fallback FINTZ_API_KEY_FALLBACK")

    print(f"  Buscando: {', '.join(tickers)}")
    dados = buscar_dados_fintz(tickers, token)

    # Registra qual chave foi usada nos metadados (sem expor o valor)
    dados["_meta"] = {"usou_fallback": usando_fallback}

    salvar_resultado(dados, "fintz_raw.json")
    print(f"✅ {len(dados['acoes'])} ações + {len(dados['tesouro'])} títulos Tesouro salvos em data/fintz_raw.json")


if __name__ == "__main__":
    main()
