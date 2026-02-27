"""
Testes unitários para ReActStopCriteria.

Todos os cenários rodam sem chamar a Claude API — lógica pura.
Cobre os 4 casos da AC 8:
    1. Parada por CONFIDENT (confiança atingida após min_iterations)
    2. Parada por MAX_ITER (esgotou iterações sem atingir confiança)
    3. Parada por TIMEOUT (tempo de parede excedido)
    4. Guard de min_iterations (não para antes do mínimo mesmo com confiança alta)
"""

import pytest
from scripts.react.criteria import CRITERIA, ReActStopCriteria


# ── Fixture base ──────────────────────────────────────────────────────────────

@pytest.fixture
def criterio_padrao():
    """Critério genérico para testes de lógica."""
    return ReActStopCriteria(
        max_iterations=5,
        confidence_threshold=0.80,
        min_iterations=2,
        timeout_seconds=60,
        agent_id="test_agent",
    )


# ── Cenário 1: Parada por CONFIDENT ───────────────────────────────────────────

def test_para_por_confident_apos_min_iterations(criterio_padrao):
    """Deve parar com CONFIDENT quando confiança >= threshold após min_iterations."""
    deve_parar, motivo = criterio_padrao.should_stop(
        iteration=2,        # >= min_iterations (2)
        confidence=0.85,    # >= confidence_threshold (0.80)
        elapsed_seconds=10.0,
    )
    assert deve_parar is True
    assert motivo == "CONFIDENT"


def test_para_por_confident_exatamente_no_threshold(criterio_padrao):
    """Deve parar quando confiança é exatamente igual ao threshold."""
    deve_parar, motivo = criterio_padrao.should_stop(
        iteration=3,
        confidence=0.80,    # == confidence_threshold
        elapsed_seconds=5.0,
    )
    assert deve_parar is True
    assert motivo == "CONFIDENT"


# ── Cenário 2: Parada por MAX_ITER ────────────────────────────────────────────

def test_para_por_max_iter_sem_confianca(criterio_padrao):
    """Deve parar com MAX_ITER quando esgota iterações sem atingir confiança."""
    deve_parar, motivo = criterio_padrao.should_stop(
        iteration=5,        # >= max_iterations (5)
        confidence=0.60,    # < confidence_threshold
        elapsed_seconds=30.0,
    )
    assert deve_parar is True
    assert motivo == "MAX_ITER"


def test_continua_antes_de_max_iter_sem_confianca(criterio_padrao):
    """Não deve parar quando ainda tem iterações e confiança está baixa."""
    deve_parar, motivo = criterio_padrao.should_stop(
        iteration=3,
        confidence=0.50,
        elapsed_seconds=20.0,
    )
    assert deve_parar is False
    assert motivo is None


# ── Cenário 3: Parada por TIMEOUT ─────────────────────────────────────────────

def test_para_por_timeout(criterio_padrao):
    """Deve parar com TIMEOUT quando tempo decorrido >= timeout_seconds."""
    deve_parar, motivo = criterio_padrao.should_stop(
        iteration=1,
        confidence=0.90,    # confiança alta, mas timeout prevalece
        elapsed_seconds=60.0,  # == timeout_seconds
    )
    assert deve_parar is True
    assert motivo == "TIMEOUT"


def test_timeout_tem_prioridade_sobre_confident(criterio_padrao):
    """TIMEOUT deve ter precedência mesmo quando confiança já atingiu o threshold."""
    deve_parar, motivo = criterio_padrao.should_stop(
        iteration=3,
        confidence=0.95,
        elapsed_seconds=61.0,  # > timeout_seconds
    )
    assert deve_parar is True
    assert motivo == "TIMEOUT"


# ── Cenário 4: Guard de min_iterations ───────────────────────────────────────

def test_nao_para_antes_de_min_iterations_mesmo_com_confianca_alta(criterio_padrao):
    """Não deve parar antes de min_iterations mesmo com confiança acima do threshold."""
    deve_parar, motivo = criterio_padrao.should_stop(
        iteration=1,        # < min_iterations (2)
        confidence=0.99,    # muito acima do threshold
        elapsed_seconds=5.0,
    )
    assert deve_parar is False
    assert motivo is None


def test_nao_para_na_iteracao_zero(criterio_padrao):
    """Não deve parar na iteração 0 (antes de qualquer raciocínio)."""
    deve_parar, motivo = criterio_padrao.should_stop(
        iteration=0,
        confidence=1.0,
        elapsed_seconds=0.1,
    )
    assert deve_parar is False
    assert motivo is None


# ── Testes do dict CRITERIA ───────────────────────────────────────────────────

def test_criteria_contem_todos_os_agentes():
    """O dict CRITERIA deve conter instâncias para todos os 9 agentes do dossiê."""
    agentes_esperados = {
        "triage", "editorial",
        "linha_1", "linha_2", "linha_3", "linha_4", "linha_5", "linha_6",
        "geracao",
    }
    assert set(CRITERIA.keys()) == agentes_esperados


def test_criteria_valores_da_tabela_do_dossie():
    """Verifica os parâmetros exatos conforme tabela do dossiê — seção 6.1."""
    assert CRITERIA["triage"].max_iterations == 3
    assert CRITERIA["triage"].confidence_threshold == 0.80
    assert CRITERIA["triage"].min_iterations == 1
    assert CRITERIA["triage"].timeout_seconds == 30

    assert CRITERIA["linha_1"].max_iterations == 5
    assert CRITERIA["linha_1"].confidence_threshold == 0.75
    assert CRITERIA["linha_1"].min_iterations == 2
    assert CRITERIA["linha_1"].timeout_seconds == 90

    assert CRITERIA["geracao"].max_iterations == 4
    assert CRITERIA["geracao"].timeout_seconds == 120


def test_criteria_agent_id_corresponde_a_chave():
    """O agent_id de cada instância deve corresponder à chave do dict."""
    for chave, criterio in CRITERIA.items():
        assert criterio.agent_id == chave, (
            f"agent_id '{criterio.agent_id}' não corresponde à chave '{chave}'"
        )
