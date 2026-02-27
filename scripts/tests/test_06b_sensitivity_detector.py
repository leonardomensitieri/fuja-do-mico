"""
Testes unitários para scripts/06b_sensitivity_detector.py.

Mock puro — nenhuma chamada real ao Claude API.
Cobre os cenários da AC 8:
    1. main() lê conteudo_gerado.json, chama detectar_sensibilidade, salva sensibilidade_flag.json
    2. data/conteudo_gerado.json ausente → exibe aviso e encerra sem crash
    3. JSON gerado tem as chaves esperadas: nivel, flags, disclaimer, timestamp
    4. nivel retornado é sempre um dos valores válidos: "alto", "medio" ou "nenhum"
    5. Texto extraído inclui conteúdo do editorial e das sections[]
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Carregamento do módulo com prefixo numérico ───────────────────────────────

def _carregar_modulo_06b():
    """Carrega scripts/06b_sensitivity_detector.py via importlib (prefixo numérico)."""
    path = Path(__file__).resolve().parent.parent / "06b_sensitivity_detector.py"
    spec = importlib.util.spec_from_file_location("_script_06b", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _carregar_modulo_06b()


# ── Fixtures ──────────────────────────────────────────────────────────────────

_CONTEUDO_EXEMPLO = {
    "titulo_edicao": "Dividendos de março",
    "editorial": "Texto editorial sobre o mercado financeiro.",
    "sections": [
        {"title": "Petrobras", "content": "Análise dos resultados do trimestre."},
        {"title": "Vale", "body": "Perspectivas para minério de ferro."},
    ],
}

_RESULTADO_NENHUM = {"nivel": "nenhum", "flags": [], "disclaimer": ""}
_RESULTADO_MEDIO = {
    "nivel": "medio",
    "flags": ["Análise pode ser interpretada como recomendação implícita"],
    "disclaimer": "Este conteúdo tem caráter exclusivamente educacional.",
}
_RESULTADO_ALTO = {
    "nivel": "alto",
    "flags": ["Recomendação direta de compra de PETR4 a R$ 40"],
    "disclaimer": "",
}


def _criar_data_dir(tmp_path: Path) -> Path:
    """Cria e retorna o diretório data/ dentro de tmp_path."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


# ── Testes de execução bem-sucedida ───────────────────────────────────────────

class TestMain06bSucesso:

    def test_salva_sensibilidade_flag_json(self, tmp_path, monkeypatch):
        """main() deve criar data/sensibilidade_flag.json quando conteudo_gerado.json existe."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "conteudo_gerado.json").write_text(
            json.dumps(_CONTEUDO_EXEMPLO), encoding="utf-8"
        )

        monkeypatch.setattr(_mod, "anthropic", MagicMock())
        with patch.object(_mod, "detectar_sensibilidade", return_value=_RESULTADO_NENHUM):
            _mod.main()

        assert (data_dir / "sensibilidade_flag.json").exists()

    def test_json_gerado_tem_chaves_obrigatorias(self, tmp_path, monkeypatch):
        """JSON salvo deve ter as chaves: nivel, flags, disclaimer, timestamp (AC 8)."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "conteudo_gerado.json").write_text(
            json.dumps(_CONTEUDO_EXEMPLO), encoding="utf-8"
        )

        monkeypatch.setattr(_mod, "anthropic", MagicMock())
        with patch.object(_mod, "detectar_sensibilidade", return_value=_RESULTADO_NENHUM):
            _mod.main()

        resultado = json.loads(
            (data_dir / "sensibilidade_flag.json").read_text(encoding="utf-8")
        )

        assert "nivel" in resultado
        assert "flags" in resultado
        assert "disclaimer" in resultado
        assert "timestamp" in resultado

    @pytest.mark.parametrize("nivel", ["alto", "medio", "nenhum"])
    def test_nivel_valido_para_cada_retorno(self, tmp_path, monkeypatch, nivel):
        """nivel salvo no JSON deve ser sempre um dos valores válidos (AC 8)."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "conteudo_gerado.json").write_text(
            json.dumps(_CONTEUDO_EXEMPLO), encoding="utf-8"
        )

        resultado_mock = {"nivel": nivel, "flags": [], "disclaimer": ""}
        monkeypatch.setattr(_mod, "anthropic", MagicMock())
        with patch.object(_mod, "detectar_sensibilidade", return_value=resultado_mock):
            _mod.main()

        saida = json.loads(
            (data_dir / "sensibilidade_flag.json").read_text(encoding="utf-8")
        )

        assert saida["nivel"] in ("alto", "medio", "nenhum")
        assert saida["nivel"] == nivel

    def test_detectar_sensibilidade_chamado_com_texto(self, tmp_path, monkeypatch):
        """detectar_sensibilidade deve ser chamado com o texto extraído do conteudo_gerado."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "conteudo_gerado.json").write_text(
            json.dumps(_CONTEUDO_EXEMPLO), encoding="utf-8"
        )

        chamadas = []

        def mock_detectar(texto, cliente):
            chamadas.append(texto)
            return _RESULTADO_NENHUM

        monkeypatch.setattr(_mod, "anthropic", MagicMock())
        monkeypatch.setattr(_mod, "detectar_sensibilidade", mock_detectar)

        _mod.main()

        assert len(chamadas) == 1
        assert isinstance(chamadas[0], str)
        assert len(chamadas[0]) > 0


# ── Testes de ausência de arquivo ─────────────────────────────────────────────

class TestMain06bArquivoAusente:

    def test_conteudo_gerado_ausente_nao_crasha(self, tmp_path, monkeypatch):
        """main() sem conteudo_gerado.json deve encerrar sem lançar exceção."""
        monkeypatch.chdir(tmp_path)
        # Não cria data/conteudo_gerado.json
        _mod.main()

    def test_conteudo_gerado_ausente_nao_cria_flag(self, tmp_path, monkeypatch):
        """main() sem conteudo_gerado.json não deve criar sensibilidade_flag.json."""
        monkeypatch.chdir(tmp_path)
        _mod.main()
        assert not (tmp_path / "data" / "sensibilidade_flag.json").exists()

    def test_conteudo_gerado_ausente_exibe_aviso(self, tmp_path, monkeypatch, capsys):
        """main() sem conteudo_gerado.json deve exibir mensagem de aviso no stdout."""
        monkeypatch.chdir(tmp_path)
        _mod.main()
        saida = capsys.readouterr().out
        assert "não encontrado" in saida or "pulando" in saida


# ── Testes de extração de texto ───────────────────────────────────────────────

class TestExtrairTexto:

    def test_inclui_editorial_no_texto(self):
        """extrair_texto_gerado deve incluir o campo editorial."""
        conteudo = {"editorial": "Texto importante do editorial.", "sections": []}
        texto = _mod.extrair_texto_gerado(conteudo)
        assert "Texto importante do editorial." in texto

    def test_inclui_sections_no_texto(self):
        """extrair_texto_gerado deve incluir conteúdo das sections[]."""
        conteudo = {
            "sections": [
                {"title": "Título da Seção", "content": "Conteúdo da seção aqui."}
            ]
        }
        texto = _mod.extrair_texto_gerado(conteudo)
        assert "Título da Seção" in texto
        assert "Conteúdo da seção aqui." in texto

    def test_inclui_editorial_e_sections(self):
        """extrair_texto_gerado deve incluir tanto o editorial quanto as sections[]."""
        conteudo = _CONTEUDO_EXEMPLO
        texto = _mod.extrair_texto_gerado(conteudo)
        assert "Texto editorial sobre o mercado financeiro." in texto
        assert "Petrobras" in texto
        assert "Análise dos resultados do trimestre." in texto

    def test_conteudo_vazio_retorna_string(self):
        """extrair_texto_gerado com dict vazio deve retornar string (sem erro)."""
        resultado = _mod.extrair_texto_gerado({})
        assert isinstance(resultado, str)

    def test_section_com_items_lista(self):
        """extrair_texto_gerado deve processar sections com campo items (lista)."""
        conteudo = {
            "sections": [
                {"items": ["item 1", "item 2", "item 3"]}
            ]
        }
        texto = _mod.extrair_texto_gerado(conteudo)
        assert "item 1" in texto
        assert "item 2" in texto
