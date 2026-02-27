"""
SCRIPT 05c — Execução dos Agentes de Linha
===========================================
Para cada linha editorial com score >= 6, instancia e executa um ReActAgent
com o clone correto, tool belt específico e critérios de parada da linha.

Salva resultado em data/conteudo_por_linha.json.

Posição no pipeline: após 05b_editorial_gate.py e APIs financeiras (04/04b),
antes de 06_generate.py.

Credenciais necessárias:
  - ANTHROPIC_API_KEY       : para os agentes de linha (claude-sonnet-4-6)
  - EXA_API_KEY             : WebSearchTool (linhas 2-6)
  - BRAPI_TOKEN             : BrapiQueryTool (linhas 1, 5)
  - FINTZ_API_KEY           : FintzQueryTool (linhas 1, 4)
  - TELEGRAM_BOT_TOKEN      : HumanFeedbackTool (linhas 3, 6)
  - TELEGRAM_CHAT_ID        : HumanFeedbackTool (linhas 3, 6)
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.react.line_agents import criar_agentes_linha, executar_agentes_linha


def _montar_contexto(triados: list) -> dict:
    """
    Monta o contexto passado para cada agente de linha.
    Usa até 15 itens mais relevantes do conteúdo triado.
    """
    partes = []
    for item in triados[:15]:
        triagem = item.get("triagem", {})
        partes.append(
            f"FONTE: {item.get('fonte', 'desconhecida')}\n"
            f"TÍTULO: {item.get('titulo', item.get('assunto', ''))}\n"
            f"RELEVÂNCIA: {triagem.get('relevancia', '')}\n"
            f"TEMAS: {', '.join(triagem.get('temas_identificados', []))}\n"
            f"ÂNGULO: {triagem.get('angulo_potencial_para_newsletter', '')}\n"
            f"RESUMO: {triagem.get('resumo_em_3_linhas', '')}"
        )

    resumo = "\n---\n".join(partes) if partes else "Sem conteúdo triado disponível."

    return {
        "task": (
            "Com base no conteúdo coletado e triado abaixo, gere material editorial "
            "de alta qualidade para a newsletter Fuja do Mico. Use suas ferramentas "
            "para enriquecer a análise quando necessário. Escreva em português."
        ),
        "conteudo_triado": resumo,
    }


def main() -> None:
    print("🤖 Iniciando execução dos agentes de linha...")

    path_scores = Path("data/scores_editorial.json")
    if not path_scores.exists():
        print("  ⚠️  data/scores_editorial.json não encontrado — pulando agentes de linha")
        return

    path_triado = Path("data/conteudo_triado.json")
    if not path_triado.exists():
        print("  ⚠️  data/conteudo_triado.json não encontrado — pulando agentes de linha")
        return

    scores_data = json.loads(path_scores.read_text(encoding="utf-8"))
    scores = scores_data.get("scores", {})
    linhas_ativas = scores_data.get("linhas_ativas", [])

    if not linhas_ativas:
        print("  ⚠️  Nenhuma linha ativa nos scores — pulando agentes de linha")
        return

    print(f"  Linhas ativas: {linhas_ativas}")

    triados = json.loads(path_triado.read_text(encoding="utf-8"))
    contexto = _montar_contexto(triados)

    agentes = criar_agentes_linha(scores, contexto)
    if not agentes:
        print("  ⚠️  Nenhum agente criado — pulando execução")
        return

    print(f"  {len(agentes)} agente(s) criado(s). Iniciando execução sequencial...")
    resultados = executar_agentes_linha(agentes, contexto)

    # Serializar AgentResult para JSON (campos primitivos)
    saida = {}
    for linha_id, resultado in resultados.items():
        saida[linha_id] = {
            "output": str(resultado.output) if resultado.output else "",
            "stop_reason": resultado.stop_reason,
            "confidence": resultado.confidence,
        }

    Path("data").mkdir(exist_ok=True)
    Path("data/conteudo_por_linha.json").write_text(
        json.dumps(saida, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n  Resultados por linha:")
    for linha_id, dados in saida.items():
        conf_pct = f"{dados['confidence']:.0%}"
        print(f"    {linha_id}: stop={dados['stop_reason']}, confiança={conf_pct}")

    print(f"✅ conteudo_por_linha.json salvo ({len(saida)} linha(s))")


if __name__ == "__main__":
    main()
