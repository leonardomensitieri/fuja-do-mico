"""
CalculatorTool — avaliador seguro de expressões matemáticas.

Usa AST visitor com whitelist estrita de operadores e funções.
NUNCA usa eval() diretamente — proteção contra injeção de código.
Qualquer token fora da whitelist resulta em ToolResult de erro.
"""

from __future__ import annotations

import ast
import logging
import math
import operator
from typing import Any, Union

from scripts.react.tools import Tool, ToolResult

logger = logging.getLogger(__name__)

# Operadores permitidos — whitelist estrita
_OPERADORES: dict = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Funções matemáticas permitidas — whitelist estrita
_FUNCOES: dict = {
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "pow": pow,
    "floor": math.floor,
    "ceil": math.ceil,
}


class _AvaliadorSeguro(ast.NodeVisitor):
    """
    Visitor AST que avalia expressões matemáticas com whitelist estrita.
    Rejeita qualquer nó fora da whitelist — incluindo imports, atributos e chamadas não-whitelisted.
    """

    def visit_Constant(self, node: ast.Constant) -> Union[int, float]:
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Tipo de constante não permitido: {type(node.value).__name__}")

    # Compatibilidade Python 3.7
    def visit_Num(self, node: ast.Num) -> Union[int, float]:
        return node.n

    def visit_BinOp(self, node: ast.BinOp) -> float:
        op_tipo = type(node.op)
        if op_tipo not in _OPERADORES:
            raise ValueError(f"Operador binário não permitido: {op_tipo.__name__}")
        esquerda = self.visit(node.left)
        direita = self.visit(node.right)
        return _OPERADORES[op_tipo](esquerda, direita)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        op_tipo = type(node.op)
        if op_tipo not in _OPERADORES:
            raise ValueError(f"Operador unário não permitido: {op_tipo.__name__}")
        return _OPERADORES[op_tipo](self.visit(node.operand))

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Apenas chamadas de função simples são permitidas (sem métodos).")
        nome = node.func.id
        if nome not in _FUNCOES:
            raise ValueError(f"Função não permitida: '{nome}'. Permitidas: {sorted(_FUNCOES)}")
        argumentos = [self.visit(arg) for arg in node.args]
        return _FUNCOES[nome](*argumentos)

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"Construção não permitida na expressão: {type(node).__name__}")


def _avaliar_formula(formula: str) -> Any:
    """Avalia a fórmula matematicamente de forma segura via AST."""
    try:
        arvore = ast.parse(formula.strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Sintaxe inválida: {e}")
    return _AvaliadorSeguro().visit(arvore)


class CalculatorTool(Tool):
    """
    Avalia expressões matemáticas de forma segura via AST com whitelist estrita.

    Use para cálculos financeiros (CAGR, yields, variações percentuais, etc.).
    Operadores: +, -, *, /, **, %. Funções: sqrt, log, log10, abs, round, pow, floor, ceil.
    NUNCA usa eval() — seguro contra injeção.
    Parâmetro: formula (string com expressão matemática).
    """

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return (
            "Avalia expressões matemáticas de forma segura. "
            "Operadores: +, -, *, /, **, %. "
            "Funções: sqrt, log, log10, abs, round, pow, floor, ceil. "
            "Exemplos: '(100 + 50) * 0.15', 'sqrt(22.5 * 2.5 * 18)', 'round(150 / 1.06, 2)'. "
            "Parâmetro: formula (string)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "formula": {
                    "type": "string",
                    "description": "Expressão matemática segura (ex: 'sqrt(22.5 * 2.5 * 18)')",
                }
            },
            "required": ["formula"],
        }

    def execute(self, **kwargs) -> ToolResult:
        """Avalia a expressão matemática de forma segura."""
        try:
            formula = kwargs.get("formula", "").strip()
            if not formula:
                return ToolResult(success=False, data=None, error="Parâmetro 'formula' é obrigatório.")

            resultado = _avaliar_formula(formula)
            return ToolResult(
                success=True,
                data={"formula": formula, "resultado": resultado},
                source="calculator",
            )

        except ValueError as e:
            return ToolResult(success=False, data=None, error=str(e))
        except Exception as e:
            logger.warning("[CalculatorTool] Erro inesperado: %s", e)
            return ToolResult(success=False, data=None, error=f"Erro ao avaliar fórmula: {e}")
