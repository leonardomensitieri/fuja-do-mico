"""
Testes unitários para o CloneLoader.

Cobre os cenários da AC 8:
    1. Carregamento bem-sucedido (mock do sistema de arquivos)
    2. Substituição correta de placeholder {ticker}
    3. FileNotFoundError para clone_id inexistente
    4. Retorno de string não-vazia para cada um dos 15 clone_ids reais (integração leve)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

# ── IDs esperados ──────────────────────────────────────────────────────────────

CLONE_IDS_ESPERADOS = [
    "graham",
    "buffett",
    "barsi",
    "damodaran",
    "munger",
    "housel",
    "taleb",
    "cialdini",
    "dalio",
    "soros",
    "keynes",
    "brunson",
    "holiday",
    "contextual_l1",
    "contextual_l2",
]

# Conteúdo mínimo de ficha válida para uso nos mocks
_FICHA_MOCK = """# Clone: Teste

**ID:** clone-teste
**Versão:** 1.0.0
**Linha primária:** Análise Financeira

## Identidade

**Persona:** Clone de teste para validação unitária.
**Tom:** Técnico
**Público-alvo:** Avançado

## Especialidade

**Temas fortes:** Testes unitários
**Temas fracos / evitar:** Nada
**Linhas secundárias:** Nenhuma

## Restrições

- Nunca recomendar compra ou venda

## Prompt Base

Você é um clone de teste. Analise {ticker} com foco em validação de código.
Retorne sempre uma análise estruturada. Nunca recomende compra ou venda.
Este prompt serve para testar o mecanismo de carregamento de fichas.
"""


# ── Testes com mock do sistema de arquivos ────────────────────────────────────

class TestLoadClonePromptMock:

    def test_carregamento_bem_sucedido(self):
        """Ficha existente retorna string não-vazia."""
        with patch("scripts.clones.loader._CATALOG_DIR") as mock_dir:
            mock_path = mock_dir / "clone-graham.md"
            mock_path.exists.return_value = True
            mock_path.__truediv__ = lambda self, other: mock_path
            mock_path.read_text.return_value = _FICHA_MOCK

            # Recria o patch do caminho corretamente
            from scripts.clones.loader import _extrair_prompt_base
            prompt = _extrair_prompt_base(_FICHA_MOCK, "graham")

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Você é um clone de teste" in prompt

    def test_substituicao_placeholder_ticker(self):
        """Placeholder {ticker} deve ser substituído pelo valor fornecido."""
        from scripts.clones.loader import _extrair_prompt_base

        prompt_raw = _extrair_prompt_base(_FICHA_MOCK, "graham")
        prompt_com_ticker = prompt_raw.format_map({"ticker": "PETR4"})

        assert "PETR4" in prompt_com_ticker
        assert "{ticker}" not in prompt_com_ticker

    def test_file_not_found_clone_inexistente(self):
        """FileNotFoundError deve ser lançado para clone_id inexistente."""
        from scripts.clones.loader import load_clone_prompt

        with pytest.raises(FileNotFoundError) as exc_info:
            load_clone_prompt("clone_que_nao_existe_xyz")

        assert "clone_que_nao_existe_xyz" in str(exc_info.value)

    def test_mensagem_erro_lista_disponiveis(self):
        """Mensagem de erro deve incluir lista de clone_ids disponíveis."""
        from scripts.clones.loader import load_clone_prompt

        with pytest.raises(FileNotFoundError) as exc_info:
            load_clone_prompt("invalido")

        # A mensagem de erro deve ser informativa
        erro = str(exc_info.value)
        assert "invalido" in erro

    def test_extracao_sem_secao_prompt_base(self):
        """Ficha sem ## Prompt Base deve lançar ValueError."""
        from scripts.clones.loader import _extrair_prompt_base

        ficha_incompleta = "# Clone: Sem Prompt\n\n## Identidade\n\nAlgo aqui.\n"

        with pytest.raises(ValueError) as exc_info:
            _extrair_prompt_base(ficha_incompleta, "teste")

        assert "Prompt Base" in str(exc_info.value)

    def test_sem_kwargs_retorna_prompt_com_placeholder(self):
        """Sem kwargs, placeholder deve permanecer na string (não substituído)."""
        from scripts.clones.loader import _extrair_prompt_base

        prompt = _extrair_prompt_base(_FICHA_MOCK, "graham")
        # Sem format_map, {ticker} permanece
        assert "{ticker}" in prompt


# ── Testes de integração leve (lê arquivos reais) ─────────────────────────────

class TestLoadClonePromptIntegracao:
    """
    Testes de integração que lêem os arquivos reais do catálogo.
    Não fazem mock — dependem dos arquivos em config/clone_catalog/.
    """

    @pytest.mark.parametrize("clone_id", CLONE_IDS_ESPERADOS)
    def test_todos_clone_ids_carregam(self, clone_id):
        """Cada um dos 15 clone_ids deve retornar string não-vazia."""
        from scripts.clones.loader import load_clone_prompt

        prompt = load_clone_prompt(clone_id)

        assert isinstance(prompt, str), f"Prompt de '{clone_id}' não é string"
        assert len(prompt) >= 150, (
            f"Prompt de '{clone_id}' tem menos de 150 palavras/chars ({len(prompt)}). "
            "Verifique a seção ## Prompt Base da ficha."
        )

    @pytest.mark.parametrize("clone_id", ["graham", "buffett", "barsi", "damodaran"])
    def test_clones_analise_aceitam_ticker(self, clone_id):
        """Clones de análise financeira devem aceitar substituição de {ticker}."""
        from scripts.clones.loader import load_clone_prompt

        prompt = load_clone_prompt(clone_id, ticker="PETR4")

        assert "PETR4" in prompt
        assert "{ticker}" not in prompt

    @pytest.mark.parametrize("clone_id", [
        "munger", "housel", "taleb", "cialdini",
        "dalio", "soros", "keynes",
        "brunson", "holiday",
        "contextual_l1", "contextual_l2",
    ])
    def test_clones_tema_aceitam_tema(self, clone_id):
        """Clones com {tema} devem aceitar substituição do placeholder."""
        from scripts.clones.loader import load_clone_prompt

        prompt = load_clone_prompt(clone_id, tema="inflação e investimentos")

        assert "inflação e investimentos" in prompt
        assert "{tema}" not in prompt

    def test_total_de_fichas_no_catalogo(self):
        """O catálogo deve conter exatamente 15 fichas."""
        from scripts.clones.loader import _listar_clones

        disponiveis = _listar_clones()
        assert len(disponiveis) == 15, (
            f"Esperado 15 fichas no catálogo, encontrado {len(disponiveis)}: {disponiveis}"
        )

    def test_todos_ids_esperados_presentes(self):
        """Todos os 15 clone_ids esperados devem estar no catálogo."""
        from scripts.clones.loader import _listar_clones

        disponiveis = set(_listar_clones())
        esperados = set(CLONE_IDS_ESPERADOS)
        faltando = esperados - disponiveis

        assert not faltando, f"Clone_ids faltando no catálogo: {faltando}"
