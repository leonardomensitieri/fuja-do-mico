"""
Processor: video_transcriber.py
================================
Obtém transcrição de vídeo YouTube via youtube-transcript-api.
Usa proxy residencial Apify para contornar bloqueio de IPs cloud (GitHub Actions).
Fallback para título + descrição quando legendas indisponíveis.

Detecta Shorts via duração ISO 8601 (< 60s = Short).
"""

import os
import isodate


def obter_transcricao(youtube, video_id: str, titulo: str, descricao: str) -> str:
    """
    Busca transcrição via youtube-transcript-api v1.x.
    Se APIFY_API_TOKEN disponível, roteia pelo proxy residencial Apify
    para contornar o bloqueio de IPs de cloud providers (GitHub Actions).
    Fallback: retorna título + descrição se nenhuma legenda disponível.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.proxies import GenericProxiesConfig

        apify_token = os.environ.get('APIFY_API_TOKEN')
        if apify_token:
            # Proxy residencial Apify — não bloqueado pelo YouTube
            proxy_url = f'http://auto:{apify_token}@proxy.apify.com:8000'
            proxies_config = GenericProxiesConfig(
                http_url=proxy_url,
                https_url=proxy_url,
            )
            api = YouTubeTranscriptApi(proxies=proxies_config)
        else:
            api = YouTubeTranscriptApi()

        entradas = api.fetch(video_id, languages=['pt', 'pt-BR', 'pt-br', 'en'])
        texto = ' '.join(
            e.text if hasattr(e, 'text') else e['text']
            for e in entradas
        ).strip()
        if texto:
            return texto

    except Exception as e:
        print(f'    ⚠️  Transcrição falhou ({video_id}): {type(e).__name__}: {e}')

    return f"{titulo}\n\n{descricao}".strip()


def is_short(duration_iso: str) -> bool:
    """Retorna True se vídeo durar menos de 60 segundos (YouTube Short)."""
    try:
        duration = isodate.parse_duration(duration_iso)
        return duration.total_seconds() < 60
    except Exception:
        return False


def tipo_conteudo(duration_iso: str) -> str:
    """Retorna 'short' ou 'video' baseado na duração."""
    return 'short' if is_short(duration_iso) else 'video'
