"""
SCRIPT 10 — Coleta de Conteúdo Social (Instagram e Twitter/X)
==============================================================
Decision Tree: Worker Script com External API — chamada não-bloqueante

O que faz:
  - Lê os perfis de newsletters financeiras de SOCIAL_PROFILES (env)
  - Coleta posts públicos do Instagram via Actor apify/instagram-scraper
  - Coleta tweets públicos do Twitter/X via Actor apify/twitter-scraper
  - Transforma o output Apify no schema social_raw.json (compatível com rss_raw.json)
  - Salva em data/social_raw.json para consumo pelo script 05_triage.py

Integração no pipeline:
  - Chamada não-bloqueante: falha não aborta o pipeline principal
  - Apenas ativado se APIFY_API_TOKEN estiver configurado
  - 05_triage.py lê social_raw.json como fonte adicional sem modificações

Actors Apify utilizados:
  - Instagram : apify/instagram-scraper  (~$1.50/1000 posts)
  - Twitter/X : apify/twitter-scraper    (~$0.50/1000 tweets)
  - Custo total por execução: ~$0.05 (25 posts/rede) — dentro do NFR1 ($0.20/edição)

Campos do social_raw.json (idêntico ao rss_raw.json):
  - fonte    : "instagram:{handle}" ou "twitter:{handle}"
  - titulo   : primeiros 120 chars do caption/tweet
  - resumo   : caption/tweet truncado a 500 chars
  - link     : URL do post/tweet
  - data     : ISO 8601 com timezone
  - conteudo : texto completo
  - _social_meta : {tipo, autor, likes, [retweets, replies]} (suplementar)

Credenciais necessárias (GitHub Secrets):
  - APIFY_API_TOKEN  : token da conta Apify (obrigatório)
  - SOCIAL_PROFILES  : JSON com handles por rede (opcional — usa default interno)
  - SOCIAL_MAX_POSTS : máximo de posts por rede (opcional — default 25)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────

APIFY_BASE_URL = 'https://api.apify.com/v2'

# Perfis padrão de newsletters financeiras brasileiras
_PERFIS_DEFAULT = {
    'instagram': ['sunoresearch', 'infomoney', 'moneytimes_br'],
    'twitter': ['ValorEcon', 'infomoney', 'sunoresearch'],
}


def carregar_perfis() -> dict:
    """
    Lê os perfis de redes sociais do ambiente.
    Retorna dict com listas de handles por rede.
    Usa default interno se SOCIAL_PROFILES não configurado.
    """
    perfis_raw = os.environ.get('SOCIAL_PROFILES', '')

    if not perfis_raw:
        print('  ℹ️  SOCIAL_PROFILES não configurado — usando perfis padrão')
        return _PERFIS_DEFAULT

    try:
        perfis = json.loads(perfis_raw)
        # Garantir que as chaves esperadas existem
        perfis.setdefault('instagram', _PERFIS_DEFAULT['instagram'])
        perfis.setdefault('twitter', _PERFIS_DEFAULT['twitter'])
        return perfis
    except json.JSONDecodeError as e:
        print(f'  ⚠️  SOCIAL_PROFILES inválido ({e}) — usando perfis padrão')
        return _PERFIS_DEFAULT


def _max_posts() -> int:
    """Retorna o máximo de posts por rede (default 25)."""
    try:
        return int(os.environ.get('SOCIAL_MAX_POSTS', '25'))
    except ValueError:
        return 25


# ──────────────────────────────────────────────────────────────
# CHAMADA À API REST DO APIFY
# ──────────────────────────────────────────────────────────────

def _rodar_actor(actor_id: str, input_data: dict) -> list:
    """
    Executa um Actor Apify de forma síncrona e retorna os itens do dataset.
    Usa o endpoint run-sync-get-dataset-items para aguardar o resultado
    diretamente, sem polling.

    Timeout de 5 minutos por rede — retorna lista vazia em caso de falha.
    """
    token = os.environ.get('APIFY_API_TOKEN', '')
    if not token:
        raise ValueError('APIFY_API_TOKEN não configurado')

    url = f'{APIFY_BASE_URL}/acts/{actor_id}/run-sync-get-dataset-items'

    resp = requests.post(
        url,
        params={'token': token},
        json=input_data,
        timeout=300,  # 5 minutos máximo por rede
    )
    resp.raise_for_status()

    dados = resp.json()
    # Apify retorna lista diretamente ou objeto com campo 'items'
    if isinstance(dados, list):
        return dados
    return dados.get('items', [])


# ──────────────────────────────────────────────────────────────
# COLETA POR REDE
# ──────────────────────────────────────────────────────────────

def coletar_instagram(perfis: list, max_posts: int) -> list:
    """
    Coleta posts públicos de perfis do Instagram via apify/instagram-scraper.
    Retorna lista de posts transformados para o schema social_raw.json.
    """
    if not perfis:
        print('  ℹ️  Nenhum perfil Instagram configurado — pulando')
        return []

    print(f'  📸 Coletando Instagram: {perfis} (max {max_posts}/rede)...')

    try:
        itens_brutos = _rodar_actor(
            'apify/instagram-scraper',
            {
                'usernames': [h.lstrip('@') for h in perfis],
                'resultsLimit': max_posts,
                'resultsType': 'posts',
            }
        )
        print(f'    ✅ Instagram: {len(itens_brutos)} posts coletados')
        return transformar_para_raw(itens_brutos, 'instagram')

    except Exception as e:
        print(f'    ⚠️  Instagram falhou ({e}) — continuando sem dados do Instagram')
        return []


def coletar_twitter(perfis: list, max_posts: int) -> list:
    """
    Coleta tweets públicos de perfis do Twitter/X via apify/twitter-scraper.
    Retorna lista de tweets transformados para o schema social_raw.json.
    """
    if not perfis:
        print('  ℹ️  Nenhum perfil Twitter configurado — pulando')
        return []

    print(f'  🐦 Coletando Twitter/X: {perfis} (max {max_posts}/rede)...')

    try:
        itens_brutos = _rodar_actor(
            'apify/twitter-scraper',
            {
                'twitterHandles': [h.lstrip('@') for h in perfis],
                'maxItems': max_posts,
                'sort': 'Latest',
            }
        )
        print(f'    ✅ Twitter: {len(itens_brutos)} tweets coletados')
        return transformar_para_raw(itens_brutos, 'twitter')

    except Exception as e:
        print(f'    ⚠️  Twitter/X falhou ({e}) — continuando sem dados do Twitter')
        return []


# ──────────────────────────────────────────────────────────────
# TRANSFORMAÇÃO PARA SCHEMA SOCIAL_RAW.JSON
# ──────────────────────────────────────────────────────────────

def _normalizar_data(valor: str) -> str:
    """
    Converte timestamp para ISO 8601 com timezone.
    Retorna string vazia se não for possível converter.
    """
    if not valor:
        return datetime.now(timezone.utc).isoformat()

    try:
        # Tenta parse direto (já pode estar em ISO 8601)
        from dateutil import parser as dateutil_parser
        dt = dateutil_parser.parse(valor)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _transformar_instagram(item: dict) -> dict:
    """Transforma um post do Instagram (output Apify) para social_raw.json."""
    caption = item.get('caption', '') or ''
    autor = (item.get('ownerUsername', '') or '').lower()
    url = item.get('url', '') or item.get('shortCode', '')
    if url and not url.startswith('http'):
        url = f'https://www.instagram.com/p/{url}/'

    titulo = caption[:120].strip() or 'Post sem legenda'
    resumo = caption[:500].strip()

    return {
        'fonte': f'instagram:{autor}',
        'titulo': titulo,
        'resumo': resumo,
        'link': url,
        'data': _normalizar_data(item.get('timestamp', '')),
        'conteudo': caption,
        '_social_meta': {
            'tipo': 'instagram',
            'autor': autor,
            'likes': item.get('likesCount', 0),
            'comentarios': item.get('commentsCount', 0),
        },
    }


def _transformar_twitter(item: dict) -> dict:
    """Transforma um tweet (output Apify) para social_raw.json."""
    texto = item.get('text', '') or item.get('fullText', '') or ''
    autor_obj = item.get('author', {}) or {}
    autor = (autor_obj.get('userName', '') or '').lower()
    url = item.get('url', '') or ''

    titulo = texto[:120].strip() or 'Tweet sem texto'
    resumo = texto[:500].strip()

    return {
        'fonte': f'twitter:{autor}',
        'titulo': titulo,
        'resumo': resumo,
        'link': url,
        'data': _normalizar_data(item.get('createdAt', '')),
        'conteudo': texto,
        '_social_meta': {
            'tipo': 'twitter',
            'autor': autor,
            'likes': item.get('likeCount', 0),
            'retweets': item.get('retweetCount', 0),
            'replies': item.get('replyCount', 0),
        },
    }


def transformar_para_raw(itens: list, tipo: str) -> list:
    """
    Converte lista de itens do Apify para o schema social_raw.json.
    Filtra itens sem conteúdo útil.
    """
    transformados = []
    transformador = _transformar_instagram if tipo == 'instagram' else _transformar_twitter

    for item in itens:
        try:
            raw = transformador(item)
            # Filtra posts sem conteúdo (caption/tweet vazio)
            if raw.get('conteudo') or raw.get('titulo') != 'Post sem legenda':
                transformados.append(raw)
        except Exception as e:
            print(f'    ⚠️  Erro ao transformar item {tipo}: {e}')
            continue

    return transformados


# ──────────────────────────────────────────────────────────────
# PERSISTÊNCIA
# ──────────────────────────────────────────────────────────────

def salvar_resultado(dados: list, arquivo: str, edicao_id: str = None):
    """
    Persiste resultado localmente e no banco (se configurado).
    Extensível: Supabase ativado via SUPABASE_URL + SUPABASE_SERVICE_KEY.
    """
    Path('data').mkdir(exist_ok=True)
    Path(f'data/{arquivo}').write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    # Persistência no banco (ativa com SUPABASE_URL — Story 2.2):
    if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY'):
        try:
            _scripts_dir = str(Path(__file__).resolve().parent)
            if _scripts_dir not in sys.path:
                sys.path.insert(0, _scripts_dir)
            from db_provider import get_client, _rotear_para_supabase
            supabase = get_client()
            if supabase:
                edicao_id = edicao_id or os.environ.get('EDICAO_ID')
                _rotear_para_supabase(supabase, dados, arquivo, edicao_id)
        except Exception as e:
            print(f'  ⚠️  Supabase indisponível ({e}) — continuando sem persistência')


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def main():
    print('📱 Iniciando coleta de conteúdo social...')

    token = os.environ.get('APIFY_API_TOKEN', '')
    if not token:
        print('  ❌ APIFY_API_TOKEN não configurado — script encerrado')
        sys.exit(1)

    perfis = carregar_perfis()
    max_posts = _max_posts()
    print(f'  Perfis: {perfis}')
    print(f'  Max posts/rede: {max_posts}')

    todos = []

    # Coleta Instagram (falha isolada — não impede Twitter)
    posts_instagram = coletar_instagram(
        perfis.get('instagram', []),
        max_posts
    )
    todos.extend(posts_instagram)

    # Coleta Twitter (falha isolada — não impede Instagram)
    tweets_twitter = coletar_twitter(
        perfis.get('twitter', []),
        max_posts
    )
    todos.extend(tweets_twitter)

    print(f'\n  📊 Total coletado: {len(todos)} itens '
          f'(Instagram: {len(posts_instagram)}, Twitter: {len(tweets_twitter)})')

    salvar_resultado(todos, 'social_raw.json')
    print('✅ Conteúdo social salvo em data/social_raw.json')


if __name__ == '__main__':
    main()
