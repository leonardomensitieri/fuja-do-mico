"""
SCRIPT 01 — Coleta de Newsletters (Gmail)
==========================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? SIM → Worker with API

O que faz:
  - Conecta na conta Gmail via API (OAuth2)
  - Busca emails não lidos das newsletters que você assinou
  - Extrai o corpo do email em texto limpo
  - Salva em data/newsletters_raw.json para o próximo script

Credenciais necessárias (GitHub Secrets):
  - GMAIL_CREDENTIALS_JSON : conteúdo do credentials.json baixado do Google Cloud
  - GMAIL_REMETENTES       : lista de emails separados por vírgula
                             ex: "newsletter@infomoney.com.br,noticias@suno.com.br"
"""

import os
import json
import base64
import re
from datetime import datetime, timedelta
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


def limpar_html(html: str) -> str:
    """Remove tags HTML e retorna texto limpo."""
    texto = re.sub(r'<[^>]+>', ' ', html)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def decodificar_parte(parte: dict) -> str:
    """Decodifica uma parte do email (base64 → string)."""
    dados = parte.get('body', {}).get('data', '')
    if dados:
        return base64.urlsafe_b64decode(dados + '==').decode('utf-8', errors='ignore')
    return ''


def extrair_texto_email(payload: dict) -> str:
    """Extrai texto de um payload de email (suporta multipart)."""
    mime_type = payload.get('mimeType', '')

    if mime_type == 'text/plain':
        return decodificar_parte(payload)

    if mime_type == 'text/html':
        return limpar_html(decodificar_parte(payload))

    # Email com múltiplas partes
    if 'parts' in payload:
        textos = []
        for parte in payload['parts']:
            texto = extrair_texto_email(parte)
            if texto:
                textos.append(texto)
        return '\n\n'.join(textos)

    return ''


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
    print("📧 Iniciando coleta de newsletters via Gmail...")

    # Carregar credenciais
    creds_json = os.environ.get('GMAIL_CREDENTIALS_JSON')
    if not creds_json:
        print("⚠️  GMAIL_CREDENTIALS_JSON não configurado. Pulando coleta de Gmail.")
        Path('data').mkdir(exist_ok=True)
        Path('data/newsletters_raw.json').write_text('[]')
        return

    creds_data = json.loads(creds_json)
    creds = Credentials(
        token=creds_data.get('token'),
        refresh_token=creds_data.get('refresh_token'),
        token_uri=creds_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=creds_data.get('client_id'),
        client_secret=creds_data.get('client_secret'),
        scopes=['https://www.googleapis.com/auth/gmail.readonly']
    )

    # Renovar token se necessário
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build('gmail', 'v1', credentials=creds)

    # Construir query: emails dos remetentes nos últimos 7 dias
    remetentes = os.environ.get('GMAIL_REMETENTES', '').split(',')
    remetentes = [r.strip() for r in remetentes if r.strip()]

    data_limite = (datetime.now() - timedelta(days=7)).strftime('%Y/%m/%d')
    from_query = ' OR '.join([f'from:{r}' for r in remetentes])
    query = f'({from_query}) after:{data_limite} is:unread'

    print(f"  Buscando: {query}")

    # Buscar mensagens
    resultado = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=30
    ).execute()

    mensagens = resultado.get('messages', [])
    print(f"  Encontradas: {len(mensagens)} newsletters")

    newsletters = []
    for msg_ref in mensagens:
        msg = service.users().messages().get(
            userId='me',
            id=msg_ref['id'],
            format='full'
        ).execute()

        headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
        texto = extrair_texto_email(msg['payload'])

        if texto and len(texto) > 100:  # Ignora emails vazios
            newsletters.append({
                'fonte': 'gmail',
                'remetente': headers.get('From', ''),
                'assunto': headers.get('Subject', ''),
                'data': headers.get('Date', ''),
                'conteudo': texto[:8000]  # Limita a 8k chars por email
            })

    salvar_resultado(newsletters, 'newsletters_raw.json')
    print(f"✅ {len(newsletters)} newsletters salvas em data/newsletters_raw.json")


if __name__ == '__main__':
    main()
