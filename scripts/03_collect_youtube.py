"""
SCRIPT 03 — Coleta YouTube (Concorrentes)
==========================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? SIM → Worker with API

O que faz:
  - Busca vídeos recentes sobre investimentos na B3
  - Foca em títulos e descrições (não transcrição — evita custos de API)
  - Salva em data/youtube_raw.json para o próximo script

Credenciais necessárias (GitHub Secrets):
  - YOUTUBE_API_KEY : chave do YouTube Data API v3 (Google Cloud Console)
                      Quota gratuita: 10.000 unidades/dia — mais que suficiente.
"""

import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from googleapiclient.discovery import build


# Termos de busca para encontrar conteúdo de concorrentes e inspiração
QUERIES_BUSCA = [
    "análise fundamentalista ações B3",
    "como analisar ações brasileiras",
    "indicadores financeiros P/L ROE",
    "value investing Brasil",
    "como identificar ação barata B3",
]


def salvar_resultado(dados: list, arquivo: str, edicao_id: str = None):
    """
    Persiste resultado localmente e no banco (se configurado).
    Retrocompatível: sem SUPABASE_URL, apenas salva o arquivo JSON.
    """
    Path('data').mkdir(exist_ok=True)
    Path(f'data/{arquivo}').write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    # Persistência no banco — ativa com SUPABASE_URL (Story 2.2)
    if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY'):
        try:
            from db_provider import get_client, _rotear_para_supabase
            supabase = get_client()
            if supabase:
                edicao_id = edicao_id or os.environ.get('EDICAO_ID')
                _rotear_para_supabase(supabase, dados, arquivo, edicao_id)
        except Exception as e:
            print(f'  ⚠️  Supabase indisponível ({e}) — continuando sem persistência')


def main():
    print("▶️  Iniciando coleta YouTube...")

    api_key = os.environ.get('YOUTUBE_API_KEY')
    if not api_key:
        print("⚠️  YOUTUBE_API_KEY não configurado. Pulando coleta YouTube.")
        Path('data').mkdir(exist_ok=True)
        Path('data/youtube_raw.json').write_text('[]')
        return

    service = build('youtube', 'v3', developerKey=api_key)
    limite = (datetime.now(tz=timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')

    videos = []
    vistos = set()  # Evita duplicatas

    for query in QUERIES_BUSCA:
        print(f"  Buscando: '{query}'")
        try:
            resposta = service.search().list(
                part='snippet',
                q=query,
                type='video',
                order='date',
                publishedAfter=limite,
                maxResults=10,
                relevanceLanguage='pt',
                regionCode='BR'
            ).execute()

            for item in resposta.get('items', []):
                video_id = item['id']['videoId']
                if video_id in vistos:
                    continue
                vistos.add(video_id)

                snippet = item['snippet']
                videos.append({
                    'fonte': 'youtube',
                    'canal': snippet.get('channelTitle', ''),
                    'titulo': snippet.get('title', ''),
                    'descricao': snippet.get('description', '')[:1000],
                    'data': snippet.get('publishedAt', ''),
                    'url': f"https://youtube.com/watch?v={video_id}",
                    'conteudo': f"{snippet.get('title', '')}\n\n{snippet.get('description', '')[:1000]}"
                })

        except Exception as e:
            print(f"    ⚠️  Erro na query '{query}': {e}")
            continue

    salvar_resultado(videos, 'youtube_raw.json')
    print(f"✅ {len(videos)} vídeos salvos em data/youtube_raw.json")


if __name__ == '__main__':
    main()
