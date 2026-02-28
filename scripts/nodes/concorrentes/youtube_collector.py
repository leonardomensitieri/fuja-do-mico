"""
Node Concorrentes — YouTube Collector
======================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? SIM → Worker with API

O que faz:
  1. Lê canais configurados em config/concorrentes.json (campo "youtube")
  2. Para cada handle: obtém ultima_verificacao do Supabase (MAX data_captura)
  3. Resolve handle → uploads_playlist_id via channels().list()
  4. Lista vídeos novos via playlistItems().list() — 1 unidade de quota/página
  5. Busca duração via videos().list(contentDetails) para detectar Shorts
  6. Tenta transcrição via Captions API; fallback para título + descrição
  7. Aplica filtro @vowtz: exclui "shark tank", "react", "review"
  8. Grava cada vídeo em conteudo_raw individualmente

Credenciais necessárias (GitHub Secrets):
  - YOUTUBE_API_KEY    : YouTube Data API v3
  - SUPABASE_URL       : URL do projeto Supabase
  - SUPABASE_SERVICE_KEY: chave de serviço para leitura/escrita em conteudo_raw
"""

import os
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from googleapiclient.discovery import build

# Adiciona scripts/ ao path para importar db_provider
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from processors.video_transcriber import obter_transcricao, tipo_conteudo

# Termos excluídos para o canal @vowtz (AC 4)
VOWTZ_EXCLUSION_TERMS = ['shark tank', 'react', 'review']

# Arquivo de configuração de canais monitorados
CONFIG_PATH = Path('config/concorrentes.json')


def carregar_canais() -> list[dict]:
    """Carrega lista de canais YouTube de config/concorrentes.json."""
    if not CONFIG_PATH.exists():
        print(f'  ⚠️  {CONFIG_PATH} não encontrado — encerrando.')
        return []
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    return config.get('youtube', [])


def obter_ultima_verificacao(supabase, handle: str) -> str:
    """
    Retorna ultima_verificacao do canal via Supabase.
    MUST-FIX (Story 3.5 @po): GitHub Actions fresh checkout perde alterações
    em arquivos — ultima_verificacao DEVE vir do banco, não do JSON.
    Fallback: 7 dias atrás (primeira execução ou Supabase indisponível).
    """
    handle_clean = handle.lstrip('@')
    fallback = (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat()

    if not supabase:
        return fallback
    try:
        res = (
            supabase.table('conteudo_raw')
            .select('data_captura')
            .eq('fonte', 'youtube')
            .eq('conta_origem', handle_clean)
            .order('data_captura', desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]['data_captura']
    except Exception as e:
        print(f'  ⚠️  Erro ao consultar ultima_verificacao ({e}) — usando fallback 7 dias')
    return fallback


def resolver_uploads_playlist(youtube, handle: str) -> str | None:
    """
    Resolve handle (@primorico) → uploads_playlist_id dinamicamente.
    IDs de canal NUNCA hardcoded — resolver via API em cada execução.
    """
    try:
        resp = youtube.channels().list(
            part='contentDetails',
            forHandle=handle.lstrip('@')
        ).execute()
        itens = resp.get('items', [])
        if not itens:
            print(f'  ⚠️  Canal não encontrado: {handle}')
            return None
        return itens[0]['contentDetails']['relatedPlaylists']['uploads']
    except Exception as e:
        print(f'  ⚠️  Erro ao resolver canal {handle}: {e}')
        return None


def deve_excluir_vowtz(titulo: str, handle: str) -> bool:
    """Aplica filtro @vowtz: exclui vídeos com termos específicos (AC 4)."""
    if handle.lstrip('@').lower() != 'vowtz':
        return False
    titulo_lower = titulo.lower()
    return any(termo in titulo_lower for termo in VOWTZ_EXCLUSION_TERMS)


def coletar_canal(youtube, supabase, canal: dict) -> int:
    """
    Coleta vídeos novos de um canal e grava em conteudo_raw.
    Retorna número de vídeos gravados.
    """
    handle = canal['handle']
    handle_clean = handle.lstrip('@')
    ultima = obter_ultima_verificacao(supabase, handle)
    print(f'  Canal: {handle} | ultima_verificacao: {ultima[:19]}')

    playlist_id = resolver_uploads_playlist(youtube, handle)
    if not playlist_id:
        return 0

    gravados = 0
    page_token = None

    while True:
        kwargs = dict(
            part='snippet',
            playlistId=playlist_id,
            maxResults=50,
        )
        if page_token:
            kwargs['pageToken'] = page_token

        try:
            resp = youtube.playlistItems().list(**kwargs).execute()
        except Exception as e:
            print(f'  ⚠️  Erro ao listar playlist {handle}: {e}')
            break

        for item in resp.get('items', []):
            snippet = item['snippet']
            publicado_em = snippet.get('publishedAt', '')

            # Filtra apenas vídeos após ultima_verificacao (delta incremental)
            if publicado_em <= ultima:
                continue

            video_id = snippet.get('resourceId', {}).get('videoId', '')
            titulo = snippet.get('title', '')
            descricao = snippet.get('description', '')[:2000]
            url = f'https://youtube.com/watch?v={video_id}'

            # Filtro @vowtz (AC 4)
            if deve_excluir_vowtz(titulo, handle):
                print(f'    ⏭️  Excluído (@vowtz): {titulo[:60]}')
                continue

            # Busca duração para detectar Short
            duracao_iso = 'PT0S'
            try:
                vresp = youtube.videos().list(
                    part='contentDetails',
                    id=video_id
                ).execute()
                vitens = vresp.get('items', [])
                if vitens:
                    duracao_iso = vitens[0]['contentDetails'].get('duration', 'PT0S')
            except Exception:
                pass

            tipo = tipo_conteudo(duracao_iso)

            # Tenta transcrição; fallback para título + descrição (AC 3)
            conteudo = obter_transcricao(youtube, video_id, titulo, descricao)

            # Grava em conteudo_raw (AC 7)
            if supabase:
                try:
                    supabase.table('conteudo_raw').insert({
                        'fonte': 'youtube',
                        'plataforma': 'youtube',
                        'tipo_conteudo': tipo,
                        'conta_origem': handle_clean,
                        'conteudo_texto': conteudo[:8000],
                        'url_original': url,
                        'data_publicacao': publicado_em,
                        'processado': False,
                        'metadata': {
                            'titulo': titulo,
                            'video_id': video_id,
                            'duracao_iso': duracao_iso,
                            'handle': handle,
                        }
                    }).execute()
                    gravados += 1
                    print(f'    ✅ {tipo.upper()}: {titulo[:60]}')
                except Exception as e:
                    print(f'    ⚠️  Erro ao gravar {video_id}: {e}')

        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    return gravados


def main():
    print('📺 Iniciando Node Concorrentes — YouTube Collector...')

    api_key = os.environ.get('YOUTUBE_API_KEY')
    if not api_key:
        print('⚠️  YOUTUBE_API_KEY não configurado — encerrando.')
        return

    if not (os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY')):
        print('⚠️  SUPABASE_URL ou SUPABASE_SERVICE_KEY não configurados — encerrando.')
        return

    from db_provider import get_client
    supabase = get_client()
    if not supabase:
        print('⚠️  Falha ao conectar ao Supabase — encerrando.')
        return

    youtube = build('youtube', 'v3', developerKey=api_key)
    canais = carregar_canais()

    if not canais:
        print('  Pool de canais vazio — encerrando.')
        return

    total = 0
    for canal in canais:
        gravados = coletar_canal(youtube, supabase, canal)
        total += gravados
        print(f'  → {gravados} vídeos gravados de {canal["handle"]}')

    print(f'\n✅ Total: {total} vídeos novos gravados em conteudo_raw.')


if __name__ == '__main__':
    main()
