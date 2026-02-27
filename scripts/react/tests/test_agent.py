"""
Testes unitários para ReActAgent.

Todos os cenários usam mock do cliente Anthropic — sem chamada real à API.
Cobre os 3 cenários da AC 10:
    1. Loop completa por CONFIDENT (tool call retorna bem, confiança sobe)
    2. Loop completa por MAX_ITER (confiança nunca atinge threshold)
    3. Loop completa por TIMEOUT (tempo de parede excedido)
"""

from unittest.mock import MagicMock, patch

import pytest

from scripts.react.agent import AgentResult, ReActAgent
from scripts.react.criteria import ReActStopCriteria
from scripts.react.tools import Tool, ToolResult


# ── Fixtures e helpers ────────────────────────────────────────────────────────

@pytest.fixture
def criterio_teste():
    """Critério com valores baixos para facilitar testes."""
    return ReActStopCriteria(
        max_iterations=3,
        confidence_threshold=0.60,
        min_iterations=1,
        timeout_seconds=30,
        agent_id="teste",
    )


@pytest.fixture
def tool_mock():
    """Tool que sempre retorna sucesso."""
    tool = MagicMock(spec=Tool)
    tool.name = "tool_mock"
    tool.description = "Tool mock para testes"
    tool.parameters_schema = {"type": "object", "properties": {}}
    tool.execute.return_value = ToolResult(
        success=True,
        data={"resultado": "ok"},
        source="mock",
    )
    return tool


def _criar_resposta_com_tool_use(tool_name: str = "tool_mock") -> MagicMock:
    """Cria mock de resposta da API com tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = {}

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Vou chamar o tool para obter os dados."

    response = MagicMock()
    response.content = [text_block, block]
    return response


def _criar_resposta_texto(texto: str = '{"resultado": "análise completa"}') -> MagicMock:
    """Cria mock de resposta da API com apenas texto (finalização)."""
    block = MagicMock()
    block.type = "text"
    block.text = texto

    response = MagicMock()
    response.content = [block]
    return response


# ── Cenário 1: Loop completa por CONFIDENT ────────────────────────────────────

def test_loop_para_por_confident(criterio_teste, tool_mock):
    """
    Quando o tool retorna sucesso, a confiança sobe. Na iteração seguinte,
    Claude retorna texto sem tool_use — o agente finaliza com CONFIDENT.

    Fluxo de chamadas à API:
    1. _think() → tool_use ("tool_mock") — Claude quer dados
    2. _think() → texto puro — Claude finalizou, output extraído diretamente
    """
    with patch("scripts.react.agent.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_client.messages.create.side_effect = [
            _criar_resposta_com_tool_use("tool_mock"),              # Think iter 0: chama tool
            _criar_resposta_texto('{"analise": "PETR4 está barata"}'),  # Think iter 1: finaliza
        ]

        agente = ReActAgent(
            agent_id="teste",
            system_prompt="Você é um analista de ações.",
            criteria=criterio_teste,
            tool_belt=[tool_mock],
        )

        resultado = agente.run(task="Analise PETR4")

    assert isinstance(resultado, AgentResult)
    assert resultado.stop_reason == "CONFIDENT"
    assert resultado.confidence > 0
    assert resultado.output is not None


# ── Cenário 2: Loop completa por MAX_ITER ─────────────────────────────────────

def test_loop_para_por_max_iter(criterio_teste):
    """
    Quando o tool sempre falha, a confiança nunca sobe e o loop
    deve parar por MAX_ITER após esgotar as iterações.
    """
    tool_falho = MagicMock(spec=Tool)
    tool_falho.name = "tool_falho"
    tool_falho.description = "Tool que sempre falha"
    tool_falho.parameters_schema = {"type": "object", "properties": {}}
    tool_falho.execute.return_value = ToolResult(
        success=False,
        data=None,
        error="API indisponível",
    )

    with patch("scripts.react.agent.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Sempre propõe usar o tool (nunca finaliza por conta própria)
        mock_client.messages.create.return_value = _criar_resposta_com_tool_use("tool_falho")

        agente = ReActAgent(
            agent_id="teste",
            system_prompt="Você é um analista.",
            criteria=criterio_teste,
            tool_belt=[tool_falho],
        )

        resultado = agente.run(task="Analise algo")

    assert resultado.stop_reason == "MAX_ITER"
    assert resultado.confidence < criterio_teste.confidence_threshold
    assert len(resultado.trace.iterations) > 0


# ── Cenário 3: Loop completa por TIMEOUT ──────────────────────────────────────

def test_loop_para_por_timeout(caplog):
    """
    Quando o tempo de parede excede timeout_seconds, o loop deve
    parar com TIMEOUT e emitir um log de warning.
    """
    criterio_timeout = ReActStopCriteria(
        max_iterations=10,
        confidence_threshold=0.99,
        min_iterations=0,
        timeout_seconds=0,   # timeout imediato — qualquer elapsed já excede
        agent_id="teste_timeout",
    )

    tool_lento = MagicMock(spec=Tool)
    tool_lento.name = "tool_lento"
    tool_lento.description = "Tool lento"
    tool_lento.parameters_schema = {"type": "object", "properties": {}}
    tool_lento.execute.return_value = ToolResult(success=True, data="ok")

    with patch("scripts.react.agent.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.return_value = _criar_resposta_com_tool_use("tool_lento")

        agente = ReActAgent(
            agent_id="teste_timeout",
            system_prompt="Você é um analista.",
            criteria=criterio_timeout,
            tool_belt=[tool_lento],
        )

        import logging
        with caplog.at_level(logging.WARNING, logger="scripts.react.agent"):
            resultado = agente.run(task="Analise algo")

    assert resultado.stop_reason == "TIMEOUT"
    assert resultado.trace.timeout_triggered is True
    assert "TIMEOUT" in caplog.text
    assert "teste_timeout" in caplog.text


# ── Testes auxiliares ─────────────────────────────────────────────────────────

def test_tool_inexistente_retorna_tool_result_erro(criterio_teste):
    """
    Quando Claude propõe um tool que não existe no Belt,
    o agente registra o erro e continua. Na iteração seguinte,
    Claude finaliza com texto puro — sem lançar exceção.

    Fluxo:
    1. _think() → tool_use("tool_inexistente") — Belt vazio → ToolResult erro
    2. _think() → texto puro — Claude finaliza
    """
    with patch("scripts.react.agent.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_client.messages.create.side_effect = [
            _criar_resposta_com_tool_use("tool_inexistente"),  # iter 0: tool não existe
            _criar_resposta_texto('{"resultado": "ok"}'),      # iter 1: Claude finaliza
        ]

        agente = ReActAgent(
            agent_id="teste",
            system_prompt="Analista",
            criteria=criterio_teste,
            tool_belt=[],   # Belt vazio — nenhum tool disponível
        )

        # Não deve lançar exceção
        resultado = agente.run(task="Tarefa qualquer")

    assert isinstance(resultado, AgentResult)


def test_trace_registra_iteracoes(criterio_teste, tool_mock):
    """O AgentTrace deve registrar o histórico de iterações."""
    with patch("scripts.react.agent.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # iter 0: tool_use → iter 1: texto puro (finaliza)
        mock_client.messages.create.side_effect = [
            _criar_resposta_com_tool_use("tool_mock"),
            _criar_resposta_texto('{"analise": "ok"}'),
        ]

        agente = ReActAgent(
            agent_id="teste",
            system_prompt="Analista",
            criteria=criterio_teste,
            tool_belt=[tool_mock],
        )

        resultado = agente.run(task="Tarefa")

    assert len(resultado.trace.iterations) >= 1
    assert resultado.trace.total_elapsed >= 0
    assert resultado.trace.agent_id == "teste"


def test_context_e_passado_corretamente():
    """O contexto adicional deve ser incluído na primeira mensagem enviada à API."""
    with patch("scripts.react.agent.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        # Resposta de finalização imediata (sem tool_use)
        mock_client.messages.create.return_value = _criar_resposta_texto('{"ok": true}')

        # min_iterations=1 garante que pelo menos uma chamada à API aconteça
        criterio = ReActStopCriteria(
            max_iterations=3,
            confidence_threshold=0.0,   # para assim que min_iterations for satisfeito
            min_iterations=1,
            timeout_seconds=30,
            agent_id="teste_ctx",
        )

        agente = ReActAgent(
            agent_id="teste_ctx",
            system_prompt="Analista",
            criteria=criterio,
            tool_belt=[],
        )

        contexto = {"tickers": ["PETR4"], "clone": "graham"}
        agente.run(task="Analise", context=contexto)

    # Deve ter feito ao menos uma chamada à API
    assert mock_client.messages.create.called

    # Verifica que a primeira mensagem contém o contexto serializado
    primeira_chamada = mock_client.messages.create.call_args_list[0]
    messages = primeira_chamada.kwargs.get("messages", [])
    conteudo_inicial = messages[0]["content"] if messages else ""
    assert "PETR4" in conteudo_inicial
    assert "graham" in conteudo_inicial
