"""
Interface base para todos os tools do Belt dos agentes ReAct.

Decision tree: Worker Script — define contrato de interface sem I/O externo.
Todo tool concreto implementa esta ABC. A regra fundamental é que execute()
NUNCA propaga exceção para o caller — erros são encapsulados no ToolResult.
Isso garante que uma falha de API externa não derruba o loop inteiro.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    """
    Resultado padronizado de qualquer tool do Belt.

    O campo success indica se o tool completou sua tarefa com êxito.
    Em caso de falha, error contém a mensagem e data é None.
    O campo source identifica a origem do dado para rastreabilidade
    (ex: "brapi", "fintz", "web_search") — útil para o agente
    citar a fonte no conteúdo gerado.
    """

    success: bool
    data: Any
    error: Optional[str] = None
    source: Optional[str] = None


class Tool(ABC):
    """
    Interface que todos os tools do Belt devem implementar.

    Um tool representa uma capacidade atômica e testável do agente.
    O Claude usa o campo name para chamar o tool e description para
    decidir quando usá-lo. parameters_schema define o contrato de entrada
    no formato JSON Schema aceito pela API Anthropic.

    Regra de implementação obrigatória:
        O método execute() NUNCA deve lançar exceção.
        Todo erro deve ser capturado internamente e retornado
        como ToolResult(success=False, data=None, error=str(e)).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Identificador único do tool.
        Claude usa este nome exato ao emitir um tool_use block.
        Usar snake_case, sem espaços.
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Descrição em linguagem natural para o prompt do agente.
        Claude lê esta descrição para decidir quando e como usar o tool.
        Deve incluir: o que o tool faz, quando usar, e limitações relevantes.
        """
        ...

    @property
    @abstractmethod
    def parameters_schema(self) -> dict:
        """
        JSON Schema dos parâmetros aceitos pelo execute().
        Deve seguir o formato esperado pela API Anthropic em tools=[].
        Exemplo mínimo:
            {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"]
            }
        """
        ...

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        Executa a ação do tool com os parâmetros fornecidos.

        OBRIGATÓRIO: nunca lançar exceção. Encapsular erros:
            try:
                resultado = fazer_algo(**kwargs)
                return ToolResult(success=True, data=resultado, source="nome")
            except Exception as e:
                return ToolResult(success=False, data=None, error=str(e))
        """
        ...
