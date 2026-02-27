"""
Critérios de parada do ReAct Loop.

Decision tree: Worker Script — lógica de decisão pura, sem I/O externo.
Todos os parâmetros vêm do dossiê (seção 6.1) e são configurados
por instância, permitindo que cada agente tenha seus próprios limites
sem duplicar a lógica de parada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple


@dataclass
class ReActStopCriteria:
    """
    Parâmetros de parada do ReAct Loop para um agente específico.

    Combina três mecanismos independentes:
    - Hard stop por número máximo de iterações (nunca ultrapassa)
    - Soft stop por confiança (para antes se a qualidade foi atingida)
    - Hard stop por tempo de parede (crítico em GitHub Actions)

    O min_iterations protege contra saída prematura antes de o agente
    ter dados suficientes para uma decisão confiável.
    """

    max_iterations: int
    confidence_threshold: float
    min_iterations: int
    timeout_seconds: int
    agent_id: str

    def should_stop(
        self,
        iteration: int,
        confidence: float,
        elapsed_seconds: float,
    ) -> tuple[bool, Literal["CONFIDENT", "MAX_ITER", "TIMEOUT"] | None]:
        """
        Decide se o loop deve parar nesta iteração.

        A ordem de verificação é intencional:
        1. TIMEOUT é sempre verificado primeiro — é um hard stop de segurança
        2. min_iterations impede saída precipitada antes de dados suficientes
        3. CONFIDENT é o caminho feliz — qualidade atingida, pode parar
        4. MAX_ITER é o fallback — esgotou sem atingir confiança suficiente

        Args:
            iteration: índice da iteração atual (base 0)
            confidence: score de confiança atual do agente (0.0 a 1.0)
            elapsed_seconds: tempo decorrido desde o início do run()

        Returns:
            (deve_parar, motivo) — motivo é None se o loop deve continuar
        """
        if elapsed_seconds >= self.timeout_seconds:
            return True, "TIMEOUT"

        if iteration < self.min_iterations:
            return False, None

        if confidence >= self.confidence_threshold:
            return True, "CONFIDENT"

        if iteration >= self.max_iterations:
            return True, "MAX_ITER"

        return False, None


# Instâncias pré-configuradas conforme tabela do dossiê — seção 6.1
# Qualquer ajuste de parâmetro deve ser feito aqui, em um único lugar.
CRITERIA: dict[str, ReActStopCriteria] = {
    "triage": ReActStopCriteria(
        max_iterations=3,
        confidence_threshold=0.80,
        min_iterations=1,
        timeout_seconds=30,
        agent_id="triage",
    ),
    "editorial": ReActStopCriteria(
        max_iterations=2,
        confidence_threshold=0.85,
        min_iterations=1,
        timeout_seconds=20,
        agent_id="editorial",
    ),
    "linha_1": ReActStopCriteria(
        max_iterations=5,
        confidence_threshold=0.75,
        min_iterations=2,
        timeout_seconds=90,
        agent_id="linha_1",
    ),
    "linha_2": ReActStopCriteria(
        max_iterations=4,
        confidence_threshold=0.80,
        min_iterations=2,
        timeout_seconds=60,
        agent_id="linha_2",
    ),
    "linha_3": ReActStopCriteria(
        max_iterations=3,
        confidence_threshold=0.82,
        min_iterations=1,
        timeout_seconds=60,
        agent_id="linha_3",
    ),
    "linha_4": ReActStopCriteria(
        max_iterations=4,
        confidence_threshold=0.80,
        min_iterations=2,
        timeout_seconds=90,
        agent_id="linha_4",
    ),
    "linha_5": ReActStopCriteria(
        max_iterations=4,
        confidence_threshold=0.82,
        min_iterations=2,
        timeout_seconds=60,
        agent_id="linha_5",
    ),
    "linha_6": ReActStopCriteria(
        max_iterations=3,
        confidence_threshold=0.85,
        min_iterations=1,
        timeout_seconds=60,
        agent_id="linha_6",
    ),
    "geracao": ReActStopCriteria(
        max_iterations=4,
        confidence_threshold=0.82,
        min_iterations=2,
        timeout_seconds=120,
        agent_id="geracao",
    ),
}
