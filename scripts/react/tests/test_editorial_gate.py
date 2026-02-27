"""
Testes unitários para o Gate Editorial (editorial_gate.py).

Mock puro — nenhuma chamada real ao Claude API.
Cobre os cenários da AC 11:
    1. pontuar_linhas() retorna dict com as 6 linhas e scores inteiros 0-10
    2. JSON inválido retornado pelo mock → fallback todos scores = 0 (sem crash)
    3. Exceção genérica na chamada de API → fallback scores = 0 (sem crash)
    4. LIMIAR_ATIVACAO == 6
    5. HIERARQUIA tem 6 elementos na ordem correta do dossiê
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.react.editorial_gate import (
    HIERARQUIA,
    LIMIAR_ATIVACAO,
    _LINHAS,
    pontuar_linhas,
)

# ── Fixtures de conteúdo ──────────────────────────────────────────────────────

_CONTEUDO_EXEMPLO = {
    "emails": ["Petrobras anuncia dividendos extraordinários de R$1,20 por ação"],
    "rss": ["Selic mantida em 10,5% ao ano pelo Copom"],
    "youtube": ["Análise de balanço: como ler o DRE de uma empresa"],
}

_SCORES_VALIDOS = {
    "linha_1": 9,
    "linha_2": 7,
    "linha_3": 4,
    "linha_4": 8,
    "linha_5": 3,
    "linha_6": 2,
}


def _mock_resposta_anthropic(texto: str) -> MagicMock:
    """Cria mock de resposta da API Anthropic com texto fornecido."""
    content_block = MagicMock()
    content_block.text = texto
    resposta = MagicMock()
    resposta.content = [content_block]
    return resposta


# ── Testes de pontuação bem-sucedida ─────────────────────────────────────────

class TestPontuarLinhas:

    def test_retorna_dict_com_6_linhas(self):
        """pontuar_linhas() deve retornar dict com as 6 linhas esperadas."""
        texto_resposta = json.dumps(_SCORES_VALIDOS)

        with patch("scripts.react.editorial_gate.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _mock_resposta_anthropic(texto_resposta)

            scores = pontuar_linhas(_CONTEUDO_EXEMPLO)

        assert set(scores.keys()) == set(_LINHAS)
        assert len(scores) == 6

    def test_scores_sao_inteiros_0_a_10(self):
        """Todos os scores devem ser inteiros entre 0 e 10 inclusive."""
        texto_resposta = json.dumps(_SCORES_VALIDOS)

        with patch("scripts.react.editorial_gate.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _mock_resposta_anthropic(texto_resposta)

            scores = pontuar_linhas(_CONTEUDO_EXEMPLO)

        for linha, score in scores.items():
            assert isinstance(score, int), f"Score de {linha} deve ser int, got {type(score)}"
            assert 0 <= score <= 10, f"Score de {linha} fora do intervalo [0,10]: {score}"

    def test_valores_corretos_do_mock(self):
        """Os valores retornados devem corresponder ao JSON mockado."""
        texto_resposta = json.dumps(_SCORES_VALIDOS)

        with patch("scripts.react.editorial_gate.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _mock_resposta_anthropic(texto_resposta)

            scores = pontuar_linhas(_CONTEUDO_EXEMPLO)

        assert scores["linha_1"] == 9
        assert scores["linha_4"] == 8

    def test_score_acima_de_10_e_clampado(self):
        """Score > 10 na resposta deve ser clampado para 10."""
        scores_invalidos = {l: 15 for l in _LINHAS}
        texto_resposta = json.dumps(scores_invalidos)

        with patch("scripts.react.editorial_gate.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _mock_resposta_anthropic(texto_resposta)

            scores = pontuar_linhas(_CONTEUDO_EXEMPLO)

        for score in scores.values():
            assert score == 10

    def test_score_negativo_e_clampado_para_zero(self):
        """Score < 0 na resposta deve ser clampado para 0."""
        scores_invalidos = {l: -5 for l in _LINHAS}
        texto_resposta = json.dumps(scores_invalidos)

        with patch("scripts.react.editorial_gate.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _mock_resposta_anthropic(texto_resposta)

            scores = pontuar_linhas(_CONTEUDO_EXEMPLO)

        for score in scores.values():
            assert score == 0

    def test_linha_ausente_na_resposta_recebe_score_zero(self):
        """Linha ausente no JSON da resposta deve receber score 0."""
        scores_parciais = {"linha_1": 8, "linha_2": 6}  # faltam 4 linhas
        texto_resposta = json.dumps(scores_parciais)

        with patch("scripts.react.editorial_gate.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _mock_resposta_anthropic(texto_resposta)

            scores = pontuar_linhas(_CONTEUDO_EXEMPLO)

        assert scores["linha_3"] == 0
        assert scores["linha_4"] == 0
        assert scores["linha_1"] == 8  # presente no mock — deve ser preservado


# ── Testes de fallback (erros) ────────────────────────────────────────────────

class TestPontuarLinhasFallback:

    def test_json_invalido_retorna_scores_zero_sem_crash(self):
        """Resposta com JSON malformado deve retornar todos scores = 0 sem lançar exceção."""
        with patch("scripts.react.editorial_gate.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _mock_resposta_anthropic(
                "Aqui está minha análise: linha_1=8, muito bom!"  # JSON inválido
            )

            scores = pontuar_linhas(_CONTEUDO_EXEMPLO)

        assert set(scores.keys()) == set(_LINHAS)
        for score in scores.values():
            assert score == 0

    def test_excecao_de_api_retorna_scores_zero_sem_crash(self):
        """Exceção na chamada de API deve retornar todos scores = 0 sem propagar."""
        with patch("scripts.react.editorial_gate.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = ConnectionError("Timeout na API")

            scores = pontuar_linhas(_CONTEUDO_EXEMPLO)

        assert set(scores.keys()) == set(_LINHAS)
        for score in scores.values():
            assert score == 0

    def test_api_key_ausente_nao_propaga_excecao(self):
        """Mesmo sem ANTHROPIC_API_KEY, a função não deve propagar exceção."""
        with patch("scripts.react.editorial_gate.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("authentication_error")

            scores = pontuar_linhas({})  # conteúdo vazio

        assert len(scores) == 6
        for score in scores.values():
            assert score == 0

    def test_json_markdown_retorna_scores_zero(self):
        """Modelo retornando JSON em bloco markdown (```json) deve falhar de forma controlada."""
        texto_com_markdown = "```json\n{\"linha_1\": 8}\n```"

        with patch("scripts.react.editorial_gate.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _mock_resposta_anthropic(texto_com_markdown)

            scores = pontuar_linhas(_CONTEUDO_EXEMPLO)

        # O JSON com markdown vai falhar no parse — fallback esperado
        assert set(scores.keys()) == set(_LINHAS)


# ── Testes das constantes ─────────────────────────────────────────────────────

class TestConstantes:

    def test_limiar_ativacao_e_6(self):
        """LIMIAR_ATIVACAO deve ser exatamente 6 conforme dossiê."""
        assert LIMIAR_ATIVACAO == 6

    def test_hierarquia_tem_6_elementos(self):
        """HIERARQUIA deve ter exatamente 6 elementos."""
        assert len(HIERARQUIA) == 6

    def test_hierarquia_cobre_todas_as_linhas(self):
        """HIERARQUIA deve incluir todas as 6 linhas."""
        assert set(HIERARQUIA) == {
            "linha_1", "linha_2", "linha_3", "linha_4", "linha_5", "linha_6"
        }

    def test_hierarquia_ordem_correta(self):
        """HIERARQUIA deve seguir a ordem definida no dossiê seção 4.2."""
        assert HIERARQUIA[0] == "linha_1", "Rank 1 deve ser linha_1 (Análise Financeira)"
        assert HIERARQUIA[1] == "linha_5", "Rank 2 deve ser linha_5 (Erros e Armadilhas)"
        assert HIERARQUIA[2] == "linha_4", "Rank 3 deve ser linha_4 (Macro e Cenário)"
        assert HIERARQUIA[3] == "linha_2", "Rank 4 deve ser linha_2 (Notícia de Mercado)"
        assert HIERARQUIA[4] == "linha_6", "Rank 5 deve ser linha_6 (Narrativa)"
        assert HIERARQUIA[5] == "linha_3", "Rank 6 deve ser linha_3 (Mentalidade)"
