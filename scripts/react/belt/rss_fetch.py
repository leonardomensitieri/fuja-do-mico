"""
RssFetchTool — busca e parseia feeds RSS.

Usa requests para o download (com timeout) + feedparser para parsing.
feedparser não suporta timeout nativo, por isso o request é separado.
Retorna lista de {"title", "link", "published", "summary"}.
"""

from __future__ import annotations

import logging
from typing import Any, List

import feedparser
import requests

from scripts.react.tools import Tool, ToolResult

logger = logging.getLogger(__name__)

_TIMEOUT_SEGUNDOS = 10
_USER_AGENT = "FujaDoMico-Newsletter/1.0 (RSS Reader)"


class RssFetchTool(Tool):
    """
    Busca e parseia artigos de feeds RSS.

    Use para coletar notícias de portais financeiros, blogs de investimento
    e qualquer fonte com feed RSS disponível.
    Parâmetros: url (string do feed RSS), max_items (int, opcional, default 10).
    """

    @property
    def name(self) -> str:
        return "rss_fetch"

    @property
    def description(self) -> str:
        return (
            "Busca artigos de um feed RSS. "
            "Use para coletar notícias de portais financeiros (InfoMoney, Valor, B3, etc.). "
            "Parâmetros: url (URL do feed RSS), max_items (int, opcional, default 10, máx 50)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL do feed RSS (ex: 'https://www.infomoney.com.br/feed/')",
                },
                "max_items": {
                    "type": "integer",
                    "description": "Número máximo de itens a retornar (1-50, default: 10)",
                },
            },
            "required": ["url"],
        }

    def execute(self, **kwargs) -> ToolResult:
        """Busca e retorna itens do feed RSS."""
        try:
            url = kwargs.get("url", "").strip()
            if not url:
                return ToolResult(success=False, data=None, error="Parâmetro 'url' é obrigatório.")

            max_items = min(int(kwargs.get("max_items", 10)), 50)

            # Download com timeout (feedparser não suporta timeout nativo)
            resposta = requests.get(
                url,
                timeout=_TIMEOUT_SEGUNDOS,
                headers={"User-Agent": _USER_AGENT},
            )
            resposta.raise_for_status()

            # Parsing via feedparser
            feed = feedparser.parse(resposta.text)

            if feed.bozo and not feed.entries:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Feed inválido ou inacessível: {feed.bozo_exception}",
                )

            itens: List[Any] = []
            for entry in feed.entries[:max_items]:
                itens.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", "")[:500],  # limita resumo
                })

            return ToolResult(success=True, data=itens, source="rss")

        except requests.RequestException as e:
            logger.warning("[RssFetchTool] Erro de rede: %s", e)
            return ToolResult(success=False, data=None, error=f"Falha ao acessar feed RSS: {e}")
        except Exception as e:
            logger.warning("[RssFetchTool] Erro inesperado: %s", e)
            return ToolResult(success=False, data=None, error=str(e))
