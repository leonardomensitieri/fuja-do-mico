"""
BrapiQueryTool — consulta cotações e dados fundamentalistas via Brapi API.

Delega para buscar_tickers() do script 04_collect_brapi.py.
Usa importlib.util porque o módulo começa com dígito (04_).
Credencial: BRAPI_TOKEN via os.environ.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path
from typing import Any

from scripts.react.tools import Tool, ToolResult

logger = logging.getLogger(__name__)

# Localização do script 04 em relação a este arquivo
_SCRIPT_04 = Path(__file__).parent.parent.parent.parent / "scripts" / "04_collect_brapi.py"


def _carregar_buscar_tickers():
    """Carrega buscar_tickers() via importlib (módulo com prefixo numérico)."""
    spec = importlib.util.spec_from_file_location("script_04_brapi", _SCRIPT_04)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.buscar_tickers


class BrapiQueryTool(Tool):
    """
    Consulta dados financeiros de ações na B3 via API Brapi.

    Retorna cotação, valuation (P/L, P/VP), rentabilidade (ROE, ROA) e perfil.
    Use para obter dados de mercado atualizados de tickers específicos.
    NÃO disponível no plano gratuito: Dividend Yield, Dívida/PL.
    Para esses indicadores, use FintzQueryTool.
    """

    @property
    def name(self) -> str:
        return "brapi_query"

    @property
    def description(self) -> str:
        return (
            "Consulta cotações e dados fundamentalistas de ações da B3 via Brapi. "
            "Retorna preço, variação, P/L, P/VP, ROE, market cap e perfil da empresa. "
            "Use para análise fundamentalista. Parâmetro: tickers (lista de strings, ex: ['PETR4', 'VALE3'])."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de tickers da B3 (ex: ['PETR4', 'VALE3', 'ITUB4'])",
                }
            },
            "required": ["tickers"],
        }

    def execute(self, **kwargs) -> ToolResult:
        """Busca dados Brapi para os tickers informados."""
        try:
            tickers = kwargs.get("tickers", [])
            if not tickers:
                return ToolResult(success=False, data=None, error="Parâmetro 'tickers' é obrigatório e não pode ser vazio.")

            token = os.environ.get("BRAPI_TOKEN", "")
            if not token:
                return ToolResult(success=False, data=None, error="Variável de ambiente BRAPI_TOKEN não configurada.")

            buscar_tickers = _carregar_buscar_tickers()
            resultado = buscar_tickers(tickers, token)
            return ToolResult(success=True, data=resultado, source="brapi")

        except Exception as e:
            logger.warning("[BrapiQueryTool] Falha na consulta: %s", e)
            return ToolResult(success=False, data=None, error=str(e))
