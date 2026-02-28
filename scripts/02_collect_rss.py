"""
SCRIPT 02 — Coleta de RSS (Notícias e Research)
================================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? SIM → Worker with API

O que faz:
  - Lê os feeds RSS configurados em config/rss_feeds.txt
  - Filtra apenas itens publicados nos últimos 7 dias
  - Grava cada artigo individualmente em conteudo_raw (Story 3.2)
  - Salva em data/rss_raw.json para o próximo script (fallback pipeline semanal)

Credenciais necessárias (opcionais — sem elas, só salva JSON local):
  - SUPABASE_URL        : URL do projeto Supabase
  - SUPABASE_SERVICE_KEY: chave de serviço para gravação em conteudo_raw
"""

import os
import json
import feedparser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import mktime
from urllib.parse import urlparse


# Feeds RSS de portais financeiros brasileiros
# Edite config/rss_feeds.txt para adicionar/remover fontes
RSS_FEEDS_PADRAO = [
    "https://www.infomoney.com.br/feed/",
    "https://exame.com/investimentos/feed/",
    "https://www.moneytimes.com.br/feed/",
    "https://einvestidor.estadao.com.br/feed/",
    "https://www.suno.com.br/noticias/feed/",
    "https://valoreconomico.com.br/rss/ultimas-noticias.xml",
]


def carregar_feeds() -> list[str]:
    """Carrega feeds de config/rss_feeds.txt ou usa os padrão."""
    config_path = Path('config/rss_feeds.txt')
    if config_path.exists():
        feeds = [linha.strip() for linha in config_path.read_text().splitlines()
                 if linha.strip() and not linha.startswith('#')]
        return feeds if feeds else RSS_FEEDS_PADRAO
    return RSS_FEEDS_PADRAO


def data_entry(entry) -> datetime | None:
    """Extrai data de publicação de um item RSS."""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        return datetime.fromtimestamp(mktime(entry.updated_parsed), tz=timezone.utc)
    return None


def gravar_em_conteudo_raw(supabase, item: dict, url_feed: str = ''):
    """
    Grava um artigo RSS individualmente em conteudo_raw (Story 3.2).
    Não substitui a gravação em conteudo_coletado — operação aditiva.
    """
    if not supabase:
        return
    try:
        # Extrai domínio do feed como conta_origem (ex: 'infomoney.com.br')
        dominio = urlparse(url_feed).netloc.replace('www.', '') if url_feed else ''
        supabase.table('conteudo_raw').insert({
            'fonte': 'rss',
            'plataforma': 'web',
            'tipo_conteudo': 'artigo',
            'conta_origem': dominio,
            'conteudo_texto': item.get('conteudo', ''),
            'url_original': item.get('link', ''),
            'data_publicacao': item.get('data') or None,
            'processado': False,
            'metadata': {'titulo': item.get('titulo', ''), 'feed_url': url_feed}
        }).execute()
    except Exception as e:
        print(f'  ⚠️  Erro ao gravar em conteudo_raw ({e}) — continuando')


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
    print("📰 Iniciando coleta de feeds RSS...")

    # Inicializa cliente Supabase para gravação em conteudo_raw (Story 3.2)
    supabase = None
    if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY'):
        try:
            from db_provider import get_client
            supabase = get_client()
        except Exception as e:
            print(f'  ⚠️  Supabase indisponível ({e}) — gravando apenas JSON local')

    feeds = carregar_feeds()
    limite = datetime.now(tz=timezone.utc) - timedelta(days=7)
    artigos = []
    gravados_raw = 0

    for url in feeds:
        print(f"  Processando: {url}")
        try:
            feed = feedparser.parse(url)
            fonte = feed.feed.get('title', url)
            novos = 0

            for entry in feed.entries:
                data = data_entry(entry)

                # Filtra por data (últimos 7 dias)
                if data and data < limite:
                    continue

                titulo = entry.get('title', '')
                resumo = entry.get('summary', '') or entry.get('description', '')
                link = entry.get('link', '')

                # Limpa HTML do resumo
                import re
                resumo_limpo = re.sub(r'<[^>]+>', ' ', resumo)
                resumo_limpo = re.sub(r'\s+', ' ', resumo_limpo).strip()

                if titulo and resumo_limpo:
                    artigo = {
                        'fonte': f'rss:{fonte}',
                        'titulo': titulo,
                        'resumo': resumo_limpo[:2000],
                        'link': link,
                        'data': data.isoformat() if data else '',
                        'conteudo': f"{titulo}\n\n{resumo_limpo}"
                    }
                    artigos.append(artigo)

                    # Grava individualmente em conteudo_raw (Story 3.2)
                    gravar_em_conteudo_raw(supabase, artigo, url_feed=url)
                    if supabase:
                        gravados_raw += 1

                    novos += 1

            print(f"    → {novos} artigos novos")

        except Exception as e:
            print(f"    ⚠️  Erro ao processar {url}: {e}")
            continue

    if supabase:
        print(f"  📥 {gravados_raw} artigos gravados em conteudo_raw")

    salvar_resultado(artigos, 'rss_raw.json')
    print(f"✅ {len(artigos)} artigos RSS salvos em data/rss_raw.json")


if __name__ == '__main__':
    main()
