"""
Módulo react — ReAct Loop para os agentes da newsletter Fuja do Mico.

Exports principais:
    ReActAgent        — classe base do loop (instanciar para cada agente de linha)
    ReActStopCriteria — dataclass de parâmetros de parada
    CRITERIA          — instâncias pré-configuradas por agente_id
    Tool              — ABC que todos os tools do Belt devem implementar
    ToolResult        — resultado padronizado de qualquer tool

Gate Editorial + Agentes de Linha (Story 1.11):
    pontuar_linhas        — score 0-10 por linha via claude-haiku
    criar_agentes_linha   — instancia ReActAgent por linha ativa
    executar_agentes_linha — executa todos os agentes sequencialmente
    LIMIAR_ATIVACAO       — score mínimo para ativar uma linha (6)
    HIERARQUIA            — ordem de desempate entre linhas
    CLONE_PADRAO          — mapeamento linha_id → clone_id padrão
"""

from scripts.react.agent import AgentResult, AgentTrace, ReActAgent, ThoughtState
from scripts.react.criteria import CRITERIA, ReActStopCriteria
from scripts.react.editorial_gate import HIERARQUIA, LIMIAR_ATIVACAO, pontuar_linhas
from scripts.react.line_agents import (
    CLONE_PADRAO,
    criar_agentes_linha,
    executar_agentes_linha,
)
from scripts.react.tools import Tool, ToolResult

__all__ = [
    # Story 1.8 — ReAct Loop Foundation
    "ReActAgent",
    "ReActStopCriteria",
    "CRITERIA",
    "Tool",
    "ToolResult",
    "AgentResult",
    "AgentTrace",
    "ThoughtState",
    # Story 1.11 — Gate Editorial + Agentes de Linha
    "pontuar_linhas",
    "criar_agentes_linha",
    "executar_agentes_linha",
    "LIMIAR_ATIVACAO",
    "HIERARQUIA",
    "CLONE_PADRAO",
]
