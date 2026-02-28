"""
Node Concorrentes — Instagram Collector
=========================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? SIM → Worker with API

O que faz:
  1. Lê contas configuradas em config/concorrentes.json (campo "instagram")
  2. Para cada conta: obtém ultima_verificacao do Supabase (MAX data_captura)
  3. Coleta posts novos via Apify apify/instagram-scraper por conta específica
  4. Carrosséis (type == "Sidecar"): processa cada slide via carousel_vision.py
  5. Grava cada post em conteudo_raw individualmente

Credenciais necessárias (GitHub Secrets):
  - APIFY_API_TOKEN     : token Apify
  - ANTHROPIC_API_KEY   : para carousel_vision (Claude Vision)
  - SUPABASE_URL        : URL do projeto Supabase
  - SUPABASE_SERVICE_KEY: chave de serviço
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
from processors.carousel_vision import processar_carrossel

APIFY_BASE_URL = 'https://api.apify.com/v2'
CONFIG_PATH = Path('config/concorrentes.json')


def carregar_contas() -> list[str]:
    """Carrega contas Instagram de config/concorrentes.json."""
    if not CONFIG_PATH.exists():
        print(f'  ⚠️  {CONFIG_PATH} não encontrado — encerrando.')
        return []
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    return config.get('instagram', [])


def obter_ultima_verificacao(supabase, conta: str) -> str:
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
            .eq('fonte', 'instagram')
            .eq('conta_origem', conta.lstrip('@'))
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


def coletar_conta(supabase, anthropic_client, conta: str) -> int:
    """
    Coleta posts novos de uma conta Instagram e grava em conteudo_raw.
    Retorna número de posts gravados.
    """
    conta_clean = conta.lstrip('@')
    ultima = obter_ultima_verificacao(supabase, conta_clean)
    print(f'  Conta: @{conta_clean} | ultima_verificacao: {ultima[:19]}')

    try:
        itens = _rodar_actor(
            'apify/instagram-scraper',
            {
                'usernames': [conta_clean],
                'resultsLimit': 50,
                'resultsType': 'posts',
            }
        )
    except Exception as e:
        print(f'  ⚠️  Apify falhou para @{conta_clean}: {e}')
        return 0

    gravados = 0
    for item in itens:
        data_post = _normalizar_data(item.get('timestamp', ''))

        # Filtra apenas posts após ultima_verificacao (delta incremental)
        if data_post <= ultima:
            continue

        caption = item.get('caption', '') or ''
        tipo_post = item.get('type', 'Image')
        url = item.get('url', '') or item.get('shortCode', '')
        if url and not url.startswith('http'):
            url = f'https://www.instagram.com/p/{url}/'

        # Carrossel: extrai texto de cada slide via Claude Vision (AC 2)
        if tipo_post == 'Sidecar' and anthropic_client:
            conteudo = processar_carrossel(item, anthropic_client)
            tipo_conteudo = 'carrossel'
        else:
            conteudo = caption
            tipo_conteudo = 'post'

        if not supabase:
            continue

        try:
            # Usa primeira linha da caption como título (máx 120 chars)
            titulo = (caption.split('\n')[0] or caption)[:120]
            supabase.table('conteudo_raw').insert({
                'fonte': 'instagram',
                'plataforma': 'instagram',
                'tipo_conteudo': tipo_conteudo,
                'titulo': titulo,
                'conta_origem': conta_clean,
                'conteudo_texto': conteudo[:8000],
                'url_original': url,
                'data_publicacao': data_post,
                'processado': False,
                'metadata': {
                    'tipo_post': tipo_post,
                    'likes': item.get('likesCount', 0),
                    'num_slides': len(item.get('images', [])) if tipo_post == 'Sidecar' else 1,
                }
            }).execute()
            gravados += 1
            print(f'    ✅ {tipo_conteudo.upper()}: {caption[:60]}')
        except Exception as e:
            print(f'  ⚠️  Erro ao gravar post: {e}')

    return gravados


def main():
    print('📸 Iniciando Node Concorrentes — Instagram Collector...')

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

    # Claude Vision para carrosséis (opcional — sem chave, usa caption como fallback)
    anthropic_client = None
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if api_key:
        import anthropic
        anthropic_client = anthropic.Anthropic(api_key=api_key)
    else:
        print('  ℹ️  ANTHROPIC_API_KEY ausente — carrosséis usarão caption como fallback')

    contas = carregar_contas()
    if not contas:
        print('  Pool de contas vazio — encerrando.')
        return

    total = 0
    for conta in contas:
        gravados = coletar_conta(supabase, anthropic_client, conta)
        total += gravados
        print(f'  → {gravados} posts gravados de @{conta.lstrip("@")}')

    print(f'\n✅ Total: {total} posts novos gravados em conteudo_raw.')


if __name__ == '__main__':
    main()
