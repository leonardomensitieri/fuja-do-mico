"""
SCRIPT 02 — Coleta de RSS (Notícias e Research)
================================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? SIM → Worker with API

O que faz:
  - Lê os feeds RSS configurados em config/rss_feeds.txt
  - Filtra apenas itens publicados nos últimos 7 dias
  - Salva em data/rss_raw.json para o próximo script

Sem credenciais necessárias — feeds RSS são públicos.
"""

import json
import feedparser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import mktime


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

    feeds = carregar_feeds()
    limite = datetime.now(tz=timezone.utc) - timedelta(days=7)
    artigos = []

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
                    artigos.append({
                        'fonte': f'rss:{fonte}',
                        'titulo': titulo,
                        'resumo': resumo_limpo[:2000],
                        'link': link,
                        'data': data.isoformat() if data else '',
                        'conteudo': f"{titulo}\n\n{resumo_limpo}"
                    })
                    novos += 1

            print(f"    → {novos} artigos novos")

        except Exception as e:
            print(f"    ⚠️  Erro ao processar {url}: {e}")
            continue

    salvar_resultado(artigos, 'rss_raw.json')
    print(f"✅ {len(artigos)} artigos RSS salvos em data/rss_raw.json")


if __name__ == '__main__':
    main()
