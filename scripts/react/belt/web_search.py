"""
WebSearchTool — busca na web via EXA API.

Credencial: EXA_API_KEY via os.environ.
Endpoint: POST https://api.exa.ai/search
Retorna lista de {"title", "url", "snippet"} com max_results itens.
"""

from __future__ import annotations

import logging
import os
from typing import Any, List

import requests

from scripts.react.tools import Tool, ToolResult

logger = logging.getLogger(__name__)

_EXA_ENDPOINT = "https://api.exa.ai/search"
_TIMEOUT_SEGUNDOS = 15


class WebSearchTool(Tool):
    """
    Realiza buscas na web via EXA API.

    Use para pesquisar notícias financeiras, artigos e informações atualizadas.
    Requer variável de ambiente EXA_API_KEY.
    Parâmetros: query (string), max_results (int, opcional, default 5).
    """

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Busca informações na web via EXA. "
            "Use para notícias, análises recentes, contexto de mercado e pesquisa. "
            "Parâmetros: query (string de busca), max_results (int, opcional, default 5, máx 10)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termos de busca (ex: 'PETR4 resultados 2025 dividendos')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Número máximo de resultados (1-10, default: 5)",
                },
            },
            "required": ["query"],
        }

    def execute(self, **kwargs) -> ToolResult:
        """Busca na web via EXA API."""
        try:
            query = kwargs.get("query", "").strip()
            if not query:
                return ToolResult(success=False, data=None, error="Parâmetro 'query' é obrigatório.")

            max_results = min(int(kwargs.get("max_results", 5)), 10)

            api_key = os.environ.get("EXA_API_KEY", "")
            if not api_key:
                return ToolResult(success=False, data=None, error="Variável de ambiente EXA_API_KEY não configurada.")

            resposta = requests.post(
                _EXA_ENDPOINT,
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={"query": query, "numResults": max_results},
                timeout=_TIMEOUT_SEGUNDOS,
            )
            resposta.raise_for_status()

            dados = resposta.json()
            resultados: List[Any] = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": (item.get("highlights") or [""])[0] if item.get("highlights") else item.get("text", "")[:200],
                }
                for item in dados.get("results", [])
            ]

            return ToolResult(success=True, data=resultados, source="exa")

        except requests.RequestException as e:
            logger.warning("[WebSearchTool] Erro de rede: %s", e)
            return ToolResult(success=False, data=None, error=f"Falha na busca EXA: {e}")
        except Exception as e:
            logger.warning("[WebSearchTool] Erro inesperado: %s", e)
            return ToolResult(success=False, data=None, error=str(e))
