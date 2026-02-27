"""
Instanciação dos 6 agentes de linha da newsletter Fuja do Mico.

Cada agente de linha é um ReActAgent configurado com:
- system_prompt: carregado do catálogo de clones via load_clone_prompt()
- criteria: critérios de parada específicos da linha (de CRITERIA)
- tool_belt: conjunto de tools específico da linha
- model: claude-sonnet-4-6 (dossiê seção 6.2: Sonnet para todos os agentes de linha)

Padrão de uso:
    scores = pontuar_linhas(conteudo_coletado)
    agentes = criar_agentes_linha(scores, contexto)
    resultados = executar_agentes_linha(agentes, contexto)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from scripts.clones.loader import load_clone_prompt
from scripts.react.agent import AgentResult, ReActAgent
from scripts.react.criteria import CRITERIA
from scripts.react.editorial_gate import LIMIAR_ATIVACAO
from scripts.react.belt import (
    BrapiQueryTool,
    CalculatorTool,
    FintzQueryTool,
    HumanFeedbackTool,
    RssFetchTool,
    ValuationCalculatorTool,
    WebSearchTool,
)

logger = logging.getLogger(__name__)

# Modelo Sonnet para agentes de linha — dossiê seção 6.2
_MODELO_LINHA = "claude-sonnet-4-6"

# Clone padrão por linha (AC 4)
# Outros clones por linha conforme dossiê seção 5.1:
# linha_1: graham | buffett | barsi | damodaran
# linha_3: munger | housel | taleb | cialdini
# linha_4: dalio | soros | keynes
# linha_5: munger | taleb
# linha_6: brunson | holiday
CLONE_PADRAO: Dict[str, str] = {
    "linha_1": "graham",
    "linha_2": "contextual_l1",
    "linha_3": "housel",
    "linha_4": "dalio",
    "linha_5": "munger",
    "linha_6": "brunson",
}

# Clone de fallback quando o clone solicitado não é encontrado
_CLONE_FALLBACK = "contextual_l2"


def _criar_tool_belt(linha_id: str) -> list:
    """
    Retorna uma nova instância do tool belt para a linha informada.

    Mapeamento por linha (dossiê seção 6.3 a 6.8):
        linha_1: BrapiQueryTool, FintzQueryTool, ValuationCalculatorTool, CalculatorTool
        linha_2: WebSearchTool, RssFetchTool
        linha_3: WebSearchTool, HumanFeedbackTool
        linha_4: WebSearchTool, FintzQueryTool, CalculatorTool
        linha_5: WebSearchTool, BrapiQueryTool
        linha_6: WebSearchTool, HumanFeedbackTool
    """
    belts: Dict[str, list] = {
        "linha_1": [
            BrapiQueryTool(),
            FintzQueryTool(),
            ValuationCalculatorTool(),
            CalculatorTool(),
        ],
        "linha_2": [
            WebSearchTool(),
            RssFetchTool(),
        ],
        "linha_3": [
            WebSearchTool(),
            HumanFeedbackTool(),
        ],
        "linha_4": [
            WebSearchTool(),
            FintzQueryTool(),
            CalculatorTool(),
        ],
        "linha_5": [
            WebSearchTool(),
            BrapiQueryTool(),
        ],
        "linha_6": [
            WebSearchTool(),
            HumanFeedbackTool(),
        ],
    }
    return belts.get(linha_id, [])


def _carregar_system_prompt(clone_id: str, linha_id: str) -> str:
    """
    Carrega o system_prompt do clone. Em caso de falha, usa o fallback contextual_l2.
    """
    try:
        return load_clone_prompt(clone_id)
    except (FileNotFoundError, ValueError) as exc:
        logger.error(
            "Linha %s: falha ao carregar clone '%s': %s. Usando fallback '%s'.",
            linha_id,
            clone_id,
            exc,
            _CLONE_FALLBACK,
        )
        return load_clone_prompt(_CLONE_FALLBACK)


def criar_agentes_linha(
    scores: Dict[str, int],
    contexto: dict,
    clone_override: Optional[Dict[str, str]] = None,
) -> Dict[str, ReActAgent]:
    """
    Para cada linha com score >= LIMIAR_ATIVACAO, instancia um ReActAgent
    com system_prompt do clone correto e tool belt da linha.

    Args:
        scores: dict {linha_id: score} retornado por pontuar_linhas()
        contexto: contexto da edição (não usado internamente — passado para referência futura)
        clone_override: opcional — sobrepõe o clone padrão por linha
                        Ex: {"linha_1": "buffett"} força Buffett na Linha 1 desta edição

    Returns:
        dict {linha_id: ReActAgent} — apenas linhas ativas (score >= LIMIAR_ATIVACAO).
        Retorna dict vazio e emite warning se nenhuma linha ativar.
    """
    overrides = clone_override or {}

    linhas_ativas = [
        linha for linha, score in scores.items()
        if score >= LIMIAR_ATIVACAO
    ]

    if not linhas_ativas:
        logger.warning(
            "Gate editorial: nenhuma linha ativada (limiar=%d). Scores: %s",
            LIMIAR_ATIVACAO,
            scores,
        )
        return {}

    agentes: Dict[str, ReActAgent] = {}

    for linha_id in linhas_ativas:
        clone_id = overrides.get(linha_id, CLONE_PADRAO.get(linha_id, _CLONE_FALLBACK))
        system_prompt = _carregar_system_prompt(clone_id, linha_id)
        criteria = CRITERIA.get(linha_id)
        tool_belt = _criar_tool_belt(linha_id)

        agentes[linha_id] = ReActAgent(
            agent_id=linha_id,
            system_prompt=system_prompt,
            criteria=criteria,
            tool_belt=tool_belt,
            model=_MODELO_LINHA,
        )

        logger.info(
            "Agente linha %s criado (score=%d, clone=%s, tools=%d, model=%s).",
            linha_id,
            scores[linha_id],
            clone_id,
            len(tool_belt),
            _MODELO_LINHA,
        )

    return agentes


def executar_agentes_linha(
    agentes: Dict[str, ReActAgent],
    contexto: dict,
) -> Dict[str, AgentResult]:
    """
    Executa run() para cada agente de linha ativo.
    Execução sequencial na V1 (V2 poderá paralelizar via threading/asyncio).

    Args:
        agentes: dict {linha_id: ReActAgent} retornado por criar_agentes_linha()
        contexto: contexto da edição — pode conter chave "task_{linha_id}" para
                  personalizar a tarefa por linha, ou "task" como fallback genérico

    Returns:
        dict {linha_id: AgentResult}
    """
    resultados: Dict[str, AgentResult] = {}

    for linha_id, agente in agentes.items():
        # Permite tarefa específica por linha; fallback para tarefa genérica
        task = contexto.get(
            f"task_{linha_id}",
            contexto.get("task", "Gere conteúdo para a newsletter Fuja do Mico."),
        )

        logger.info("Executando agente %s — task: %.80s...", linha_id, task)
        resultados[linha_id] = agente.run(task=task, context=contexto)
        logger.info(
            "Agente %s concluído — stop_reason=%s, confidence=%.2f.",
            linha_id,
            resultados[linha_id].stop_reason,
            resultados[linha_id].confidence,
        )

    return resultados
