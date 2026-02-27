"""
Tool Belt — tools concretos para os agentes ReAct da newsletter Fuja do Mico.

Cada tool implementa a interface Tool (ABC) de scripts.react.tools.
O método execute() NUNCA propaga exceção — erros são encapsulados em ToolResult.

Mapeamento por linha editorial (dossiê seção 6.1):
    linha_1 (Análise Financeira): BrapiQueryTool, FintzQueryTool, ValuationCalculatorTool, CalculatorTool
    linha_2 (Notícia de Mercado): WebSearchTool, RssFetchTool
    linha_3 (Mentalidade):        WebSearchTool, HumanFeedbackTool
    linha_4 (Macro e Cenário):    WebSearchTool, FintzQueryTool, CalculatorTool
    linha_5 (Erros e Armadilhas): WebSearchTool, BrapiQueryTool
    linha_6 (Narrativa):          WebSearchTool, HumanFeedbackTool
"""

from scripts.react.belt.brapi_query import BrapiQueryTool
from scripts.react.belt.calculator import CalculatorTool
from scripts.react.belt.fintz_query import FintzQueryTool
from scripts.react.belt.human_feedback import HumanFeedbackTool
from scripts.react.belt.rss_fetch import RssFetchTool
from scripts.react.belt.valuation_calculator import ValuationCalculatorTool
from scripts.react.belt.web_search import WebSearchTool

__all__ = [
    "BrapiQueryTool",
    "FintzQueryTool",
    "ValuationCalculatorTool",
    "CalculatorTool",
    "WebSearchTool",
    "RssFetchTool",
    "HumanFeedbackTool",
]
