"""
ValuationCalculatorTool — calcula preços teóricos de valuation sem APIs externas.

Implementa:
    - Preço Graham: √(22.5 × LPA × VPA)  [Benjamin Graham, Security Analysis]
    - Preço Bazin/Teto: DY_anual / 0.06   [Décio Bazin / adaptação yield mínimo 6%]

Não faz chamadas externas. Entrada: LPA, VPA, DY — todos disponíveis via Brapi/Fintz.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from scripts.react.tools import Tool, ToolResult

logger = logging.getLogger(__name__)


class ValuationCalculatorTool(Tool):
    """
    Calcula preços teóricos de valuation usando fórmulas clássicas.

    Use após BrapiQueryTool/FintzQueryTool para calcular preço justo.
    Fórmulas: Graham (√22.5×LPA×VPA) e Bazin (DY/0.06).
    Parâmetros: ticker, lpa (Lucro Por Ação), vpa (VPA), dy (DY anual em R$ por ação).
    """

    @property
    def name(self) -> str:
        return "valuation_calculator"

    @property
    def description(self) -> str:
        return (
            "Calcula preço justo teórico via fórmulas de Graham e Bazin. "
            "Graham: raiz(22.5 × LPA × VPA). Bazin/Teto: DY_anual / 0.06. "
            "Use após obter LPA, VPA e DY via brapi_query ou fintz_query. "
            "Parâmetros: ticker (string), lpa (float), vpa (float), dy (float, DY anual em R$/ação)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Código do ticker (ex: 'PETR4')",
                },
                "lpa": {
                    "type": "number",
                    "description": "Lucro Por Ação (LPA) em reais",
                },
                "vpa": {
                    "type": "number",
                    "description": "Valor Patrimonial Por Ação (VPA) em reais",
                },
                "dy": {
                    "type": "number",
                    "description": "Dividendo anual por ação em reais (não percentual)",
                },
            },
            "required": ["ticker", "lpa", "vpa", "dy"],
        }

    def execute(self, **kwargs) -> ToolResult:
        """Calcula preços Graham e Bazin para o ticker informado."""
        try:
            ticker = kwargs.get("ticker", "")
            lpa = float(kwargs.get("lpa", 0))
            vpa = float(kwargs.get("vpa", 0))
            dy = float(kwargs.get("dy", 0))

            # Preço Graham: √(22.5 × LPA × VPA)
            # Produto negativo (empresa com prejuízo ou VPA negativo) → retorna 0
            produto = 22.5 * lpa * vpa
            preco_graham = math.sqrt(produto) if produto > 0 else 0.0

            # Preço Bazin/Teto: DY_anual_em_R$ / yield_mínimo (6%)
            preco_bazin = dy / 0.06 if dy > 0 else 0.0

            resultado: Any = {
                "ticker": ticker,
                "graham": round(preco_graham, 2),
                "bazin": round(preco_bazin, 2),
                "inputs": {"lpa": lpa, "vpa": vpa, "dy": dy},
            }

            return ToolResult(success=True, data=resultado, source="calculator")

        except Exception as e:
            logger.warning("[ValuationCalculatorTool] Erro no cálculo: %s", e)
            return ToolResult(success=False, data=None, error=str(e))
