"""
Processor: video_transcriber.py
================================
Obtém transcrição de vídeo YouTube via youtube-transcript-api (sem OAuth).
Fallback para título + descrição quando legendas indisponíveis.

Detecta Shorts via duração ISO 8601 (< 60s = Short).
"""

import isodate


def obter_transcricao(youtube, video_id: str, titulo: str, descricao: str) -> str:
    """
    Busca transcrição via youtube-transcript-api.get_transcript() — API mais
    simples e estável entre v0.x e v1.x. Tenta pt, pt-BR e en nessa ordem.
    Fallback: retorna f"{titulo}. {descricao}" se nenhuma legenda disponível.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        entradas = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=['pt', 'pt-BR', 'pt-br', 'en']
        )
        # Compatível com v0.x (dict) e v1.x (objeto com .text)
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
