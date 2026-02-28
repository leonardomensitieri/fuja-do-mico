"""
Node Concorrentes — Twitter/X Collector
=========================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? SIM → Worker with API

O que faz:
  1. Lê handles de config/concorrentes.json (campo "twitter")
  2. Para cada handle: obtém ultima_verificacao do Supabase (MAX data_captura)
  3. Coleta tweets via Apify apify/twitter-scraper por handle
  4. Filtra apenas tweets após ultima_verificacao (delta incremental)
  5. Grava cada tweet em conteudo_raw individualmente

Credenciais necessárias (GitHub Secrets):
  - APIFY_API_TOKEN     : token Apify
  - SUPABASE_URL        : URL do projeto Supabase
  - SUPABASE_SERVICE_KEY: chave de serviço

Nota: handles verificados durante implementação (AC 4) — apenas contas
existentes e ativas em config/concorrentes.json (campo "twitter").
"""

import os
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dateutil import parser as dateutil_parser

# Adiciona scripts/ ao path para importar db_provider
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

APIFY_BASE_URL = 'https://api.apify.com/v2'
CONFIG_PATH = Path('config/concorrentes.json')


def carregar_handles() -> list[str]:
    """Carrega handles Twitter/X de config/concorrentes.json."""
    if not CONFIG_PATH.exists():
        print(f'  ⚠️  {CONFIG_PATH} não encontrado — encerrando.')
        return []
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    return config.get('twitter', [])


def obter_ultima_verificacao(supabase, handle: str) -> str:
    """
    MUST-FIX (Story 3.6 @po): ultima_verificacao via Supabase.
    GitHub Actions fresh checkout perde alterações em arquivos locais.
    Fallback: 7 dias atrás (primeira execução ou Supabase indisponível).
    """
    fallback = (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat()
    if not supabase:
        return fallback
    try:
        res = (
            supabase.table('conteudo_raw')
            .select('data_captura')
            .eq('fonte', 'twitter')
            .eq('conta_origem', handle.lstrip('@'))
            .order('data_captura', desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]['data_captura']
    except Exception as e:
        print(f'  ⚠️  Erro ao consultar ultima_verificacao ({e}) — usando fallback 7 dias')
    return fallback


def _normalizar_data(valor: str) -> str:
    """Converte timestamp para ISO 8601 com timezone."""
    if not valor:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = dateutil_parser.parse(valor)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _rodar_actor(actor_id: str, input_data: dict) -> list:
    """Executa Actor Apify de forma síncrona e retorna itens do dataset."""
    token = os.environ.get('APIFY_API_TOKEN', '')
    url = f'{APIFY_BASE_URL}/acts/{actor_id}/run-sync-get-dataset-items'
    resp = requests.post(
        url,
        params={'token': token},
        json=input_data,
        timeout=300,
    )
    resp.raise_for_status()
    dados = resp.json()
    return dados if isinstance(dados, list) else dados.get('items', [])


def coletar_handle(supabase, handle: str) -> int:
    """
    Coleta tweets novos de um handle e grava em conteudo_raw.
    Retorna número de tweets gravados.
    """
    handle_clean = handle.lstrip('@')
    ultima = obter_ultima_verificacao(supabase, handle_clean)
    print(f'  Handle: @{handle_clean} | ultima_verificacao: {ultima[:19]}')

    try:
        itens = _rodar_actor(
            'apify/twitter-scraper',
            {
                'twitterHandles': [handle_clean],
                'maxItems': 50,
                'sort': 'Latest',
            }
        )
    except Exception as e:
        print(f'  ⚠️  Apify falhou para @{handle_clean}: {e}')
        return 0

    gravados = 0
    for item in itens:
        autor_obj = item.get('author', {}) or {}
        data_tweet = _normalizar_data(item.get('createdAt', ''))

        # Filtra apenas tweets após ultima_verificacao (delta incremental)
        if data_tweet <= ultima:
            continue

        texto = item.get('text', '') or item.get('fullText', '') or ''
        url = item.get('url', '') or ''

        if not supabase:
            continue

        try:
            supabase.table('conteudo_raw').insert({
                'fonte': 'twitter',
                'plataforma': 'twitter',
                'tipo_conteudo': 'tweet',
                'conta_origem': handle_clean,
                'conteudo_texto': texto[:8000],
                'url_original': url,
                'data_publicacao': data_tweet,
                'processado': False,
                'metadata': {
                    'like_count': item.get('likeCount', 0),
                    'retweet_count': item.get('retweetCount', 0),
                    'reply_count': item.get('replyCount', 0),
                    'author_username': autor_obj.get('userName', handle_clean),
                }
            }).execute()
            gravados += 1
            print(f'    ✅ TWEET: {texto[:60]}')
        except Exception as e:
            print(f'  ⚠️  Erro ao gravar tweet: {e}')

    return gravados


def main():
    print('🐦 Iniciando Node Concorrentes — Twitter/X Collector...')

    if not os.environ.get('APIFY_API_TOKEN'):
        print('⚠️  APIFY_API_TOKEN não configurado — encerrando.')
        return

    if not (os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY')):
        print('⚠️  SUPABASE_URL ou SUPABASE_SERVICE_KEY não configurados — encerrando.')
        return

    from db_provider import get_client
    supabase = get_client()
    if not supabase:
        print('⚠️  Falha ao conectar ao Supabase — encerrando.')
        return

    handles = carregar_handles()
    if not handles:
        print('  Pool de handles vazio — encerrando.')
        return

    total = 0
    for handle in handles:
        gravados = coletar_handle(supabase, handle)
        total += gravados
        print(f'  → {gravados} tweets gravados de @{handle.lstrip("@")}')

    print(f'\n✅ Total: {total} tweets novos gravados em conteudo_raw.')


if __name__ == '__main__':
    main()
