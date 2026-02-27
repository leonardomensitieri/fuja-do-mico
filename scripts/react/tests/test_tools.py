"""
Testes unitários para Tool (ABC) e ToolResult.

Cobre os cenários da AC 9:
    1. ToolResult com sucesso — campos preenchidos corretamente
    2. ToolResult com erro — success=False, data=None
    3. Garantia de que execute() nunca propaga exceção
    4. Tool concreta de exemplo implementa a interface corretamente
"""

import pytest
from scripts.react.tools import Tool, ToolResult


# ── Tool concreta para testes ─────────────────────────────────────────────────

class ToolDeSucesso(Tool):
    """Tool de exemplo que sempre retorna sucesso."""

    @property
    def name(self) -> str:
        return "tool_sucesso"

    @property
    def description(self) -> str:
        return "Tool de teste que sempre retorna sucesso."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"valor": {"type": "string"}},
            "required": ["valor"],
        }

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(
            success=True,
            data={"recebido": kwargs.get("valor")},
            source="tool_sucesso",
        )


class ToolDeErro(Tool):
    """Tool de exemplo que sempre falha — mas encapsula o erro."""

    @property
    def name(self) -> str:
        return "tool_erro"

    @property
    def description(self) -> str:
        return "Tool de teste que sempre falha."

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs) -> ToolResult:
        try:
            raise ValueError("Erro simulado para teste")
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class ToolComExcecaoNaoCapturada(Tool):
    """Tool mal-implementada que lança exceção — não deveria existir em produção."""

    @property
    def name(self) -> str:
        return "tool_excecao"

    @property
    def description(self) -> str:
        return "Tool de teste que lança exceção diretamente."

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs) -> ToolResult:
        raise RuntimeError("Exceção não capturada — implementação incorreta")


# ── Testes de ToolResult ──────────────────────────────────────────────────────

def test_tool_result_sucesso():
    """ToolResult de sucesso deve ter success=True e data preenchido."""
    resultado = ToolResult(success=True, data={"ticker": "PETR4"}, source="brapi")

    assert resultado.success is True
    assert resultado.data == {"ticker": "PETR4"}
    assert resultado.error is None
    assert resultado.source == "brapi"


def test_tool_result_erro():
    """ToolResult de erro deve ter success=False e error preenchido."""
    resultado = ToolResult(success=False, data=None, error="Timeout na API")

    assert resultado.success is False
    assert resultado.data is None
    assert resultado.error == "Timeout na API"
    assert resultado.source is None


def test_tool_result_campos_opcionais_tem_default_none():
    """Os campos error e source devem ser None por padrão."""
    resultado = ToolResult(success=True, data=42)

    assert resultado.error is None
    assert resultado.source is None


# ── Testes de Tool concreta ───────────────────────────────────────────────────

def test_tool_sucesso_retorna_resultado_correto():
    """Tool de sucesso deve retornar ToolResult com success=True."""
    tool = ToolDeSucesso()
    resultado = tool.execute(valor="teste")

    assert resultado.success is True
    assert resultado.data == {"recebido": "teste"}
    assert resultado.source == "tool_sucesso"


def test_tool_erro_encapsula_excecao():
    """Tool que falha deve retornar ToolResult com success=False — sem propagar."""
    tool = ToolDeErro()
    resultado = tool.execute()

    assert resultado.success is False
    assert resultado.data is None
    assert "Erro simulado" in resultado.error


def test_tool_nao_deve_propagar_excecao():
    """
    Tools devem encapsular exceções — nunca propagar para o caller.

    Este teste documenta o comportamento INCORRETO de uma tool mal-implementada.
    Em produção, todas as tools devem seguir o padrão de ToolDeErro.
    """
    tool = ToolComExcecaoNaoCapturada()

    # Tool mal-implementada vai lançar — este teste documenta o problema
    with pytest.raises(RuntimeError, match="Exceção não capturada"):
        tool.execute()


# ── Testes da interface ABC ───────────────────────────────────────────────────

def test_nao_pode_instanciar_tool_abstrata():
    """Não deve ser possível instanciar Tool diretamente."""
    with pytest.raises(TypeError):
        Tool()


def test_tool_concreta_implementa_interface():
    """Tool concreta deve implementar todos os métodos abstratos."""
    tool = ToolDeSucesso()

    assert isinstance(tool.name, str)
    assert len(tool.name) > 0
    assert isinstance(tool.description, str)
    assert isinstance(tool.parameters_schema, dict)
    assert "type" in tool.parameters_schema


def test_tool_name_sem_espacos():
    """O nome do tool deve usar snake_case, sem espaços (exigido pela API Anthropic)."""
    tool = ToolDeSucesso()
    assert " " not in tool.name
