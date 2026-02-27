"""
Testes unitários para os agentes de linha (line_agents.py).

Mock puro — sem chamadas reais ao Claude API nem ao catálogo de clones.
Cobre os cenários da AC 12:
    1. criar_agentes_linha() com todos scores < 6 → dict vazio + warning
    2. criar_agentes_linha() com 2 linhas ativas → 2 ReActAgent com agent_id correto
    3. tool belt correto por linha (verificado por tipo de classe)
    4. executar_agentes_linha() chama agent.run() e retorna AgentResult por linha
    5. Clone inexistente → fallback para contextual_l2
    6. clone_override permite sobrepor o clone padrão
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scripts.react.belt import (
    BrapiQueryTool,
    CalculatorTool,
    FintzQueryTool,
    HumanFeedbackTool,
    RssFetchTool,
    ValuationCalculatorTool,
    WebSearchTool,
)
from scripts.react.editorial_gate import LIMIAR_ATIVACAO
from scripts.react.line_agents import (
    CLONE_PADRAO,
    criar_agentes_linha,
    executar_agentes_linha,
    _criar_tool_belt,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

_SCORES_NENHUM_ATIVO = {
    "linha_1": 0, "linha_2": 0, "linha_3": 0,
    "linha_4": 0, "linha_5": 0, "linha_6": 0,
}

_SCORES_DOIS_ATIVOS = {
    "linha_1": 8, "linha_2": 7, "linha_3": 3,
    "linha_4": 5, "linha_5": 2, "linha_6": 1,
}

_SCORES_TODOS_ATIVOS = {
    "linha_1": 9, "linha_2": 8, "linha_3": 7,
    "linha_4": 8, "linha_5": 7, "linha_6": 6,
}

_CONTEXTO = {"task": "Gere conteúdo sobre PETR4 e dividendos extraordinários."}


# ── Helpers de mock ───────────────────────────────────────────────────────────

def _patch_load_clone(return_value: str = "Você é um analista financeiro."):
    """Patch para load_clone_prompt retornar string fixa."""
    return patch(
        "scripts.react.line_agents.load_clone_prompt",
        return_value=return_value,
    )


def _patch_react_agent():
    """Patch para ReActAgent — evita chamadas reais ao Claude."""
    return patch("scripts.react.line_agents.ReActAgent")


# ── Testes de criar_agentes_linha ─────────────────────────────────────────────

class TestCriarAgentesLinha:

    def test_todos_scores_abaixo_do_limiar_retorna_vazio(self, caplog):
        """Quando nenhum score >= LIMIAR_ATIVACAO, retorna dict vazio."""
        with _patch_load_clone(), _patch_react_agent():
            agentes = criar_agentes_linha(_SCORES_NENHUM_ATIVO, _CONTEXTO)

        assert agentes == {}

    def test_todos_scores_abaixo_do_limiar_emite_warning(self, caplog):
        """Warning deve ser emitido quando nenhuma linha é ativada."""
        import logging
        with _patch_load_clone(), _patch_react_agent():
            with caplog.at_level(logging.WARNING, logger="scripts.react.line_agents"):
                criar_agentes_linha(_SCORES_NENHUM_ATIVO, _CONTEXTO)

        assert any("nenhuma linha ativada" in msg for msg in caplog.messages)

    def test_duas_linhas_ativas_retorna_dois_agentes(self):
        """Com 2 linhas com score >= 6, deve retornar 2 agentes."""
        with _patch_load_clone(), _patch_react_agent() as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock()
            agentes = criar_agentes_linha(_SCORES_DOIS_ATIVOS, _CONTEXTO)

        assert len(agentes) == 2
        assert "linha_1" in agentes
        assert "linha_2" in agentes
        assert "linha_3" not in agentes

    def test_agent_id_correto_por_linha(self):
        """Cada agente deve ter agent_id igual à sua linha."""
        with _patch_load_clone(), _patch_react_agent() as mock_agent_cls:
            mock_agent_cls.side_effect = lambda **kw: MagicMock(agent_id=kw.get("agent_id"))
            agentes = criar_agentes_linha(_SCORES_DOIS_ATIVOS, _CONTEXTO)

        # Verificar que ReActAgent foi chamado com agent_id correto
        chamadas = mock_agent_cls.call_args_list
        agent_ids_usados = {c.kwargs.get("agent_id") for c in chamadas}
        assert "linha_1" in agent_ids_usados
        assert "linha_2" in agent_ids_usados

    def test_score_exatamente_no_limiar_ativa_linha(self):
        """Score == LIMIAR_ATIVACAO (6) deve ativar a linha."""
        scores_limiar = {
            "linha_1": 6, "linha_2": 5, "linha_3": 5,
            "linha_4": 5, "linha_5": 5, "linha_6": 5,
        }
        with _patch_load_clone(), _patch_react_agent() as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock()
            agentes = criar_agentes_linha(scores_limiar, _CONTEXTO)

        assert len(agentes) == 1
        assert "linha_1" in agentes

    def test_score_abaixo_do_limiar_nao_ativa(self):
        """Score == LIMIAR_ATIVACAO - 1 (5) NÃO deve ativar a linha."""
        scores_abaixo = {
            "linha_1": 5, "linha_2": 0, "linha_3": 0,
            "linha_4": 0, "linha_5": 0, "linha_6": 0,
        }
        with _patch_load_clone(), _patch_react_agent():
            agentes = criar_agentes_linha(scores_abaixo, _CONTEXTO)

        assert agentes == {}

    def test_clone_override_e_respeitado(self):
        """clone_override deve substituir o clone padrão da linha."""
        with _patch_load_clone() as mock_load, _patch_react_agent() as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock()
            criar_agentes_linha(
                _SCORES_DOIS_ATIVOS,
                _CONTEXTO,
                clone_override={"linha_1": "buffett"},
            )

        # Verificar que load_clone_prompt foi chamado com "buffett" em vez de "graham"
        calls_args = [call.args[0] for call in mock_load.call_args_list]
        assert "buffett" in calls_args

    def test_clone_inexistente_usa_fallback_contextual_l2(self):
        """Quando load_clone_prompt lança FileNotFoundError, usa contextual_l2."""
        call_count = {"n": 0}

        def load_com_erro(clone_id: str) -> str:
            call_count["n"] += 1
            if clone_id == "graham":
                raise FileNotFoundError(f"Clone 'graham' não encontrado.")
            return f"Prompt do {clone_id}"

        with patch("scripts.react.line_agents.load_clone_prompt", side_effect=load_com_erro):
            with _patch_react_agent() as mock_agent_cls:
                mock_agent_cls.return_value = MagicMock()
                scores_linha1 = {
                    "linha_1": 8, "linha_2": 0, "linha_3": 0,
                    "linha_4": 0, "linha_5": 0, "linha_6": 0,
                }
                agentes = criar_agentes_linha(scores_linha1, _CONTEXTO)

        # Deve ter sido chamado 2x: 1x "graham" (erro) + 1x "contextual_l2" (fallback)
        assert call_count["n"] == 2
        assert len(agentes) == 1  # agente criado mesmo com fallback

    def test_model_sonnet_e_usado_para_agentes_de_linha(self):
        """Todos os agentes de linha devem usar claude-sonnet-4-6."""
        with _patch_load_clone(), _patch_react_agent() as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock()
            criar_agentes_linha(_SCORES_TODOS_ATIVOS, _CONTEXTO)

        for chamada in mock_agent_cls.call_args_list:
            model = chamada.kwargs.get("model")
            assert model == "claude-sonnet-4-6", (
                f"Agente de linha deve usar claude-sonnet-4-6, got {model}"
            )


# ── Testes do tool belt por linha ─────────────────────────────────────────────

class TestToolBeltPorLinha:

    def test_linha_1_tem_4_tools(self):
        """Linha 1 deve ter 4 tools: Brapi, Fintz, Valuation, Calculator."""
        belt = _criar_tool_belt("linha_1")
        assert len(belt) == 4

    def test_linha_1_tipos_corretos(self):
        """Linha 1 deve ter BrapiQueryTool, FintzQueryTool, ValuationCalculatorTool, CalculatorTool."""
        belt = _criar_tool_belt("linha_1")
        tipos = {type(t) for t in belt}
        assert BrapiQueryTool in tipos
        assert FintzQueryTool in tipos
        assert ValuationCalculatorTool in tipos
        assert CalculatorTool in tipos

    def test_linha_2_tem_2_tools(self):
        """Linha 2 deve ter 2 tools: WebSearch e RssFetch."""
        belt = _criar_tool_belt("linha_2")
        assert len(belt) == 2
        tipos = {type(t) for t in belt}
        assert WebSearchTool in tipos
        assert RssFetchTool in tipos

    def test_linha_3_tem_2_tools(self):
        """Linha 3 deve ter 2 tools: WebSearch e HumanFeedback."""
        belt = _criar_tool_belt("linha_3")
        assert len(belt) == 2
        tipos = {type(t) for t in belt}
        assert WebSearchTool in tipos
        assert HumanFeedbackTool in tipos

    def test_linha_4_tem_3_tools(self):
        """Linha 4 deve ter 3 tools: WebSearch, Fintz, Calculator."""
        belt = _criar_tool_belt("linha_4")
        assert len(belt) == 3
        tipos = {type(t) for t in belt}
        assert WebSearchTool in tipos
        assert FintzQueryTool in tipos
        assert CalculatorTool in tipos

    def test_linha_5_tem_2_tools(self):
        """Linha 5 deve ter 2 tools: WebSearch e Brapi."""
        belt = _criar_tool_belt("linha_5")
        assert len(belt) == 2
        tipos = {type(t) for t in belt}
        assert WebSearchTool in tipos
        assert BrapiQueryTool in tipos

    def test_linha_6_tem_2_tools(self):
        """Linha 6 deve ter 2 tools: WebSearch e HumanFeedback."""
        belt = _criar_tool_belt("linha_6")
        assert len(belt) == 2
        tipos = {type(t) for t in belt}
        assert WebSearchTool in tipos
        assert HumanFeedbackTool in tipos

    def test_linha_inexistente_retorna_lista_vazia(self):
        """Linha não mapeada deve retornar lista vazia sem crash."""
        belt = _criar_tool_belt("linha_99")
        assert belt == []

    def test_cada_chamada_retorna_novas_instancias(self):
        """Chamadas distintas a _criar_tool_belt devem retornar instâncias diferentes."""
        belt1 = _criar_tool_belt("linha_2")
        belt2 = _criar_tool_belt("linha_2")
        assert belt1[0] is not belt2[0]  # instâncias diferentes


# ── Testes de executar_agentes_linha ─────────────────────────────────────────

class TestExecutarAgentesLinha:

    def _criar_mock_agente(self, agent_id: str, output: str = "Análise gerada.") -> MagicMock:
        """Cria mock de ReActAgent com run() retornando AgentResult simulado."""
        agente = MagicMock()
        agente.agent_id = agent_id
        resultado = MagicMock()
        resultado.output = output
        resultado.stop_reason = "CONFIDENT"
        resultado.confidence = 0.85
        agente.run.return_value = resultado
        return agente

    def test_executa_run_para_cada_agente(self):
        """executar_agentes_linha deve chamar run() de cada agente."""
        agentes = {
            "linha_1": self._criar_mock_agente("linha_1"),
            "linha_2": self._criar_mock_agente("linha_2"),
        }

        resultados = executar_agentes_linha(agentes, _CONTEXTO)

        agentes["linha_1"].run.assert_called_once()
        agentes["linha_2"].run.assert_called_once()

    def test_retorna_resultado_por_linha(self):
        """executar_agentes_linha deve retornar dict {linha_id: AgentResult}."""
        agentes = {
            "linha_1": self._criar_mock_agente("linha_1", "Análise do Graham"),
            "linha_3": self._criar_mock_agente("linha_3", "Lição do Housel"),
        }

        resultados = executar_agentes_linha(agentes, _CONTEXTO)

        assert "linha_1" in resultados
        assert "linha_3" in resultados
        assert resultados["linha_1"].output == "Análise do Graham"
        assert resultados["linha_3"].output == "Lição do Housel"

    def test_task_especifica_por_linha_e_usada(self):
        """Se contexto contém task_linha_X, essa task deve ser passada ao agente."""
        contexto_com_task = {
            "task": "Tarefa genérica",
            "task_linha_1": "Analise PETR4 com foco em dividendos",
        }
        agente = self._criar_mock_agente("linha_1")
        agentes = {"linha_1": agente}

        executar_agentes_linha(agentes, contexto_com_task)

        task_usada = agente.run.call_args.kwargs.get("task") or agente.run.call_args.args[0]
        assert task_usada == "Analise PETR4 com foco em dividendos"

    def test_task_generica_como_fallback(self):
        """Se contexto não tem task_linha_X, deve usar 'task' genérica como fallback."""
        contexto_generico = {"task": "Gere conteúdo sobre Selic e inflação."}
        agente = self._criar_mock_agente("linha_4")
        agentes = {"linha_4": agente}

        executar_agentes_linha(agentes, contexto_generico)

        task_usada = agente.run.call_args.kwargs.get("task") or agente.run.call_args.args[0]
        assert task_usada == "Gere conteúdo sobre Selic e inflação."

    def test_dict_vazio_retorna_vazio_sem_crash(self):
        """executar_agentes_linha com dict vazio deve retornar dict vazio."""
        resultados = executar_agentes_linha({}, _CONTEXTO)
        assert resultados == {}


# ── Testes das constantes ─────────────────────────────────────────────────────

class TestConstantes:

    def test_clone_padrao_tem_6_linhas(self):
        """CLONE_PADRAO deve ter mapeamento para as 6 linhas."""
        assert len(CLONE_PADRAO) == 6
        linhas_esperadas = {"linha_1", "linha_2", "linha_3", "linha_4", "linha_5", "linha_6"}
        assert set(CLONE_PADRAO.keys()) == linhas_esperadas

    def test_clone_padrao_valores_corretos(self):
        """CLONE_PADRAO deve mapear cada linha para o clone padrão do dossiê."""
        assert CLONE_PADRAO["linha_1"] == "graham"
        assert CLONE_PADRAO["linha_2"] == "contextual_l1"
        assert CLONE_PADRAO["linha_3"] == "housel"
        assert CLONE_PADRAO["linha_4"] == "dalio"
        assert CLONE_PADRAO["linha_5"] == "munger"
        assert CLONE_PADRAO["linha_6"] == "brunson"
