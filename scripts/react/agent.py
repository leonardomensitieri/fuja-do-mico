"""
Classe base do ReAct Loop para os agentes da newsletter Fuja do Mico.

Decision tree: Clone with Heuristics — encapsula raciocínio iterativo
com tool use. Todos os 6 agentes de linha são instâncias desta classe
com system_prompt e tool_belt diferentes. A lógica do loop existe
em exatamente um lugar.

Padrão de uso:
    agente = ReActAgent(
        agent_id="linha_1",
        system_prompt=load_clone_prompt("graham"),
        criteria=CRITERIA["linha_1"],
        tool_belt=[BrapiQueryTool(), FintzQueryTool(), ...],
    )
    resultado = agente.run(task="Analise PETR4 sob a ótica de Graham", context={...})
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from anthropic import Anthropic

from scripts.react.criteria import ReActStopCriteria
from scripts.react.tools import Tool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ThoughtState:
    """
    Estado interno do agente ao final de cada iteração do loop.

    reasoning: o raciocínio textual emitido pelo Claude
    proposed_action: nome do tool que o Claude quer chamar (None = finalizar)
    action_params: parâmetros para o tool proposto
    confidence: score de 0.0 a 1.0 — atualizado pelo _reflect após cada tool call
    output: resultado final (preenchido apenas na última iteração)
    """

    reasoning: str
    proposed_action: str | None = None
    action_params: dict = field(default_factory=dict)
    confidence: float = 0.0
    output: Any = None


@dataclass
class AgentTrace:
    """
    Log completo de uma execução do ReAct Loop.

    Serializable em JSON para compatibilidade futura com LangSmith.
    Todos os campos usam tipos primitivos Python.
    """

    agent_id: str
    iterations: list[dict] = field(default_factory=list)
    stop_reason: str | None = None
    total_elapsed: float = 0.0
    timeout_triggered: bool = False


@dataclass
class AgentResult:
    """Resultado final de uma execução do ReAct Loop."""

    output: Any
    stop_reason: str
    confidence: float
    trace: AgentTrace


class ReActAgent:
    """
    Implementação do ReAct Loop (Reason + Act) para agentes de linha.

    O loop segue o ciclo: Think → Act → Observe → Reflect, controlado
    pelos critérios de parada em ReActStopCriteria. Quando o Claude não
    propõe nenhuma ação, o loop entra na fase de finalização e gera o
    output final.

    Todos os 6 agentes de linha da newsletter são instâncias desta classe
    — diferem apenas no system_prompt (clone ativo) e no tool_belt.
    """

    def __init__(
        self,
        agent_id: str,
        system_prompt: str,
        criteria: ReActStopCriteria,
        tool_belt: list[Tool],
        model: str = "claude-haiku-4-5-20251001",
    ):
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.criteria = criteria
        self.tool_belt = {t.name: t for t in tool_belt}
        self.model = model
        self.client = Anthropic()

    # ── Interface pública ─────────────────────────────────────────────────────

    def run(self, task: str, context: dict | None = None) -> AgentResult:
        """
        Executa o ReAct Loop até atingir um critério de parada.

        Args:
            task: descrição da tarefa para o agente
            context: dados de contexto adicionais (conteúdo triado, dados financeiros, etc.)

        Returns:
            AgentResult com output final, motivo de parada e trace completo
        """
        trace = AgentTrace(agent_id=self.agent_id)
        start = time.time()

        messages = self._build_initial_messages(task, context)
        thought = ThoughtState(reasoning="", confidence=0.0)

        for i in range(self.criteria.max_iterations):
            elapsed = time.time() - start
            deve_parar, motivo = self.criteria.should_stop(i, thought.confidence, elapsed)

            if deve_parar:
                if motivo == "TIMEOUT":
                    logger.warning(
                        "[%s] TIMEOUT após %.1fs — considere aumentar timeout_seconds "
                        "ou simplificar o prompt do agente",
                        self.agent_id,
                        elapsed,
                    )
                    trace.timeout_triggered = True
                trace.stop_reason = motivo
                break

            # Ciclo principal: Think → Act → Observe → Reflect
            thought = self._think(messages)
            trace.iterations.append({
                "iteration": i,
                "reasoning": thought.reasoning,
                "proposed_action": thought.proposed_action,
                "confidence_before": thought.confidence,
            })

            if thought.proposed_action:
                # Act: executa o tool solicitado pelo Claude
                tool_result = self._act(thought.proposed_action, **thought.action_params)
                observation = self._format_observation(tool_result)
                messages = self._append_observation(messages, thought, observation)

                # Reflect: atualiza confiança com base no resultado
                thought = self._reflect(thought, tool_result)
                trace.iterations[-1]["observation"] = observation
                trace.iterations[-1]["confidence_after"] = thought.confidence
            else:
                # Claude não propôs nenhuma ação — o reasoning atual já É o output final.
                # Não fazemos chamada extra à API: o texto retornado por _think é suficiente.
                thought.output = self._extract_json_from_text(thought.reasoning)
                thought.confidence = 1.0
                trace.stop_reason = "CONFIDENT"
                break

        trace.total_elapsed = time.time() - start

        return AgentResult(
            output=thought.output,
            stop_reason=trace.stop_reason or "MAX_ITER",
            confidence=thought.confidence,
            trace=trace,
        )

    # ── Métodos privados do loop ──────────────────────────────────────────────

    def _think(self, messages: list) -> ThoughtState:
        """
        Chama a API Claude e extrai raciocínio + intenção de ação.

        Se Claude emitir um tool_use block, o ThoughtState terá
        proposed_action preenchido. Se emitir apenas texto, o agente
        está pronto para finalizar.
        """
        tools_schema = [self._tool_to_claude_schema(t) for t in self.tool_belt.values()]

        kwargs: dict = {
            "model": self.model,
            "system": self.system_prompt,
            "messages": messages,
            "max_tokens": 2048,
        }
        if tools_schema:
            kwargs["tools"] = tools_schema

        response = self.client.messages.create(**kwargs)
        return self._parse_response(response)

    def _act(self, action_name: str, **params) -> ToolResult:
        """
        Executa o tool solicitado pelo agente.

        Se o tool não existir no Belt, retorna ToolResult de erro sem
        lançar exceção — o loop continua e o agente pode reconsiderar.
        """
        tool = self.tool_belt.get(action_name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool '{action_name}' não existe no Belt do agente '{self.agent_id}'",
            )
        return tool.execute(**params)

    def _reflect(self, thought: ThoughtState, result: ToolResult) -> ThoughtState:
        """
        Atualiza o score de confiança com base no resultado do tool.

        Sucesso: +0.2 (capped em 1.0)
        Falha: -0.1 (floored em 0.0)
        """
        if result.success:
            thought.confidence = min(thought.confidence + 0.2, 1.0)
        else:
            thought.confidence = max(thought.confidence - 0.1, 0.0)
        return thought

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _build_initial_messages(self, task: str, context: dict | None) -> list:
        """Monta a lista inicial de mensagens para a API."""
        content = task
        if context:
            context_str = json.dumps(context, ensure_ascii=False, indent=2)
            content = f"{task}\n\nContexto disponível:\n{context_str}"
        return [{"role": "user", "content": content}]

    def _tool_to_claude_schema(self, tool: Tool) -> dict:
        """Converte um Tool para o formato esperado pela API Anthropic."""
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters_schema,
        }

    def _parse_response(self, response) -> ThoughtState:
        """
        Extrai ThoughtState da resposta da API Anthropic.

        Trata dois casos:
        - tool_use block: Claude quer chamar um tool (proposed_action preenchido)
        - text block: Claude está finalizando (proposed_action = None)
        """
        reasoning_parts = []
        proposed_action = None
        action_params = {}

        for block in response.content:
            if block.type == "text":
                reasoning_parts.append(block.text)
            elif block.type == "tool_use":
                # Nota V1: se Claude emitir múltiplos tool_use blocks, usa o último.
                # Para Tool Belts pequenos (≤4 tools) isso é suficiente.
                # V2: implementar fila de tool_use se necessário.
                proposed_action = block.name
                action_params = block.input if block.input else {}

        reasoning = " ".join(reasoning_parts).strip()

        return ThoughtState(
            reasoning=reasoning,
            proposed_action=proposed_action,
            action_params=action_params,
            confidence=0.0,
        )

    def _format_observation(self, result: ToolResult) -> str:
        """Formata o resultado de um tool como string de observação."""
        if result.success:
            source_prefix = f"[{result.source}] " if result.source else ""
            data_str = json.dumps(result.data, ensure_ascii=False) if result.data is not None else "null"
            return f"{source_prefix}{data_str}"
        return f"[ERRO] {result.error}"

    def _append_observation(
        self,
        messages: list,
        thought: ThoughtState,
        observation: str,
    ) -> list:
        """
        Adiciona o par (raciocínio do agente, observação do tool) ao histórico.

        Mantém o formato alternado user/assistant exigido pela API Anthropic.
        """
        updated = list(messages)

        # Resposta do assistente com o raciocínio
        if thought.reasoning:
            updated.append({"role": "assistant", "content": thought.reasoning})

        # Observação do tool como mensagem do usuário
        updated.append({
            "role": "user",
            "content": f"Observação do tool '{thought.proposed_action}': {observation}",
        })

        return updated

    @staticmethod
    def _extract_json_from_text(text: str) -> Any:
        """
        Extrai JSON de uma string de texto.

        Tenta parsear como JSON, incluindo blocos de código markdown.
        Se não conseguir, retorna o texto bruto — o agente pode ter
        retornado prosa direta em vez de JSON estruturado.
        """
        text = text.strip()

        # Tenta extrair JSON de blocos de código markdown
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()

        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return text

    @staticmethod
    def _extract_json(response) -> Any:
        """
        Extrai JSON do último bloco de texto de uma resposta da API.
        Delega para _extract_json_from_text após extrair o texto.
        """
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
        return ReActAgent._extract_json_from_text(text)
