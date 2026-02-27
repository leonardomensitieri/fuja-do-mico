"""
SCRIPT 05b — Gate Editorial
============================
Pontua 0-10 cada linha editorial com base no conteúdo triado.
Salva resultado em data/scores_editorial.json.

Posição no pipeline: após 05_triage.py, antes das APIs financeiras (04/04b).
O orquestrador usa os scores para:
  - Decidir se linha_1 (Análise Financeira) está ativa → chamar Brapi/Fintz
  - Passar scores para 05c_run_line_agents.py

Credenciais necessárias:
  - ANTHROPIC_API_KEY : usa claude-haiku para pontuar linhas
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.react.editorial_gate import LIMIAR_ATIVACAO, pontuar_linhas


def main() -> None:
    print("📊 Iniciando Gate Editorial...")

    path_triado = Path("data/conteudo_triado.json")
    if not path_triado.exists():
        print("  ⚠️  data/conteudo_triado.json não encontrado — pulando gate editorial")
        return

    triados = json.loads(path_triado.read_text(encoding="utf-8"))
    print(f"  {len(triados)} itens triados carregados")

    # Passa conteúdo triado estruturado como contexto para o gate
    conteudo_para_gate = {"itens_triados": triados}
    scores = pontuar_linhas(conteudo_para_gate)

    linhas_ativas = [l for l, s in sorted(scores.items()) if s >= LIMIAR_ATIVACAO]

    resultado = {
        "scores": scores,
        "linhas_ativas": linhas_ativas,
        "limiar_ativacao": LIMIAR_ATIVACAO,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    Path("data").mkdir(exist_ok=True)
    Path("data/scores_editorial.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n  Scores por linha:")
    for linha, score in sorted(scores.items()):
        ativo = "✅ ATIVA" if score >= LIMIAR_ATIVACAO else "  inativa"
        print(f"    {linha}: {score:2d}/10  {ativo}")
    print(f"\n  {len(linhas_ativas)} linha(s) ativa(s): {linhas_ativas}")
    print("✅ scores_editorial.json salvo em data/")


if __name__ == "__main__":
    main()
