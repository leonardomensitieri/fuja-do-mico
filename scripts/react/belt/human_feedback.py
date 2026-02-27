"""
HumanFeedbackTool — solicita feedback humano via Telegram (V1: fire-and-forget).

Envia mensagem ao operador via Telegram e registra em fila local.
V1: NÃO bloqueia aguardando resposta. O loop ReAct continua.
V2: implementará polling via /getUpdates com timeout configurável.

Credenciais: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID via os.environ.
Fila local: data/human_feedback_queue.json (append).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from scripts.react.tools import Tool, ToolResult

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT_SEGUNDOS = 10

# Localização da fila relativa ao raiz do projeto (fuja-do-mico-gh/)
_FILA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "human_feedback_queue.json"


def _registrar_na_fila(message: str, status: str = "pending", message_id: Any = None) -> None:
    """Registra a solicitação na fila local de feedback humano."""
    try:
        _FILA_PATH.parent.mkdir(parents=True, exist_ok=True)

        entrada = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "status": status,
            "telegram_message_id": message_id,
        }

        # Append: carrega existente ou cria novo
        fila: list = []
        if _FILA_PATH.exists():
            try:
                fila = json.loads(_FILA_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                fila = []

        fila.append(entrada)
        _FILA_PATH.write_text(json.dumps(fila, ensure_ascii=False, indent=2), encoding="utf-8")

    except Exception as e:
        logger.warning("[HumanFeedbackTool] Falha ao registrar na fila: %s", e)


class HumanFeedbackTool(Tool):
    """
    Envia solicitação de feedback humano via Telegram (V1: fire-and-forget).

    Use quando o agente precisar de julgamento humano para continuar.
    A mensagem é enviada ao operador e registrada em data/human_feedback_queue.json.
    O loop ReAct NÃO pausa aguardando resposta (V1).
    Parâmetros: message (string), timeout_seconds (int, opcional, default 300 — reservado para V2).
    """

    @property
    def name(self) -> str:
        return "human_feedback"

    @property
    def description(self) -> str:
        return (
            "Solicita feedback humano enviando mensagem via Telegram. "
            "Use quando precisar de julgamento humano (aprovação, contexto, verificação). "
            "V1: fire-and-forget — o loop continua sem aguardar resposta. "
            "Parâmetros: message (string com a pergunta/contexto para o operador)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Mensagem de solicitação ao operador humano",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout em segundos (reservado para V2, ignorado na V1)",
                },
            },
            "required": ["message"],
        }

    def execute(self, **kwargs) -> ToolResult:
        """Envia mensagem Telegram e registra na fila de feedback."""
        try:
            message = kwargs.get("message", "").strip()
            if not message:
                return ToolResult(success=False, data=None, error="Parâmetro 'message' é obrigatório.")

            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

            if not bot_token or not chat_id:
                _registrar_na_fila(message, status="sem_credenciais")
                return ToolResult(
                    success=False,
                    data=None,
                    error="TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados.",
                )

            # Prefixo para identificar mensagens do loop ReAct
            texto_completo = f"🤖 *[Fuja do Mico — Feedback Solicitado]*\n\n{message}"

            url = _TELEGRAM_API.format(token=bot_token)
            resposta = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": texto_completo,
                    "parse_mode": "Markdown",
                },
                timeout=_TIMEOUT_SEGUNDOS,
            )
            resposta.raise_for_status()

            dados = resposta.json()
            message_id = dados.get("result", {}).get("message_id")

            _registrar_na_fila(message, status="sent", message_id=message_id)

            return ToolResult(
                success=True,
                data={"status": "sent", "message_id": message_id},
                source="telegram",
            )

        except requests.RequestException as e:
            logger.warning("[HumanFeedbackTool] Falha no envio Telegram: %s", e)
            _registrar_na_fila(kwargs.get("message", ""), status="erro_envio")
            return ToolResult(success=False, data=None, error=f"Falha ao enviar para Telegram: {e}")
        except Exception as e:
            logger.warning("[HumanFeedbackTool] Erro inesperado: %s", e)
            return ToolResult(success=False, data=None, error=str(e))
