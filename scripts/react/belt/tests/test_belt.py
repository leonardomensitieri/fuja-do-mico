"""
Testes unitários para o Tool Belt dos agentes ReAct.

Todos os cenários usam mock — sem chamadas reais a APIs externas.
Cobre os 7 tools com cenários de sucesso e falha encapsulada.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from scripts.react.tools import ToolResult


# ── BrapiQueryTool ────────────────────────────────────────────────────────────

class TestBrapiQueryTool:

    def test_sucesso_retorna_tool_result_positivo(self):
        """Mock de buscar_tickers retornando dados válidos."""
        dados_mock = [{"ticker": "PETR4", "preco": 38.50}]

        with patch.dict(os.environ, {"BRAPI_TOKEN": "token_teste"}):
            with patch("scripts.react.belt.brapi_query._carregar_buscar_tickers") as mock_loader:
                mock_loader.return_value = MagicMock(return_value=dados_mock)
                from scripts.react.belt.brapi_query import BrapiQueryTool
                tool = BrapiQueryTool()
                resultado = tool.execute(tickers=["PETR4"])

        assert isinstance(resultado, ToolResult)
        assert resultado.success is True
        assert resultado.data == dados_mock
        assert resultado.source == "brapi"

    def test_falha_api_encapsulada(self):
        """Exceção na busca deve retornar ToolResult de erro, não propagar."""
        with patch.dict(os.environ, {"BRAPI_TOKEN": "token_teste"}):
            with patch("scripts.react.belt.brapi_query._carregar_buscar_tickers") as mock_loader:
                mock_loader.return_value = MagicMock(side_effect=ConnectionError("API offline"))
                from scripts.react.belt.brapi_query import BrapiQueryTool
                tool = BrapiQueryTool()
                resultado = tool.execute(tickers=["VALE3"])

        assert resultado.success is False
        assert "API offline" in resultado.error

    def test_sem_token_retorna_erro(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("BRAPI_TOKEN", None)
            from scripts.react.belt.brapi_query import BrapiQueryTool
            tool = BrapiQueryTool()
            resultado = tool.execute(tickers=["PETR4"])

        assert resultado.success is False
        assert "BRAPI_TOKEN" in resultado.error

    def test_tickers_vazio_retorna_erro(self):
        with patch.dict(os.environ, {"BRAPI_TOKEN": "tok"}):
            from scripts.react.belt.brapi_query import BrapiQueryTool
            tool = BrapiQueryTool()
            resultado = tool.execute(tickers=[])

        assert resultado.success is False


# ── FintzQueryTool ────────────────────────────────────────────────────────────

class TestFintzQueryTool:

    def test_sucesso_retorna_tool_result_positivo(self):
        dados_mock = {"PETR4": {"P_L": 5.2, "DividendYield": 0.12}}

        with patch.dict(os.environ, {"FINTZ_API_KEY": "key_teste"}):
            with patch("scripts.react.belt.fintz_query._carregar_buscar_dados_fintz") as mock_loader:
                mock_loader.return_value = MagicMock(return_value=dados_mock)
                from scripts.react.belt.fintz_query import FintzQueryTool
                tool = FintzQueryTool()
                resultado = tool.execute(tickers=["PETR4"])

        assert resultado.success is True
        assert resultado.source == "fintz"

    def test_falha_encapsulada(self):
        with patch.dict(os.environ, {"FINTZ_API_KEY": "key"}):
            with patch("scripts.react.belt.fintz_query._carregar_buscar_dados_fintz") as mock_loader:
                mock_loader.return_value = MagicMock(side_effect=TimeoutError("timeout"))
                from scripts.react.belt.fintz_query import FintzQueryTool
                tool = FintzQueryTool()
                resultado = tool.execute(tickers=["ITUB4"])

        assert resultado.success is False
        assert "timeout" in resultado.error

    def test_sem_token_retorna_erro(self):
        env_limpo = {k: v for k, v in os.environ.items() if k != "FINTZ_API_KEY"}
        with patch.dict(os.environ, env_limpo, clear=True):
            from scripts.react.belt.fintz_query import FintzQueryTool
            tool = FintzQueryTool()
            resultado = tool.execute(tickers=["VALE3"])

        assert resultado.success is False
        assert "FINTZ_API_KEY" in resultado.error


# ── ValuationCalculatorTool ───────────────────────────────────────────────────

class TestValuationCalculatorTool:

    @pytest.fixture(autouse=True)
    def tool(self):
        from scripts.react.belt.valuation_calculator import ValuationCalculatorTool
        return ValuationCalculatorTool()

    def test_calculo_graham_correto(self, tool):
        """Graham = sqrt(22.5 * LPA * VPA). Com LPA=2.5, VPA=18 → sqrt(22.5*2.5*18) = sqrt(1012.5) ≈ 31.82"""
        resultado = tool.execute(ticker="PETR4", lpa=2.5, vpa=18.0, dy=2.0)

        assert resultado.success is True
        import math
        esperado = round(math.sqrt(22.5 * 2.5 * 18.0), 2)
        assert resultado.data["graham"] == esperado

    def test_calculo_bazin_correto(self, tool):
        """Bazin = DY / 0.06. Com DY=3.0 → 3.0/0.06 = 50.0"""
        resultado = tool.execute(ticker="PETR4", lpa=2.5, vpa=18.0, dy=3.0)

        assert resultado.success is True
        assert resultado.data["bazin"] == 50.0

    def test_lpa_negativo_graham_zero(self, tool):
        """Empresa com prejuízo (LPA negativo) → Graham = 0 (não raiz de negativo)."""
        resultado = tool.execute(ticker="XPTO3", lpa=-1.5, vpa=10.0, dy=0.0)

        assert resultado.success is True
        assert resultado.data["graham"] == 0.0

    def test_ticker_incluido_no_resultado(self, tool):
        resultado = tool.execute(ticker="WEGE3", lpa=3.0, vpa=15.0, dy=1.2)
        assert resultado.data["ticker"] == "WEGE3"

    def test_excecao_encapsulada(self, tool):
        """Parâmetro não-numérico deve retornar erro sem propagar exceção."""
        resultado = tool.execute(ticker="X", lpa="invalido", vpa=10.0, dy=1.0)
        assert resultado.success is False


# ── CalculatorTool ────────────────────────────────────────────────────────────

class TestCalculatorTool:

    @pytest.fixture(autouse=True)
    def tool(self):
        from scripts.react.belt.calculator import CalculatorTool
        return CalculatorTool()

    def test_expressao_valida_soma(self, tool):
        resultado = tool.execute(formula="2 + 3")
        assert resultado.success is True
        assert resultado.data["resultado"] == 5

    def test_expressao_valida_sqrt(self, tool):
        resultado = tool.execute(formula="sqrt(16)")
        assert resultado.success is True
        assert resultado.data["resultado"] == 4.0

    def test_expressao_graham(self, tool):
        """Fórmula Graham completa: sqrt(22.5 * 2.5 * 18)"""
        resultado = tool.execute(formula="sqrt(22.5 * 2.5 * 18)")
        assert resultado.success is True
        import math
        assert abs(resultado.data["resultado"] - math.sqrt(22.5 * 2.5 * 18)) < 0.01

    def test_expressao_maliciosa_import_bloqueada(self, tool):
        """__import__ deve ser bloqueado — retorna erro sem executar."""
        resultado = tool.execute(formula="__import__('os')")
        assert resultado.success is False
        assert resultado.data is None

    def test_expressao_maliciosa_dunder_bloqueada(self, tool):
        """Acesso a atributos deve ser bloqueado."""
        resultado = tool.execute(formula="(1).__class__")
        assert resultado.success is False

    def test_expressao_maliciosa_exec_bloqueada(self, tool):
        resultado = tool.execute(formula="exec('import os')")
        assert resultado.success is False

    def test_formula_vazia_retorna_erro(self, tool):
        resultado = tool.execute(formula="")
        assert resultado.success is False

    def test_divisao_por_zero_encapsulada(self, tool):
        resultado = tool.execute(formula="10 / 0")
        assert resultado.success is False


# ── WebSearchTool ─────────────────────────────────────────────────────────────

class TestWebSearchTool:

    @pytest.fixture(autouse=True)
    def tool(self):
        from scripts.react.belt.web_search import WebSearchTool
        return WebSearchTool()

    def test_sucesso_retorna_lista_normalizada(self, tool):
        resposta_mock = MagicMock()
        resposta_mock.json.return_value = {
            "results": [
                {"title": "PETR4 sobe", "url": "https://exemplo.com", "highlights": ["Petrobras subiu 3%"]},
            ]
        }
        resposta_mock.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"EXA_API_KEY": "key_teste"}):
            with patch("scripts.react.belt.web_search.requests.post", return_value=resposta_mock):
                resultado = tool.execute(query="PETR4 dividendos 2025")

        assert resultado.success is True
        assert isinstance(resultado.data, list)
        assert resultado.data[0]["title"] == "PETR4 sobe"
        assert resultado.source == "exa"

    def test_falha_rede_encapsulada(self, tool):
        import requests as req
        with patch.dict(os.environ, {"EXA_API_KEY": "key"}):
            with patch("scripts.react.belt.web_search.requests.post", side_effect=req.ConnectionError("offline")):
                resultado = tool.execute(query="VALE3")

        assert resultado.success is False
        assert "offline" in resultado.error

    def test_sem_api_key_retorna_erro(self, tool):
        env_limpo = {k: v for k, v in os.environ.items() if k != "EXA_API_KEY"}
        with patch.dict(os.environ, env_limpo, clear=True):
            resultado = tool.execute(query="mercado financeiro")

        assert resultado.success is False
        assert "EXA_API_KEY" in resultado.error


# ── RssFetchTool ──────────────────────────────────────────────────────────────

class TestRssFetchTool:

    @pytest.fixture(autouse=True)
    def tool(self):
        from scripts.react.belt.rss_fetch import RssFetchTool
        return RssFetchTool()

    def test_sucesso_retorna_itens_normalizados(self, tool):
        resposta_http = MagicMock()
        resposta_http.text = "<rss></rss>"
        resposta_http.raise_for_status = MagicMock()

        feed_mock = MagicMock()
        feed_mock.bozo = False
        feed_mock.entries = [
            MagicMock(
                get=lambda k, d="": {"title": "Notícia 1", "link": "https://ex.com", "published": "2025-01-01", "summary": "Resumo"}.get(k, d)
            )
        ]

        with patch("scripts.react.belt.rss_fetch.requests.get", return_value=resposta_http):
            with patch("scripts.react.belt.rss_fetch.feedparser.parse", return_value=feed_mock):
                resultado = tool.execute(url="https://feed.exemplo.com/rss")

        assert resultado.success is True
        assert resultado.source == "rss"

    def test_url_invalida_encapsulada(self, tool):
        import requests as req
        with patch("scripts.react.belt.rss_fetch.requests.get", side_effect=req.ConnectionError("URL inválida")):
            resultado = tool.execute(url="https://nao-existe.xyz/rss")

        assert resultado.success is False
        assert resultado.data is None

    def test_url_vazia_retorna_erro(self, tool):
        resultado = tool.execute(url="")
        assert resultado.success is False


# ── HumanFeedbackTool ─────────────────────────────────────────────────────────

class TestHumanFeedbackTool:

    @pytest.fixture(autouse=True)
    def tool(self):
        from scripts.react.belt.human_feedback import HumanFeedbackTool
        return HumanFeedbackTool()

    def test_sucesso_retorna_status_sent(self, tool):
        resposta_mock = MagicMock()
        resposta_mock.json.return_value = {"result": {"message_id": 42}}
        resposta_mock.raise_for_status = MagicMock()

        env = {"TELEGRAM_BOT_TOKEN": "123:ABC", "TELEGRAM_CHAT_ID": "-100xyz"}
        with patch.dict(os.environ, env):
            with patch("scripts.react.belt.human_feedback.requests.post", return_value=resposta_mock):
                with patch("scripts.react.belt.human_feedback._registrar_na_fila"):
                    resultado = tool.execute(message="Aprovar análise de PETR4?")

        assert resultado.success is True
        assert resultado.data["status"] == "sent"
        assert resultado.data["message_id"] == 42
        assert resultado.source == "telegram"

    def test_sem_credenciais_retorna_erro(self, tool):
        env_limpo = {k: v for k, v in os.environ.items() if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}
        with patch.dict(os.environ, env_limpo, clear=True):
            with patch("scripts.react.belt.human_feedback._registrar_na_fila"):
                resultado = tool.execute(message="Teste")

        assert resultado.success is False
        assert "TELEGRAM_BOT_TOKEN" in resultado.error or "TELEGRAM_CHAT_ID" in resultado.error

    def test_falha_rede_encapsulada(self, tool):
        import requests as req
        env = {"TELEGRAM_BOT_TOKEN": "123:ABC", "TELEGRAM_CHAT_ID": "-100xyz"}
        with patch.dict(os.environ, env):
            with patch("scripts.react.belt.human_feedback.requests.post", side_effect=req.ConnectionError("offline")):
                with patch("scripts.react.belt.human_feedback._registrar_na_fila"):
                    resultado = tool.execute(message="Teste de falha")

        assert resultado.success is False
        assert "offline" in resultado.error

    def test_message_vazia_retorna_erro(self, tool):
        resultado = tool.execute(message="")
        assert resultado.success is False
