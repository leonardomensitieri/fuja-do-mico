"""
Testes unitários para scripts/05b_editorial_gate.py.

Mock puro — nenhuma chamada real ao Claude API.
Cobre os cenários da AC 8:
    1. main() lê conteudo_triado.json, chama pontuar_linhas, salva scores_editorial.json
    2. data/conteudo_triado.json ausente → exibe aviso e encerra sem crash
    3. JSON de scores gerado tem as chaves esperadas: scores, linhas_ativas, timestamp
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Carregamento do módulo com prefixo numérico ───────────────────────────────

def _carregar_modulo_05b():
    """Carrega scripts/05b_editorial_gate.py via importlib (prefixo numérico)."""
    path = Path(__file__).resolve().parent.parent / "05b_editorial_gate.py"
    spec = importlib.util.spec_from_file_location("_script_05b", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _carregar_modulo_05b()


# ── Fixtures ──────────────────────────────────────────────────────────────────

_TRIADOS_EXEMPLO = [
    {
        "fonte": "rss",
        "titulo": "Petrobras anuncia dividendos",
        "triagem": {
            "relevancia": "alta",
            "temas_identificados": ["dividendos", "petróleo"],
            "resumo_em_3_linhas": "Petrobras anuncia JCP.",
        },
    }
]

_SCORES_MOCK = {
    "linha_1": 8,
    "linha_2": 6,
    "linha_3": 4,
    "linha_4": 7,
    "linha_5": 3,
    "linha_6": 2,
}


def _criar_data_dir(tmp_path: Path) -> Path:
    """Cria e retorna o diretório data/ dentro de tmp_path."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


# ── Testes de execução bem-sucedida ───────────────────────────────────────────

class TestMain05bSucesso:

    def test_salva_scores_editorial_json(self, tmp_path, monkeypatch):
        """main() deve criar data/scores_editorial.json quando conteudo_triado.json existe."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "conteudo_triado.json").write_text(
            json.dumps(_TRIADOS_EXEMPLO), encoding="utf-8"
        )

        with patch.object(_mod, "pontuar_linhas", return_value=_SCORES_MOCK):
            _mod.main()

        assert (data_dir / "scores_editorial.json").exists()

    def test_json_gerado_tem_chaves_obrigatorias(self, tmp_path, monkeypatch):
        """JSON salvo deve ter as chaves: scores, linhas_ativas, timestamp (AC 8)."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "conteudo_triado.json").write_text(
            json.dumps(_TRIADOS_EXEMPLO), encoding="utf-8"
        )

        with patch.object(_mod, "pontuar_linhas", return_value=_SCORES_MOCK):
            _mod.main()

        resultado = json.loads(
            (data_dir / "scores_editorial.json").read_text(encoding="utf-8")
        )

        assert "scores" in resultado
        assert "linhas_ativas" in resultado
        assert "timestamp" in resultado

    def test_linhas_ativas_so_inclui_scores_gte_limiar(self, tmp_path, monkeypatch):
        """linhas_ativas deve conter apenas linhas com score >= LIMIAR_ATIVACAO (6)."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "conteudo_triado.json").write_text(
            json.dumps(_TRIADOS_EXEMPLO), encoding="utf-8"
        )

        with patch.object(_mod, "pontuar_linhas", return_value=_SCORES_MOCK):
            _mod.main()

        resultado = json.loads(
            (data_dir / "scores_editorial.json").read_text(encoding="utf-8")
        )

        linhas_ativas = resultado["linhas_ativas"]
        # Scores >= 6: linha_1(8), linha_2(6), linha_4(7)
        assert "linha_1" in linhas_ativas
        assert "linha_2" in linhas_ativas
        assert "linha_4" in linhas_ativas
        # Scores < 6: linha_3(4), linha_5(3), linha_6(2)
        assert "linha_3" not in linhas_ativas
        assert "linha_5" not in linhas_ativas
        assert "linha_6" not in linhas_ativas

    def test_scores_preservados_no_json(self, tmp_path, monkeypatch):
        """O campo scores no JSON deve refletir os scores retornados por pontuar_linhas."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "conteudo_triado.json").write_text(
            json.dumps(_TRIADOS_EXEMPLO), encoding="utf-8"
        )

        with patch.object(_mod, "pontuar_linhas", return_value=_SCORES_MOCK):
            _mod.main()

        resultado = json.loads(
            (data_dir / "scores_editorial.json").read_text(encoding="utf-8")
        )

        assert resultado["scores"]["linha_1"] == 8
        assert resultado["scores"]["linha_4"] == 7

    def test_pontuar_linhas_e_chamado_com_itens_triados(self, tmp_path, monkeypatch):
        """pontuar_linhas deve ser chamado com dict contendo a chave itens_triados."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "conteudo_triado.json").write_text(
            json.dumps(_TRIADOS_EXEMPLO), encoding="utf-8"
        )

        with patch.object(
            _mod, "pontuar_linhas", return_value=_SCORES_MOCK
        ) as mock_pontuar:
            _mod.main()

        mock_pontuar.assert_called_once()
        chamada_arg = mock_pontuar.call_args[0][0]
        assert "itens_triados" in chamada_arg
        assert isinstance(chamada_arg["itens_triados"], list)


# ── Testes de ausência de arquivos ────────────────────────────────────────────

class TestMain05bArquivoAusente:

    def test_conteudo_triado_ausente_nao_crasha(self, tmp_path, monkeypatch):
        """main() sem conteudo_triado.json deve encerrar sem lançar exceção."""
        monkeypatch.chdir(tmp_path)
        # Não cria data/conteudo_triado.json — deve terminar sem erro
        _mod.main()

    def test_conteudo_triado_ausente_nao_cria_scores(self, tmp_path, monkeypatch):
        """main() sem conteudo_triado.json não deve criar scores_editorial.json."""
        monkeypatch.chdir(tmp_path)
        _mod.main()
        assert not (tmp_path / "data" / "scores_editorial.json").exists()

    def test_conteudo_triado_ausente_exibe_aviso(self, tmp_path, monkeypatch, capsys):
        """main() sem conteudo_triado.json deve exibir mensagem de aviso no stdout."""
        monkeypatch.chdir(tmp_path)
        _mod.main()
        saida = capsys.readouterr().out
        assert "não encontrado" in saida or "pulando" in saida
