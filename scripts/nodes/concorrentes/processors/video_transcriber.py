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
    Busca transcrição via youtube-transcript-api (não requer OAuth).
    Prefere português (pt, pt-BR); aceita qualquer idioma disponível.
    Fallback: retorna f"{titulo}. {descricao}" se nenhuma legenda disponível.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Prefere transcrição em português; aceita qualquer outro idioma
        transcript = None
        try:
            transcript = transcript_list.find_transcript(['pt', 'pt-BR', 'pt-br'])
        except NoTranscriptFound:
            try:
                # Tenta legenda gerada automaticamente em português
                transcript = transcript_list.find_generated_transcript(['pt', 'pt-BR', 'pt-br'])
            except NoTranscriptFound:
                # Pega qualquer transcrição disponível
                for t in transcript_list:
                    transcript = t
                    break

        if transcript:
            entries = transcript.fetch()
            # v1.x retorna TranscriptSnippet com atributo .text (não dict)
            texto = ' '.join(
                entry.text if hasattr(entry, 'text') else entry['text']
                for entry in entries
            ).strip()
            if texto:
                return texto

    except Exception:
        pass  # Fallback silencioso — canal sem legendas ou erro de rede

    # Fallback: título + descrição
    return f"{titulo}. {descricao}".strip()


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
