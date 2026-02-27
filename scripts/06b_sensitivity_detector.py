"""
SCRIPT 06b — Detector de Sensibilidade
=======================================
Decision Tree: Worker Script — chama Claude Haiku para classificar sensibilidade

O que faz:
  - Lê data/conteudo_gerado.json e extrai todo o texto relevante
  - Envia o texto ao Claude Haiku para classificação de sensibilidade
  - Salva data/sensibilidade_flag.json com nivel, flags, disclaimer e timestamp
  - É não-bloqueante: qualquer falha gera aviso, pipeline continua

Níveis de sensibilidade (definidos no dossiê seção 8.3):
  ALTO  — flag obrigatório no Telegram
  MÉDIO — disclaimer automático adicionado à mensagem Telegram
  NENHUM — comportamento padrão mantido

Posição no pipeline:
  06_generate.py → data/conteudo_gerado.json
  06b (ESTE SCRIPT)  → data/sensibilidade_flag.json
  07_populate_template.py
  08_notify.py → lê sensibilidade_flag.json para montar mensagem
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic


_PROMPT_DETECTOR = """
Você é um auditor de conformidade editorial de uma newsletter financeira.
Analise o texto abaixo e classifique o nível de sensibilidade:

NÍVEL ALTO (flag obrigatório):
- Recomendação direta de compra/venda com ticker E preço-alvo específico
- Menção a processo judicial em andamento com partes identificadas por nome
- Promessa de retorno garantido ou percentual específico
- Crítica nominal a gestor, analista ou instituição identificável

NÍVEL MÉDIO (disclaimer automático):
- Análise que pode ser interpretada como recomendação implícita
- Dados de balanço não confirmados por fonte oficial
- Projeção de resultado futuro sem base explícita
- Menção a rumor de mercado sem fonte verificável

Retorne SOMENTE um JSON válido:
{
  "nivel": "alto" | "medio" | "nenhum",
  "flags": ["descrição do item detectado"],
  "disclaimer": "texto do disclaimer se nivel=medio, vazio se outro"
}

Texto a analisar:
{texto}
"""


def extrair_texto_gerado(conteudo: dict) -> str:
    """Extrai todo o texto relevante das sections[] e do editorial."""
    partes = []
    if conteudo.get('editorial'):
        partes.append(conteudo['editorial'])
    for section in conteudo.get('sections', []):
        for campo in ['title', 'content', 'body', 'text', 'items']:
            if campo in section:
                valor = section[campo]
                partes.append(str(valor) if not isinstance(valor, list) else '\n'.join(str(i) for i in valor))
    return '\n\n'.join(partes)


def detectar_sensibilidade(texto: str, cliente: anthropic.Anthropic) -> dict:
    """Usa Claude Haiku para classificar sensibilidade do texto gerado."""
    prompt = _PROMPT_DETECTOR.replace('{texto}', texto[:8000])  # Limita tokens
    try:
        resposta = cliente.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=512,
            messages=[{'role': 'user', 'content': prompt}]
        )
        texto_resp = resposta.content[0].text.strip()
        inicio = texto_resp.find('{')
        fim = texto_resp.rfind('}') + 1
        resultado = json.loads(texto_resp[inicio:fim])
        # Normaliza e valida nivel
        nivel = resultado.get('nivel', 'nenhum')
        if nivel not in ('alto', 'medio', 'nenhum'):
            nivel = 'nenhum'
        return {
            'nivel': nivel,
            'flags': resultado.get('flags', []),
            'disclaimer': resultado.get('disclaimer', ''),
        }
    except Exception as e:
        print(f'  ⚠️  Detector de sensibilidade falhou: {e} — assumindo nenhum')
        return {'nivel': 'nenhum', 'flags': [], 'disclaimer': ''}


def main() -> None:
    print('🔍 Executando Detector de Sensibilidade...')

    path_gerado = Path('data/conteudo_gerado.json')
    if not path_gerado.exists():
        print('  ⚠️  data/conteudo_gerado.json não encontrado — pulando detector')
        return

    conteudo = json.loads(path_gerado.read_text(encoding='utf-8'))
    texto = extrair_texto_gerado(conteudo)

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    cliente = anthropic.Anthropic(api_key=api_key)
    resultado = detectar_sensibilidade(texto, cliente)

    saida = {
        **resultado,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }

    Path('data').mkdir(exist_ok=True)
    Path('data/sensibilidade_flag.json').write_text(
        json.dumps(saida, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    nivel = saida['nivel']
    icone = '🔴' if nivel == 'alto' else ('🟡' if nivel == 'medio' else '🟢')
    print(f'  {icone} Nível de sensibilidade: {nivel.upper()}')
    if saida['flags']:
        for flag in saida['flags']:
            print(f'    • {flag}')
    print('✅ sensibilidade_flag.json salvo em data/')


if __name__ == '__main__':
    main()
