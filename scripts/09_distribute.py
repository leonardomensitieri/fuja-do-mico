"""
SCRIPT 09 — Distribuição (Brevo / Email Marketing)
====================================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? SIM → Worker with API

O que faz:
  - Lê o HTML final aprovado (output/newsletter_final.html)
  - Cria campanha de email no Brevo com título e metadados da edição
  - Dispara o envio imediato para a lista de assinantes
  - Registra o envio em data/distribute_log.json

Credenciais (GitHub Secrets):
  - BREVO_API_KEY     : chave REST do Brevo (xkeysib-...)
  - BREVO_LIST_ID     : ID numérico da lista de contatos (ex: 2)
  - EMAIL_REMETENTE   : email verificado no Brevo (ex: leonardoabrreu@gmail.com)
  - NOME_REMETENTE    : nome exibido no envio (ex: Liga HUB Finance)

Brevo gratuito: até 300 emails/dia, listas ilimitadas.
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path


def _brevo_request(method: str, endpoint: str, api_key: str, payload: dict = None) -> dict:
    """Faz uma requisição à API v3 do Brevo."""
    url = f'https://api.brevo.com/v3/{endpoint}'
    dados = json.dumps(payload).encode('utf-8') if payload else None

    req = urllib.request.Request(
        url,
        data=dados,
        headers={
            'api-key': api_key,
            'content-type': 'application/json',
            'accept': 'application/json',
        },
        method=method
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            corpo = resp.read()
            return json.loads(corpo) if corpo else {}
    except urllib.error.HTTPError as e:
        corpo = e.read().decode('utf-8')
        raise RuntimeError(f"Brevo API {method} {endpoint} → {e.code}: {corpo}")


def carregar_html() -> str:
    """Lê o HTML final aprovado."""
    # O job 'distribuir' baixa o artefato para output/
    caminho = Path('output/newsletter_final.html')
    if not caminho.exists():
        raise FileNotFoundError(
            "output/newsletter_final.html não encontrado. "
            "Verifique se o artefato foi baixado corretamente no GitHub Actions."
        )
    return caminho.read_text(encoding='utf-8')


def carregar_metadados() -> dict:
    """Lê metadados da edição gerada."""
    # O artefato inclui data/conteudo_gerado.json baixado para output/
    for caminho in [Path('output/conteudo_gerado.json'), Path('data/conteudo_gerado.json')]:
        if caminho.exists():
            return json.loads(caminho.read_text(encoding='utf-8'))
    return {}


def montar_subject(metadados: dict) -> str:
    """Monta o assunto do email."""
    titulo = metadados.get('titulo_edicao', 'Nova Edição')
    # Remove caracteres que podem causar problema em assuntos de email
    titulo = titulo.replace('\n', ' ').strip()
    return f"Liga HUB Finance: {titulo}"


def criar_campanha(api_key: str, html: str, metadados: dict, list_id: int,
                   email_remetente: str, nome_remetente: str) -> int:
    """Cria a campanha no Brevo e retorna o ID."""
    subject = montar_subject(metadados)
    nome_campanha = (
        f"Liga HUB Finance — {metadados.get('titulo_edicao', 'Edição')} "
        f"({datetime.now().strftime('%d/%m/%Y')})"
    )

    payload = {
        'name': nome_campanha,
        'subject': subject,
        'sender': {
            'name': nome_remetente,
            'email': email_remetente,
        },
        'type': 'classic',
        'htmlContent': html,
        'recipients': {
            'listIds': [list_id]
        },
    }

    print(f"  Assunto: {subject}")
    print(f"  Lista ID: {list_id} | Remetente: {nome_remetente} <{email_remetente}>")

    resposta = _brevo_request('POST', 'emailCampaigns', api_key, payload)
    campanha_id = resposta.get('id')

    if not campanha_id:
        raise RuntimeError(f"Brevo não retornou ID da campanha: {resposta}")

    print(f"  Campanha criada com ID: {campanha_id}")
    return campanha_id


def enviar_campanha(api_key: str, campanha_id: int):
    """Dispara o envio imediato da campanha."""
    _brevo_request('POST', f'emailCampaigns/{campanha_id}/sendNow', api_key)
    print(f"  Campanha {campanha_id} enviada.")


def salvar_resultado(dados: dict, arquivo: str):
    """
    Persiste resultado localmente e no banco (se configurado).
    Extensível: adicionar provider de banco aqui no futuro.
    """
    Path('data').mkdir(exist_ok=True)
    Path(f'data/{arquivo}').write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    # Persistência no banco (futuro):
    # if os.environ.get('DATABASE_URL'):
    #     db_client.save(collection=arquivo, data=dados)


def main():
    print("📨 Iniciando distribuição via Brevo...")

    api_key = os.environ.get('BREVO_API_KEY')
    list_id_str = os.environ.get('BREVO_LIST_ID', '').strip() or '2'
    email_remetente = os.environ.get('EMAIL_REMETENTE', 'leonardoabrreu@gmail.com')
    nome_remetente = os.environ.get('NOME_REMETENTE', 'Liga HUB Finance')

    if not api_key:
        raise ValueError("BREVO_API_KEY é obrigatória.")

    try:
        list_id = int(list_id_str)
    except ValueError:
        raise ValueError(f"BREVO_LIST_ID deve ser um número inteiro, recebi: '{list_id_str}'")

    html = carregar_html()
    metadados = carregar_metadados()

    print(f"  Título da edição: {metadados.get('titulo_edicao', 'N/D')}")
    print(f"  HTML: {len(html)} caracteres")

    campanha_id = criar_campanha(api_key, html, metadados, list_id, email_remetente, nome_remetente)
    enviar_campanha(api_key, campanha_id)

    log = {
        'campanha_id': campanha_id,
        'titulo_edicao': metadados.get('titulo_edicao', 'N/D'),
        'tipo_edicao': metadados.get('tipo_edicao', 'N/D'),
        'subject': montar_subject(metadados),
        'list_id': list_id,
        'remetente': f'{nome_remetente} <{email_remetente}>',
        'enviado_em': datetime.now().isoformat(),
        'status': 'enviado',
    }
    salvar_resultado(log, 'distribute_log.json')

    print(f"✅ Newsletter enviada! Campanha ID: {campanha_id}")


if __name__ == '__main__':
    main()
