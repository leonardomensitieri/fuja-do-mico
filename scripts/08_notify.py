"""
SCRIPT 08 — Notificação de Aprovação via Telegram
==================================================
Decision Tree: Criatividade? SIM → Human Judgment? SIM
               → Critical Financial? SIM → HUMANO

O que faz:
  - Avisa o revisor humano via Telegram que a edição está pronta
  - Inclui contexto financeiro: tickers consultados, clone, APIs usadas
  - Pergunta se algum dado financeiro adicional é necessário
  - Inclui link direto para aprovação no GitHub Actions

A APROVAÇÃO em si acontece no GitHub (não aqui):
  GitHub → Actions → [execução atual] → Review deployments → Approve

Credenciais (GitHub Secrets):
  - TELEGRAM_BOT_TOKEN   : token do bot criado no BotFather
  - TELEGRAM_CHAT_ID     : ID do chat/usuário para enviar a mensagem
  - GITHUB_RUN_ID        : ID da execução (automático no GitHub Actions)
  - GITHUB_REPOSITORY    : nome do repositório (automático)
"""

import json
import os
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path


def url_aprovacao() -> str:
    """Monta a URL da página de aprovação no GitHub Actions."""
    repo = os.environ.get('GITHUB_REPOSITORY', 'seu-usuario/fuja-do-mico')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    if run_id:
        return f"https://github.com/{repo}/actions/runs/{run_id}"
    return f"https://github.com/{repo}/actions"


def carregar_conteudo_gerado() -> dict:
    """Lê o conteúdo gerado para extrair título, tempo de leitura e tags."""
    path = Path('data/conteudo_gerado.json')
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {}


def carregar_relatorio_orquestracao() -> dict:
    """Lê o relatório do orquestrador para extrair contexto do gate financeiro."""
    path = Path('data/orchestration_report.json')
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {}


def carregar_flag_sensibilidade() -> dict:
    """Lê data/sensibilidade_flag.json se existir. Retrocompatível: retorna {} se ausente."""
    path = Path('data/sensibilidade_flag.json')
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def montar_contexto_financeiro(report: dict) -> str:
    """
    Extrai informações do gate financeiro do relatório do orquestrador
    e monta um bloco de texto para a mensagem Telegram.
    """
    gate = report.get('decisao', {}).get('gate_financeiro', {})

    if not gate:
        return ""

    linhas = []

    chamar_brapi = gate.get('chamar_brapi', False)
    chamar_fintz = gate.get('chamar_fintz', False)
    tickers = gate.get('tickers', [])
    clone = gate.get('clone_detectado')

    if not chamar_brapi and not chamar_fintz:
        return ""  # Sem dados financeiros — não menciona

    # APIs usadas
    apis_usadas = []
    if chamar_brapi:
        apis_usadas.append('Brapi')
    if chamar_fintz:
        apis_usadas.append('Fintz')

    linhas.append(f"\n📊 *Dados financeiros consultados*")
    linhas.append(f"APIs: {' + '.join(apis_usadas)}")

    if tickers:
        linhas.append(f"Tickers: `{', '.join(tickers[:8])}`")

    if clone:
        nomes_clones = {
            'barsi': 'Luiz Barsi',
            'graham': 'Benjamin Graham',
            'buffett': 'Warren Buffett',
            'lynch': 'Peter Lynch',
            'damodaran': 'Aswath Damodaran',
        }
        nome_clone = nomes_clones.get(clone, clone.title())
        linhas.append(f"Clone sugerido: {nome_clone}")

    return '\n'.join(linhas)


def montar_mensagem(conteudo: dict, report: dict, url: str) -> str:
    """
    Monta a mensagem completa para o Telegram.
    Usa formatação Markdown do Telegram (v1: *bold*, _italic_, `code`).
    """
    titulo = conteudo.get('titulo_edicao', 'Nova edição da Liga HUB Finance')
    tempo = conteudo.get('tempo_leitura', '?')
    tags = conteudo.get('tags', [])
    # No MarkdownV2 o # precisa ser escapado como \#
    tags_str = ' '.join([r'\#' + t.replace(' ', '') for t in tags[:4]]) if tags else ''

    tipo_edicao = conteudo.get('tipo_edicao', 'completa')
    tipo_emoji = '📰' if tipo_edicao == 'completa' else '📄'

    # Contexto financeiro (pode ser vazio)
    ctx_financeiro = montar_contexto_financeiro(report)

    # Flag de sensibilidade (Story 1.13) — retrocompatível: {} se ausente
    flag = carregar_flag_sensibilidade()
    nivel_sensibilidade = flag.get('nivel', 'nenhum')

    prefixo = ''
    sufixo_disclaimer = ''
    if nivel_sensibilidade == 'alto':
        flags_txt = '\n'.join([f'  • {f}' for f in flag.get('flags', [])])
        prefixo = f'⚠️ *ALERTA: conteúdo sensível detectado*\n{flags_txt}\n\n'
    elif nivel_sensibilidade == 'medio':
        disclaimer = flag.get(
            'disclaimer',
            'Este conteúdo tem caráter exclusivamente educacional e não constitui recomendação de investimento.',
        )
        sufixo_disclaimer = f'\n\n📋 _Disclaimer automático aplicado: {disclaimer}_'

    # Bloco de protocolo de escalada humana
    escalada = (
        "\n\n❓ *Precisa de dados adicionais?*\n"
        "Antes de aprovar, verifique se os indicadores mostrados na newsletter "
        "estão completos para o tema desta edição\\. Se precisar de algum dado "
        "financeiro extra \\(outro ticker, um indicador específico, Tesouro Direto\\), "
        "rejeite com o motivo e reprocesse — ou aprove com a edição atual\\."
    )

    mensagem = (
        f"{prefixo}"
        f"{tipo_emoji} *Liga HUB Finance — Edição pronta para revisão*\n\n"
        f"*{titulo}*\n"
        f"⏱ Tempo de leitura: {tempo}\n"
        f"{tags_str}"
        f"{ctx_financeiro}"
        f"{escalada}\n\n"
        f"👉 [Revisar e Aprovar no GitHub]({url})\n\n"
        f"_Clique em \"Review deployments\" → selecione \"aprovacao\\-humana\" → Approve_"
        f"{sufixo_disclaimer}"
    )

    return mensagem


def montar_inline_keyboard(run_id: str, edicao_id: str) -> dict:
    """
    Monta teclado inline com botões de Aprovar e Rejeitar.
    O callback_data embute run_id e edicao_id para o webhook identificar a edição.
    """
    return {
        'inline_keyboard': [[
            {
                'text': '✅ Aprovar',
                'callback_data': f'approve:{run_id}:{edicao_id}'
            },
            {
                'text': '❌ Rejeitar',
                'callback_data': f'reject:{run_id}:{edicao_id}'
            }
        ]]
    }


def enviar_telegram(token: str, chat_id: str, mensagem: str, run_id: str = '', edicao_id: str = '') -> bool:
    """
    Envia mensagem via API do Telegram Bot.
    Inclui botões inline de aprovação quando run_id e edicao_id estão disponíveis.
    Usa urllib (sem dependências externas).
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': mensagem,
        'parse_mode': 'MarkdownV2',
        'disable_web_page_preview': False,
    }

    # Adiciona botões inline se run_id disponível (Story 2.4)
    if run_id and edicao_id:
        payload['reply_markup'] = montar_inline_keyboard(run_id, edicao_id)

    dados = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=dados,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resultado = json.loads(resp.read().decode('utf-8'))
            if resultado.get('ok'):
                print("  ✅ Notificação Telegram enviada")
                return True
            else:
                print(f"  ⚠️  Telegram respondeu ok=false: {resultado}")
                return False

    except urllib.error.HTTPError as e:
        corpo = e.read().decode('utf-8')
        print(f"  ⚠️  Telegram HTTPError {e.code}: {corpo}")
        # Fallback sem MarkdownV2 (pode ter caractere especial não escapado)
        return _enviar_telegram_simples(token, chat_id, mensagem, run_id, edicao_id)

    except Exception as e:
        print(f"  ⚠️  Erro ao enviar Telegram: {e}")
        return False


def _enviar_telegram_simples(token: str, chat_id: str, mensagem: str,
                             run_id: str = '', edicao_id: str = '') -> bool:
    """
    Fallback sem MarkdownV2 — envia texto puro caso a formatação falhe.
    Remove os marcadores de formatação antes de enviar.
    Mantém os botões inline mesmo no fallback.
    """
    import re
    texto_puro = re.sub(r'[*_`\[\]\\]', '', mensagem)
    texto_puro = re.sub(r'\(https?://[^\)]+\)', '', texto_puro)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': texto_puro,
    }
    # Botões inline mesmo no fallback — essenciais para aprovação
    if run_id and edicao_id:
        payload['reply_markup'] = montar_inline_keyboard(run_id, edicao_id)

    dados = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=dados,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resultado = json.loads(resp.read().decode('utf-8'))
            if resultado.get('ok'):
                print("  ✅ Notificação Telegram enviada (texto simples)")
                return True
            else:
                print(f"  ⚠️  Telegram fallback também falhou: {resultado}")
                return False
    except Exception as e:
        print(f"  ⚠️  Erro no fallback Telegram: {e}")
        return False


def salvar_resultado(dados: dict, arquivo: str, edicao_id: str = None):
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
    print("📱 Enviando notificação de aprovação via Telegram...")

    conteudo = carregar_conteudo_gerado()
    report = carregar_relatorio_orquestracao()
    url = url_aprovacao()

    print(f"  URL de aprovação: {url}")

    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    enviado = False

    if token and chat_id:
        run_id = os.environ.get('GITHUB_RUN_ID', '')
        edicao_id = os.environ.get('EDICAO_ID', '')
        mensagem = montar_mensagem(conteudo, report, url)
        enviado = enviar_telegram(token, chat_id, mensagem, run_id=run_id, edicao_id=edicao_id)
    else:
        print("  ⚠️  TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados")

    if not enviado:
        # Fallback: imprime no log — GitHub Actions envia email automático
        # para os reviewers configurados no environment 'aprovacao-humana'
        titulo = conteudo.get('titulo_edicao', 'N/D')
        print(f"""
  ℹ️  Telegram não configurado ou falhou.
  O GitHub Actions enviará email automático para os reviewers do environment.

  URL de aprovação: {url}
  Título da edição: {titulo}

  Dica: configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID nos GitHub Secrets.
        """)

    # Salva log da notificação
    log = {
        'url_aprovacao': url,
        'enviado': enviado,
        'canal': 'telegram' if (token and chat_id) else 'github_email',
        'titulo_edicao': conteudo.get('titulo_edicao', 'N/D'),
        'tipo_edicao': conteudo.get('tipo_edicao', 'N/D'),
    }
    salvar_resultado(log, 'notify_log.json')
    print("✅ Passo de notificação concluído.")


if __name__ == '__main__':
    main()
