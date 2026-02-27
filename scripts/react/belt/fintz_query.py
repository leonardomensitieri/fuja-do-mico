"""
FintzQueryTool — consulta indicadores financeiros completos via Fintz API.

Delega para buscar_dados_fintz() do script 04b_collect_fintz.py.
Usa importlib.util porque o módulo começa com dígito (04b_).
Credencial: FINTZ_API_KEY via os.environ.
Complementa BrapiQueryTool com DY, EV/EBITDA, Dívida/PL e proventos históricos.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path

from scripts.react.tools import Tool, ToolResult

logger = logging.getLogger(__name__)

# Localização do script 04b em relação a este arquivo
_SCRIPT_04B = Path(__file__).parent.parent.parent.parent / "scripts" / "04b_collect_fintz.py"


def _carregar_buscar_dados_fintz():
    """Carrega buscar_dados_fintz() via importlib (módulo com prefixo numérico)."""
    spec = importlib.util.spec_from_file_location("script_04b_fintz", _SCRIPT_04B)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.buscar_dados_fintz


class FintzQueryTool(Tool):
    """
    Consulta indicadores financeiros completos e histórico de proventos via Fintz.

    Retorna DY, EV/EBITDA, P/EBITDA, Dívida Bruta/PL, ROE, proventos históricos.
    Use quando precisar de Dividend Yield ou indicadores ausentes no Brapi gratuito.
    Parâmetros: tickers (lista), incluir_proventos (bool, default True).
    """

    @property
    def name(self) -> str:
        return "fintz_query"

    @property
    def description(self) -> str:
        return (
            "Consulta indicadores financeiros completos e proventos históricos via Fintz. "
            "Inclui Dividend Yield, EV/EBITDA, Dívida/PL e histórico de dividendos. "
            "Use para complementar análise com indicadores ausentes no Brapi. "
            "Parâmetros: tickers (lista de strings), incluir_proventos (bool, opcional, default true)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de tickers da B3 (ex: ['PETR4', 'VALE3'])",
                },
                "incluir_proventos": {
                    "type": "boolean",
                    "description": "Se deve incluir histórico de proventos (default: true)",
                },
            },
            "required": ["tickers"],
        }

    def execute(self, **kwargs) -> ToolResult:
        """Busca dados Fintz para os tickers informados."""
        try:
            tickers = kwargs.get("tickers", [])
            if not tickers:
                return ToolResult(success=False, data=None, error="Parâmetro 'tickers' é obrigatório e não pode ser vazio.")

            incluir_proventos = kwargs.get("incluir_proventos", True)
            token = os.environ.get("FINTZ_API_KEY", "")
            if not token:
                return ToolResult(success=False, data=None, error="Variável de ambiente FINTZ_API_KEY não configurada.")

            buscar_dados_fintz = _carregar_buscar_dados_fintz()
            resultado = buscar_dados_fintz(tickers, token)

            # Remover proventos se solicitado
            if not incluir_proventos and isinstance(resultado, dict):
                for ticker_data in resultado.values():
                    if isinstance(ticker_data, dict):
                        ticker_data.pop("proventos", None)

            return ToolResult(success=True, data=resultado, source="fintz")

        except Exception as e:
            logger.warning("[FintzQueryTool] Falha na consulta: %s", e)
            return ToolResult(success=False, data=None, error=str(e))
