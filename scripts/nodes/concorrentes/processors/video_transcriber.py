"""
Processor: video_transcriber.py
================================
Tenta obter transcrição de vídeo YouTube via Captions API.
Fallback para título + descrição quando legendas indisponíveis.

Detecta Shorts via duração ISO 8601 (< 60s = Short).
"""

import isodate


def obter_transcricao(youtube, video_id: str, titulo: str, descricao: str) -> str:
    """
    Tenta baixar transcrição via YouTube Captions API.
    Fallback: retorna f"{titulo}. {descricao}" se legendas indisponíveis.
    Note: download de captions requer OAuth — com API key simples, o fallback
    é o caminho esperado na maioria dos casos.
    """
    try:
        resp = youtube.captions().list(
            part='snippet',
            videoId=video_id
        ).execute()
        itens = resp.get('items', [])

        # Prefere legenda em português; aceita qualquer idioma
        caption_id = None
        for item in itens:
            lang = item['snippet'].get('language', '')
            if lang.startswith('pt'):
                caption_id = item['id']
                break
        if not caption_id and itens:
            caption_id = itens[0]['id']

        if caption_id:
            conteudo = youtube.captions().download(
                id=caption_id,
                tfmt='srt'
            ).execute()
            # Remove timestamps do SRT e retorna texto limpo
            import re
            texto = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d+ --> \d{2}:\d{2}:\d{2},\d+\n', '', conteudo)
            texto = re.sub(r'\n{2,}', ' ', texto).strip()
            if texto:
                return texto
    except Exception:
        pass  # Fallback silencioso — comportamento esperado com API key simples

    # Fallback: título + descrição (idêntico ao 03_collect_youtube.py)
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
