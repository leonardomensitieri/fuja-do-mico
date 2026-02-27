"""
Gate Editorial da newsletter Fuja do Mico.

Usa claude-haiku para pontuar 0-10 cada uma das 6 linhas editoriais
com base no conteúdo coletado. Linhas com score >= LIMIAR_ATIVACAO
serão passadas ao módulo line_agents para instanciação dos agentes.

Padrão de uso:
    scores = pontuar_linhas(conteudo_coletado)
    # {'linha_1': 8, 'linha_2': 3, ..., 'linha_6': 5}
    linhas_ativas = [l for l, s in scores.items() if s >= LIMIAR_ATIVACAO]
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict

import anthropic

logger = logging.getLogger(__name__)

# Limiar de ativação: linhas com score >= 6 são processadas
LIMIAR_ATIVACAO: int = 6

# Hierarquia de desempate — dossiê seção 4.2
# Rank 1 = maior prioridade quando scores empatam
HIERARQUIA: list[str] = [
    "linha_1",  # Análise Financeira — core da proposta de valor
    "linha_5",  # Erros e Armadilhas — identidade da marca "Fuja do Mico"
    "linha_4",  # Macro e Cenário — alta relevância em semanas com eventos macro
    "linha_2",  # Notícia de Mercado — urgência moderada
    "linha_6",  # Narrativa — alto engajamento, menos urgente
    "linha_3",  # Mentalidade — evergreen, funciona em qualquer semana
]

_LINHAS: list[str] = [
    "linha_1", "linha_2", "linha_3", "linha_4", "linha_5", "linha_6"
]

_PROMPT_GATE = """\
Você é o Orquestrador Editorial da newsletter Fuja do Mico.
Analise o conteúdo coletado abaixo e atribua um score de 0 a 10 para cada linha editorial.

Score 0 = conteúdo insuficiente ou irrelevante para esta linha
Score 10 = conteúdo altamente relevante e rico para esta linha

Linhas editoriais:
- linha_1: Análise Financeira (ativos, valuation, indicadores financeiros, balanços, dividendos)
- linha_2: Notícia de Mercado (eventos recentes relevantes para investidores, IPOs, M&A, resultados)
- linha_3: Mentalidade do Investidor (psicologia, comportamento, vieses cognitivos, disciplina)
- linha_4: Macro e Cenário (Selic, inflação, câmbio, PIB, ciclos econômicos, política monetária)
- linha_5: Erros e Armadilhas (cases de armadilhas, golpes, erros de julgamento, inversão à la Munger)
- linha_6: Narrativa (histórias com lição implícita, trajetórias de investidores, Epiphany Bridge)

Conteúdo coletado:
{conteudo}

Regras de scoring:
- Seja estrito: score >= 6 apenas quando o conteúdo é substancialmente relevante para a linha
- Score 0-3: tema não aparece ou é mencionado de forma marginal
- Score 4-5: tema presente mas sem profundidade suficiente para gerar seção de qualidade
- Score 6-7: conteúdo sólido que viabiliza uma seção editorial de valor
- Score 8-10: conteúdo rico, múltiplos ângulos, alta relevância para a semana

Responda APENAS com JSON válido, sem markdown, sem explicações, sem texto adicional:
{{"linha_1": 0, "linha_2": 0, "linha_3": 0, "linha_4": 0, "linha_5": 0, "linha_6": 0}}
"""


def pontuar_linhas(conteudo_coletado: dict) -> Dict[str, int]:
    """
    Usa claude-haiku para pontuar 0-10 cada linha editorial.

    Args:
        conteudo_coletado: dict com o conteúdo triado pelo 05_triage.py

    Returns:
        dict {linha_id: score} com score inteiro 0-10 por linha.
        Em caso de erro de API ou JSON inválido, retorna todos scores = 0
        e emite warning no log — nunca lança exceção.
    """
    conteudo_str = json.dumps(conteudo_coletado, ensure_ascii=False, indent=2)
    prompt = _PROMPT_GATE.format(conteudo=conteudo_str)

    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)

        resposta = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )

        texto = resposta.content[0].text.strip()
        scores_raw = json.loads(texto)

        # Normalizar: garantir que todas as linhas existem e scores estão em [0, 10]
        return {
            linha: max(0, min(10, int(scores_raw.get(linha, 0))))
            for linha in _LINHAS
        }

    except json.JSONDecodeError as exc:
        logger.warning(
            "Gate editorial: JSON inválido na resposta do modelo: %s. "
            "Usando scores=0 para todas as linhas.",
            exc,
        )
        return {linha: 0 for linha in _LINHAS}

    except Exception as exc:
        logger.warning(
            "Gate editorial: falha ao pontuar linhas (%s: %s). "
            "Usando scores=0 para todas as linhas.",
            type(exc).__name__,
            exc,
        )
        return {linha: 0 for linha in _LINHAS}
