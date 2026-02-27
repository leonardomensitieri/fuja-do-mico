"""
Testes unitários para scripts/05c_run_line_agents.py.

Mock puro — nenhuma chamada real ao Claude API ou ReActAgent.
Cobre os cenários da AC 9:
    1. main() com scores_editorial.json indicando 2 linhas ativas →
       salva conteudo_por_linha.json com 2 entradas
    2. scores_editorial.json ausente → exibe aviso e encerra sem crash
    3. conteudo_por_linha.json gerado tem as chaves corretas por linha:
       output, stop_reason, confidence
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ── Carregamento do módulo com prefixo numérico ───────────────────────────────

def _carregar_modulo_05c():
    """Carrega scripts/05c_run_line_agents.py via importlib (prefixo numérico)."""
    path = Path(__file__).resolve().parent.parent / "05c_run_line_agents.py"
    spec = importlib.util.spec_from_file_location("_script_05c", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _carregar_modulo_05c()


# ── Fixtures ──────────────────────────────────────────────────────────────────

_TRIADOS_EXEMPLO = [
    {
        "fonte": "rss",
        "titulo": "Petrobras anuncia dividendos",
        "triagem": {
            "relevancia": "alta",
            "resumo_em_3_linhas": "Petrobras anuncia JCP extraordinário.",
        },
    }
]

_SCORES_2_LINHAS_ATIVAS = {
    "scores": {
        "linha_1": 8,
        "linha_2": 7,
        "linha_3": 3,
        "linha_4": 4,
        "linha_5": 2,
        "linha_6": 1,
    },
    "linhas_ativas": ["linha_1", "linha_2"],
    "limiar_ativacao": 6,
    "timestamp": "2024-01-01T00:00:00+00:00",
}


def _criar_data_dir(tmp_path: Path) -> Path:
    """Cria e retorna o diretório data/ dentro de tmp_path."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


def _mock_agent_result(output: str, stop_reason: str = "done", confidence: float = 0.9):
    """Cria um mock de AgentResult com campos primitivos."""
    resultado = MagicMock()
    resultado.output = output
    resultado.stop_reason = stop_reason
    resultado.confidence = confidence
    return resultado


# ── Testes de execução bem-sucedida ───────────────────────────────────────────

class TestMain05cSucesso:

    def test_salva_conteudo_por_linha_json(self, tmp_path, monkeypatch):
        """main() deve criar data/conteudo_por_linha.json quando ambos os arquivos existem."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "scores_editorial.json").write_text(
            json.dumps(_SCORES_2_LINHAS_ATIVAS), encoding="utf-8"
        )
        (data_dir / "conteudo_triado.json").write_text(
            json.dumps(_TRIADOS_EXEMPLO), encoding="utf-8"
        )

        agentes_mock = {"linha_1": MagicMock(), "linha_2": MagicMock()}
        resultados_mock = {
            "linha_1": _mock_agent_result("Análise Petrobras detalhada"),
            "linha_2": _mock_agent_result("Notícia de mercado processada"),
        }

        monkeypatch.setattr(_mod, "criar_agentes_linha", lambda *a, **k: agentes_mock)
        monkeypatch.setattr(_mod, "executar_agentes_linha", lambda *a, **k: resultados_mock)

        _mod.main()

        assert (data_dir / "conteudo_por_linha.json").exists()

    def test_json_gerado_tem_2_entradas_para_2_linhas_ativas(self, tmp_path, monkeypatch):
        """Quando 2 linhas ativas, conteudo_por_linha.json deve ter exatamente 2 entradas."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "scores_editorial.json").write_text(
            json.dumps(_SCORES_2_LINHAS_ATIVAS), encoding="utf-8"
        )
        (data_dir / "conteudo_triado.json").write_text(
            json.dumps(_TRIADOS_EXEMPLO), encoding="utf-8"
        )

        agentes_mock = {"linha_1": MagicMock(), "linha_2": MagicMock()}
        resultados_mock = {
            "linha_1": _mock_agent_result("Análise linha 1"),
            "linha_2": _mock_agent_result("Análise linha 2"),
        }

        monkeypatch.setattr(_mod, "criar_agentes_linha", lambda *a, **k: agentes_mock)
        monkeypatch.setattr(_mod, "executar_agentes_linha", lambda *a, **k: resultados_mock)

        _mod.main()

        saida = json.loads(
            (data_dir / "conteudo_por_linha.json").read_text(encoding="utf-8")
        )
        assert len(saida) == 2

    def test_cada_entrada_tem_chaves_corretas(self, tmp_path, monkeypatch):
        """Cada entrada em conteudo_por_linha.json deve ter: output, stop_reason, confidence (AC 9)."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "scores_editorial.json").write_text(
            json.dumps(_SCORES_2_LINHAS_ATIVAS), encoding="utf-8"
        )
        (data_dir / "conteudo_triado.json").write_text(
            json.dumps(_TRIADOS_EXEMPLO), encoding="utf-8"
        )

        resultados_mock = {
            "linha_1": _mock_agent_result("Output linha 1", "done", 0.95),
            "linha_2": _mock_agent_result("Output linha 2", "max_steps", 0.70),
        }

        monkeypatch.setattr(_mod, "criar_agentes_linha", lambda *a, **k: {"linha_1": MagicMock(), "linha_2": MagicMock()})
        monkeypatch.setattr(_mod, "executar_agentes_linha", lambda *a, **k: resultados_mock)

        _mod.main()

        saida = json.loads(
            (data_dir / "conteudo_por_linha.json").read_text(encoding="utf-8")
        )

        for linha_id, dados in saida.items():
            assert "output" in dados, f"{linha_id} deve ter campo 'output'"
            assert "stop_reason" in dados, f"{linha_id} deve ter campo 'stop_reason'"
            assert "confidence" in dados, f"{linha_id} deve ter campo 'confidence'"

    def test_valores_primitivos_corretos_no_json(self, tmp_path, monkeypatch):
        """Valores de output, stop_reason e confidence devem ser preservados no JSON."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "scores_editorial.json").write_text(
            json.dumps(_SCORES_2_LINHAS_ATIVAS), encoding="utf-8"
        )
        (data_dir / "conteudo_triado.json").write_text(
            json.dumps(_TRIADOS_EXEMPLO), encoding="utf-8"
        )

        resultados_mock = {
            "linha_1": _mock_agent_result("Texto linha 1", "done", 0.85),
        }

        monkeypatch.setattr(_mod, "criar_agentes_linha", lambda *a, **k: {"linha_1": MagicMock()})
        monkeypatch.setattr(_mod, "executar_agentes_linha", lambda *a, **k: resultados_mock)

        _mod.main()

        saida = json.loads(
            (data_dir / "conteudo_por_linha.json").read_text(encoding="utf-8")
        )

        assert saida["linha_1"]["output"] == "Texto linha 1"
        assert saida["linha_1"]["stop_reason"] == "done"
        assert abs(saida["linha_1"]["confidence"] - 0.85) < 0.001

    def test_criar_agentes_chamado_com_scores(self, tmp_path, monkeypatch):
        """criar_agentes_linha deve ser chamado com os scores lidos do JSON."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "scores_editorial.json").write_text(
            json.dumps(_SCORES_2_LINHAS_ATIVAS), encoding="utf-8"
        )
        (data_dir / "conteudo_triado.json").write_text(
            json.dumps(_TRIADOS_EXEMPLO), encoding="utf-8"
        )

        chamadas = []

        def mock_criar(scores, contexto):
            chamadas.append((scores, contexto))
            return {"linha_1": MagicMock()}

        resultados_mock = {"linha_1": _mock_agent_result("output")}
        monkeypatch.setattr(_mod, "criar_agentes_linha", mock_criar)
        monkeypatch.setattr(_mod, "executar_agentes_linha", lambda *a, **k: resultados_mock)

        _mod.main()

        assert len(chamadas) == 1
        scores_passados = chamadas[0][0]
        assert scores_passados["linha_1"] == 8

    def test_nenhuma_linha_ativa_nao_chama_agents(self, tmp_path, monkeypatch, capsys):
        """Se linhas_ativas estiver vazio, não deve chamar criar_agentes_linha."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        scores_sem_ativas = {**_SCORES_2_LINHAS_ATIVAS, "linhas_ativas": []}
        (data_dir / "scores_editorial.json").write_text(
            json.dumps(scores_sem_ativas), encoding="utf-8"
        )
        (data_dir / "conteudo_triado.json").write_text(
            json.dumps(_TRIADOS_EXEMPLO), encoding="utf-8"
        )

        chamadas = []
        monkeypatch.setattr(_mod, "criar_agentes_linha", lambda *a, **k: chamadas.append(1) or {})
        monkeypatch.setattr(_mod, "executar_agentes_linha", lambda *a, **k: {})

        _mod.main()

        assert len(chamadas) == 0


# ── Testes de ausência de arquivos ────────────────────────────────────────────

class TestMain05cArquivosAusentes:

    def test_scores_ausente_nao_crasha(self, tmp_path, monkeypatch):
        """main() sem scores_editorial.json deve encerrar sem lançar exceção."""
        monkeypatch.chdir(tmp_path)
        # Não cria nenhum arquivo em data/
        _mod.main()

    def test_scores_ausente_nao_cria_conteudo_por_linha(self, tmp_path, monkeypatch):
        """main() sem scores_editorial.json não deve criar conteudo_por_linha.json."""
        monkeypatch.chdir(tmp_path)
        _mod.main()
        assert not (tmp_path / "data" / "conteudo_por_linha.json").exists()

    def test_scores_ausente_exibe_aviso(self, tmp_path, monkeypatch, capsys):
        """main() sem scores_editorial.json deve exibir mensagem de aviso no stdout."""
        monkeypatch.chdir(tmp_path)
        _mod.main()
        saida = capsys.readouterr().out
        assert "não encontrado" in saida or "pulando" in saida

    def test_conteudo_triado_ausente_nao_crasha(self, tmp_path, monkeypatch):
        """main() com scores mas sem conteudo_triado.json deve encerrar sem lançar exceção."""
        monkeypatch.chdir(tmp_path)
        data_dir = _criar_data_dir(tmp_path)
        (data_dir / "scores_editorial.json").write_text(
            json.dumps(_SCORES_2_LINHAS_ATIVAS), encoding="utf-8"
        )
        # conteudo_triado.json não existe
        _mod.main()
