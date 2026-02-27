"""
SCRIPT 00 — Orquestrador Central do Pipeline
==============================================
Decision Tree: Worker Script — lógica de decisão pura, sem chamadas à IA

O que faz:
  - Executa a coleta de conteúdo (scripts 01–03): Gmail, RSS, YouTube
  - Executa a triagem do conteúdo coletado (script 05)
  - Aplica Gate 1: decide se há conteúdo suficiente para gerar a edição
  - Aplica Gate Financeiro: analisa temas triados e decide se/quais APIs
    financeiras chamar (Brapi 04 e/ou Fintz 04b) e com quais tickers
  - Aplica Gate 2: decide quais nodes/seções compõem a edição
  - Executa a geração de conteúdo com a composição decidida (script 06)
  - Executa a população do template HTML (script 07)
  - Executa a notificação do revisor (script 08)
  - Gera relatório de orquestração em data/orchestration_report.json

Fluxo de decisão financeira:
  As APIs Brapi/Fintz SÓ são chamadas se o conteúdo triado justificar.
  O gate analisa temas_identificados[] de cada item triado e detecta:
    1. Gatilhos financeiros (P/L, DY, ROE, dividendos, valuation...)
    2. Tickers B3 mencionados explicitamente (PETR4, VALE3...)
    3. Clone mais provável → determina quais campos são obrigatórios
  Se nenhum gatilho: scripts 04 e 04b são pulados (0 requisições gastas).

Credenciais necessárias (GitHub Secrets) — repassadas para os sub-scripts:
  - ANTHROPIC_API_KEY    : para triagem (05) e geração (06)
  - BRAPI_TOKEN          : para coleta financeira condicional (04)
  - FINTZ_API_KEY        : para coleta financeira condicional (04b)
  - FINTZ_API_KEY_FALLBACK : chave de fallback Fintz (04b)
  - TICKERS              : tickers base da B3 — complementado pelos detectados
  - GMAIL_CREDENTIALS_JSON : credenciais Gmail (01)
  - GMAIL_REMETENTES     : remetentes monitorados (01)
  - YOUTUBE_API_KEY      : YouTube Data API (03)
  - TELEGRAM_BOT_TOKEN   : notificação Telegram (08)
  - TELEGRAM_CHAT_ID     : ID do chat Telegram (08)
  - GITHUB_RUN_ID        : ID da execução GitHub Actions (08)
  - GITHUB_REPOSITORY    : nome do repositório GitHub (08)

Sem credenciais próprias — apenas repassa o ambiente para os sub-scripts.
"""

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path


# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────

def carregar_config() -> dict:
    """Carrega as configurações do orquestrador."""
    config_path = Path('config/orchestrator_config.json')
    if not config_path.exists():
        raise FileNotFoundError(
            "config/orchestrator_config.json não encontrado. "
            "Crie o arquivo de configuração antes de executar o orquestrador."
        )
    return json.loads(config_path.read_text(encoding='utf-8'))


# ──────────────────────────────────────────────────────────────
# EXECUÇÃO DE SUB-SCRIPTS
# ──────────────────────────────────────────────────────────────

def executar_script(nome: str, env_extra: dict = None) -> bool:
    """
    Executa um script Python via subprocess.
    Retorna True se bem-sucedido, False caso contrário.
    """
    env = {**os.environ}
    if env_extra:
        env.update(env_extra)

    print(f"\n{'─' * 50}")
    print(f"▶ Executando: {nome}")
    print(f"{'─' * 50}")

    resultado = subprocess.run(
        [sys.executable, f'scripts/{nome}'],
        env=env
    )

    if resultado.returncode != 0:
        print(f"  ❌ {nome} falhou com código {resultado.returncode}")
        return False

    print(f"  ✅ {nome} concluído")
    return True


def executar_coleta_conteudo() -> dict:
    """
    Executa os scripts de coleta de conteúdo (01–03): Gmail, RSS, YouTube.
    APIs financeiras (04/04b) são tratadas separadamente no gate financeiro,
    pós-triagem, somente quando o tema justificar.
    """
    metricas = {
        'gmail_count': 0,
        'rss_count': 0,
        'youtube_count': 0,
        'social_count': 0,
    }

    # Coleta Gmail (opcional — não bloqueia se falhar)
    if executar_script('01_collect_gmail.py'):
        path = Path('data/newsletters_raw.json')
        if path.exists():
            metricas['gmail_count'] = len(json.loads(path.read_text()))

    # Coleta RSS
    if executar_script('02_collect_rss.py'):
        path = Path('data/rss_raw.json')
        if path.exists():
            metricas['rss_count'] = len(json.loads(path.read_text()))

    # Coleta YouTube (opcional — não bloqueia se falhar)
    if executar_script('03_collect_youtube.py'):
        path = Path('data/youtube_raw.json')
        if path.exists():
            metricas['youtube_count'] = len(json.loads(path.read_text()))

    # Coleta social via Apify — não-bloqueante (Story 2.1)
    if os.environ.get('APIFY_API_TOKEN'):
        sucesso_social = executar_script('10_collect_social.py')
        if not sucesso_social:
            print('  ⚠️  Coleta social falhou — pipeline continua sem dados sociais')
        else:
            path = Path('data/social_raw.json')
            if path.exists():
                metricas['social_count'] = len(json.loads(path.read_text()))
    else:
        print('  ℹ️  APIFY_API_TOKEN não configurado — coleta social pulada')

    return metricas


def executar_triagem() -> dict:
    """Executa a triagem e retorna métricas."""
    metricas = {'alto': 0, 'medio': 0, 'baixo': 0, 'total_aprovados': 0}

    if not executar_script('05_triage.py'):
        print("  ⚠️  Triagem falhou — usando métricas zeradas")
        return metricas

    path = Path('data/conteudo_triado.json')
    if not path.exists():
        return metricas

    triados = json.loads(path.read_text())
    for item in triados:
        relevancia = item.get('triagem', {}).get('relevancia', 'BAIXO')
        if relevancia == 'ALTO':
            metricas['alto'] += 1
        elif relevancia == 'MEDIO':
            metricas['medio'] += 1
        else:
            metricas['baixo'] += 1

    metricas['total_aprovados'] = metricas['alto'] + metricas['medio']
    return metricas


# ──────────────────────────────────────────────────────────────
# GATE FINANCEIRO — DECISÃO CONDICIONAL DE COLETA DE APIs
# ──────────────────────────────────────────────────────────────

# Palavras-chave que indicam que dados financeiros de mercado agregam valor
_GATILHOS_FINANCEIROS = {
    # Múltiplos e valuation
    'p/l', 'p/vp', 'p/ebitda', 'p/ebit', 'ev/ebitda', 'ev/ebit',
    'peg ratio', 'peg', 'valuation', 'múltiplos', 'multiplos',
    'valor intrínseco', 'valor intrinseco', 'margem de segurança',
    'margem de seguranca', 'desconto', 'preço justo', 'preco justo',
    # Rentabilidade
    'roe', 'roa', 'roic', 'margem líquida', 'margem liquida',
    'margem ebitda', 'margem bruta', 'retorno sobre capital',
    'lucratividade', 'rentabilidade',
    # Dividendos e proventos
    'dividend yield', 'dy', 'dividendos', 'dividendo', 'proventos',
    'jcp', 'juros sobre capital', 'renda passiva', 'yield on cost',
    'carteira de dividendos', 'barsi', 'previdência privada',
    # Endividamento
    'dívida', 'divida', 'alavancagem', 'endividamento',
    'dívida/pl', 'divida/pl', 'dívida/ebitda', 'divida/ebitda',
    'liquidez', 'cobertura de juros',
    # Dados de mercado
    'cotação', 'cotacao', 'resultado trimestral', 'balanço', 'balanco',
    'lucro por ação', 'lucro por acao', 'market cap', 'capitalização',
    'capitalizacao', 'ações da b3', 'acoes da b3',
    # Renda fixa
    'tesouro direto', 'ipca+', 'ntn-b', 'lft', 'selic', 'prefixado',
    'taxa livre de risco', 'renda fixa vs variável', 'renda fixa',
    # Análise fundamentalista
    'fundamentalista', 'análise fundamentalista', 'analise fundamentalista',
    'value investing', 'graham', 'buffett', 'lynch', 'damodaran',
    'resultado', 'receita', 'lucro líquido', 'lucro liquido', 'ebitda',
}

# Mapeamento de clone para quais APIs são obrigatórias
_CLONE_APIS = {
    'barsi':      {'brapi': False, 'fintz': True},   # DY só na Fintz
    'graham':     {'brapi': True,  'fintz': True},   # P/L Brapi + Dívida Fintz
    'buffett':    {'brapi': True,  'fintz': True},   # ROE Brapi + ROIC Fintz
    'lynch':      {'brapi': True,  'fintz': False},  # PEG Ratio no Brapi
    'damodaran':  {'brapi': True,  'fintz': True},   # FCL Brapi + EV/EBITDA Fintz
}

# Regex para detectar tickers B3 (3-5 letras + 1-2 dígitos, ex: PETR4, VALE3, TAEE11)
_REGEX_TICKER = re.compile(r'\b([A-Z]{3,5}[0-9]{1,2})\b')


def avaliar_gate_financeiro(tickers_base: list) -> dict:
    """
    Analisa o conteúdo triado e decide se/quais APIs financeiras chamar.

    Lê data/conteudo_triado.json e examina:
      - temas_identificados[] de cada item aprovado
      - textos para detectar tickers B3 mencionados
      - clones mais prováveis baseado nos temas

    Retorna:
      {
        'chamar_brapi': bool,
        'chamar_fintz': bool,
        'tickers': list,        # tickers a buscar (detectados + base)
        'clone_detectado': str, # clone mais provável (ou None)
        'justificativa': str,
      }
    """
    resultado = {
        'chamar_brapi': False,
        'chamar_fintz': False,
        'tickers': tickers_base,
        'clone_detectado': None,
        'justificativa': 'Nenhum gatilho financeiro detectado',
    }

    path = Path('data/conteudo_triado.json')
    if not path.exists():
        return resultado

    triados = json.loads(path.read_text(encoding='utf-8'))
    todos_temas = []
    texto_completo = ''

    for item in triados:
        triagem = item.get('triagem', {})
        temas = triagem.get('temas_identificados', [])
        todos_temas.extend([t.lower() for t in temas])
        # Acumula textos para detecção de tickers
        texto_completo += ' ' + item.get('titulo', '')
        texto_completo += ' ' + item.get('assunto', '')
        texto_completo += ' ' + triagem.get('resumo_em_3_linhas', '')
        texto_completo += ' ' + triagem.get('angulo_potencial_para_newsletter', '')

    # 1. Detecta gatilhos financeiros nos temas
    temas_set = set(todos_temas)
    gatilhos_encontrados = temas_set & _GATILHOS_FINANCEIROS
    if not gatilhos_encontrados:
        # Tenta também na string completa (mais permissivo)
        texto_lower = texto_completo.lower()
        gatilhos_encontrados = {g for g in _GATILHOS_FINANCEIROS if g in texto_lower}

    if not gatilhos_encontrados:
        print("  ⏭️  Gate Financeiro → sem gatilhos — APIs puladas")
        return resultado

    # 2. Detecta tickers B3 mencionados no conteúdo
    tickers_detectados = list(set(_REGEX_TICKER.findall(texto_completo.upper())))
    # Filtra falsos positivos comuns (siglas que não são tickers)
    _NAO_TICKERS = {'CEO', 'CFO', 'CTO', 'IPO', 'PIB', 'FII', 'ETF', 'CDI', 'CDB', 'LCI', 'LCA'}
    tickers_detectados = [t for t in tickers_detectados if t not in _NAO_TICKERS]

    # Combina: tickers detectados + tickers base (sem duplicatas)
    tickers_finais = list(dict.fromkeys(tickers_detectados + tickers_base))

    # 3. Detecta clone mais provável
    clone_detectado = None
    for clone in ['barsi', 'graham', 'buffett', 'lynch', 'damodaran']:
        if clone in temas_set or any(clone in t for t in temas_set):
            clone_detectado = clone
            break
    # Heurísticas de tema → clone
    if not clone_detectado:
        if any(g in gatilhos_encontrados for g in {'dividendo', 'dy', 'dividendos', 'proventos', 'renda passiva', 'barsi'}):
            clone_detectado = 'barsi'
        elif any(g in gatilhos_encontrados for g in {'margem de segurança', 'margem de seguranca', 'p/l', 'p/vp', 'graham'}):
            clone_detectado = 'graham'
        elif any(g in gatilhos_encontrados for g in {'peg', 'peg ratio', 'crescimento', 'lynch'}):
            clone_detectado = 'lynch'
        elif any(g in gatilhos_encontrados for g in {'roe', 'moat', 'vantagem competitiva', 'buffett'}):
            clone_detectado = 'buffett'
        elif any(g in gatilhos_encontrados for g in {'ev/ebitda', 'roic', 'dcf', 'wacc', 'damodaran'}):
            clone_detectado = 'damodaran'

    # 4. Determina quais APIs são necessárias
    chamar_brapi = True  # Brapi é default quando há gatilho financeiro
    chamar_fintz = False

    if clone_detectado and clone_detectado in _CLONE_APIS:
        apis = _CLONE_APIS[clone_detectado]
        chamar_brapi = apis['brapi']
        chamar_fintz = apis['fintz']
    else:
        # Sem clone específico: Fintz só se há gatilhos de DY/proventos/endividamento
        gatilhos_fintz = {'dy', 'dividend yield', 'dividendo', 'dividendos', 'proventos',
                          'ev/ebitda', 'roic', 'dívida/ebitda', 'divida/ebitda',
                          'tesouro direto', 'ipca+', 'renda fixa'}
        chamar_fintz = bool(gatilhos_encontrados & gatilhos_fintz)

    resultado.update({
        'chamar_brapi': chamar_brapi,
        'chamar_fintz': chamar_fintz,
        'tickers': tickers_finais,
        'clone_detectado': clone_detectado,
        'justificativa': (
            f"Gatilhos: {sorted(list(gatilhos_encontrados))[:5]} | "
            f"Clone: {clone_detectado or 'não identificado'} | "
            f"Tickers: {tickers_finais[:8]}"
        ),
    })

    apis_str = ' + '.join(
        [a for a, v in [('Brapi', chamar_brapi), ('Fintz', chamar_fintz)] if v]
    ) or 'nenhuma'
    print(f"  💡 Gate Financeiro → {apis_str} | Clone: {clone_detectado or '—'} | Tickers: {tickers_finais[:5]}")
    return resultado


def executar_coleta_financeira(gate: dict) -> dict:
    """
    Executa as APIs financeiras conforme decisão do gate financeiro.
    Injeta os tickers detectados como variável de ambiente TICKERS.
    """
    metricas = {'brapi_disponivel': False, 'fintz_disponivel': False}

    if not gate.get('chamar_brapi') and not gate.get('chamar_fintz'):
        print("  ⏭️  Coleta financeira pulada — não necessária para este tema")
        return metricas

    tickers_str = ','.join(gate.get('tickers', []))
    env_tickers = {'TICKERS': tickers_str} if tickers_str else {}

    if gate.get('chamar_brapi'):
        if executar_script('04_collect_brapi.py', env_tickers):
            path = Path('data/brapi_raw.json')
            if path.exists():
                dados = json.loads(path.read_text())
                metricas['brapi_disponivel'] = len(dados) > 0

    if gate.get('chamar_fintz'):
        if executar_script('04b_collect_fintz.py', env_tickers):
            path = Path('data/fintz_raw.json')
            if path.exists():
                dados = json.loads(path.read_text())
                metricas['fintz_disponivel'] = len(dados.get('acoes', [])) > 0

    return metricas


# ──────────────────────────────────────────────────────────────
# GATE 1 — LIMIAR DE CONTEÚDO
# ──────────────────────────────────────────────────────────────

def avaliar_gate1(triagem: dict, config: dict) -> str:
    """
    Avalia se há conteúdo suficiente para gerar a edição.

    Retorna:
      'completa'  — edição com todos os nodes disponíveis
      'reduzida'  — edição com nodes essenciais apenas
      'abortado'  — conteúdo insuficiente, pipeline encerrado
    """
    thresholds = config.get('thresholds', {})
    alto_min_completo = thresholds.get('alto_min_completo', 3)
    alto_min_reduzido = thresholds.get('alto_min_reduzido', 1)
    medio_min_reduzido = thresholds.get('medio_min_reduzido', 3)

    count_alto = triagem.get('alto', 0)
    count_medio = triagem.get('medio', 0)

    if count_alto >= alto_min_completo:
        print(f"\n  🟢 Gate 1 → EDIÇÃO COMPLETA ({count_alto} itens ALTO >= {alto_min_completo})")
        return 'completa'
    elif count_alto >= alto_min_reduzido or count_medio >= medio_min_reduzido:
        print(f"\n  🟡 Gate 1 → EDIÇÃO REDUZIDA (ALTO={count_alto}, MEDIO={count_medio})")
        return 'reduzida'
    else:
        print(f"\n  🔴 Gate 1 → ABORTADO (ALTO={count_alto}, MEDIO={count_medio} — insuficiente)")
        return 'abortado'


# ──────────────────────────────────────────────────────────────
# GATE 2 — COMPOSIÇÃO DE NODES
# ──────────────────────────────────────────────────────────────

def compor_nodes(triagem: dict, coleta: dict, config: dict, tipo_edicao: str) -> list:
    """
    Decide quais nodes/seções entram na edição.
    Retorna lista de IDs dos nodes incluídos.
    """
    nodes_incluidos = []
    count_alto = triagem.get('alto', 0)
    brapi_disponivel = coleta.get('brapi_disponivel', False)

    for node in config.get('nodes', []):
        node_id = node.get('id')
        obrigatorio = node.get('obrigatorio', False)
        condicao = node.get('condicao', '')

        if obrigatorio:
            nodes_incluidos.append(node_id)
            continue

        # Avaliar condição
        incluir = False
        if condicao == 'count_alto >= 1':
            incluir = count_alto >= 1
        elif condicao == 'count_alto >= 2':
            incluir = count_alto >= 2
        elif condicao == 'brapi_disponivel == true':
            incluir = brapi_disponivel
        else:
            # Condição desconhecida — incluir por padrão
            incluir = True

        if incluir:
            nodes_incluidos.append(node_id)

    print(f"\n  📋 Gate 2 → Nodes incluídos: {nodes_incluidos}")
    return nodes_incluidos


# ──────────────────────────────────────────────────────────────
# GERAÇÃO E TEMPLATE
# ──────────────────────────────────────────────────────────────

def executar_geracao(node_config: dict) -> bool:
    """Executa a geração de conteúdo com a composição decidida."""
    env_extra = {'NODE_CONFIG': json.dumps(node_config)}
    return executar_script('06_generate.py', env_extra)


def executar_template(node_config: dict) -> bool:
    """Executa a população do template HTML."""
    env_extra = {'NODE_CONFIG': json.dumps(node_config)}
    return executar_script('07_populate_template.py', env_extra)


def executar_notificacao() -> bool:
    """Executa o envio de notificação ao revisor."""
    return executar_script('08_notify.py')


# ──────────────────────────────────────────────────────────────
# ATUALIZAÇÃO DE STATUS EM TEMPO REAL (Story 2.3)
# ──────────────────────────────────────────────────────────────

def atualizar_status(status: str):
    """
    Atualiza o status da edição no Supabase em tempo real.
    Chamado a cada fase do pipeline para mover o card no Kanban.
    Silencioso em caso de falha — nunca aborta o pipeline.
    """
    if not (os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY')):
        return
    try:
        from db_provider import get_client
        _sb = get_client()
        if _sb:
            edicao_id = os.environ.get('EDICAO_ID')
            _sb.table('edicoes').update({'status': status}).eq('id', edicao_id).execute()
            print(f"  📊 Status atualizado → {status}")
    except Exception as e:
        print(f"  ⚠️  Falha ao atualizar status ({e}) — continuando")


# ──────────────────────────────────────────────────────────────
# RELATÓRIO DE ORQUESTRAÇÃO
# ──────────────────────────────────────────────────────────────

def salvar_orchestration_report(dados: dict):
    """
    Persiste o relatório de orquestração localmente e no Supabase (Story 2.2).
    Retrocompatível: sem SUPABASE_URL, apenas salva o arquivo JSON.
    """
    Path('data').mkdir(exist_ok=True)
    Path('data/orchestration_report.json').write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    # Persistência no banco — ativa com SUPABASE_URL (Story 2.2)
    if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY'):
        try:
            _scripts_dir = str(Path(__file__).resolve().parent)
            if _scripts_dir not in sys.path:
                sys.path.insert(0, _scripts_dir)
            from db_provider import get_client, salvar_edicao, salvar_execucao
            supabase = get_client()
            if supabase:
                edicao_id = os.environ.get('EDICAO_ID')
                edicao_numero_str = dados.get('edicao_numero', '0')
                try:
                    edicao_numero = int(edicao_numero_str)
                except (ValueError, TypeError):
                    edicao_numero = 0
                tipo = dados.get('decisao', {}).get('tipo_edicao')
                sucesso = tipo not in ('abortado', None)
                # Upsert edição — id=edicao_id garante FK consistency com execucoes
                # Status: aguardando_aprovacao (Job 1 termina aqui, Job 3 atualiza para 'distribuida')
                salvar_edicao(
                    supabase,
                    numero=edicao_numero,
                    id=edicao_id,
                    titulo=dados.get('decisao', {}).get('justificativa', '')[:200],
                    tipo_edicao=tipo if tipo in ('completa', 'reduzida', 'abortada') else None,
                    status='aguardando_aprovacao' if sucesso else 'abortada',
                )
                # Registra execução com relatório completo
                salvar_execucao(supabase, edicao_id, dados, sucesso)
        except Exception as e:
            print(f'  ⚠️  Supabase indisponível ({e}) — continuando sem persistência')

    print("\n  📄 Relatório salvo em data/orchestration_report.json")


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def main():
    print("🧠 Iniciando orquestrador do pipeline Fuja do Mico...")
    print(f"  Data/hora: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")

    # Gerar identificador único da execução e propagar para todos os sub-scripts (Story 2.2)
    edicao_id = str(uuid.uuid4())
    os.environ['EDICAO_ID'] = edicao_id
    print(f"  Execução ID: {edicao_id}")

    # Identificar número da edição — auto-incrementa via Supabase ou fallback timestamp
    edicao_numero = os.environ.get('EDICAO_NUMERO')
    if not edicao_numero:
        if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY'):
            try:
                from db_provider import get_client
                _sb = get_client()
                if _sb:
                    _res = _sb.table('edicoes').select('numero').order('numero', desc=True).limit(1).execute()
                    _ultimo = _res.data[0]['numero'] if _res.data else 0
                    edicao_numero = str(_ultimo + 1)
            except Exception:
                pass
        if not edicao_numero:
            from datetime import datetime as _dt
            edicao_numero = _dt.now().strftime('%Y%m%d')

    # Inicializar relatório
    report = {
        'edicao_id': edicao_id,
        'edicao_numero': edicao_numero,
        'data_execucao': datetime.now().isoformat(),
        'coleta': {},
        'triagem': {},
        'decisao': {
            'tipo_edicao': 'abortado',
            'nodes_incluidos': [],
            'justificativa': ''
        }
    }

    try:
        # Carregar configuração
        config = carregar_config()

        # Tickers base configurados (fallback se nenhum for detectado na triagem)
        tickers_raw = os.environ.get('TICKERS', 'PETR4,VALE3,ITUB4,BBDC4,WEGE3')
        tickers_base = [t.strip() for t in tickers_raw.split(',') if t.strip()]

        # Criar registro da edição no Supabase logo no início (para Realtime funcionar)
        if os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY'):
            try:
                from db_provider import get_client, salvar_edicao
                _sb = get_client()
                if _sb:
                    salvar_edicao(
                        _sb,
                        numero=int(edicao_numero) if str(edicao_numero).isdigit() else 0,
                        id=edicao_id,
                        status='em_coleta',
                        github_run_id=os.environ.get('GITHUB_RUN_ID'),
                    )
            except Exception as e:
                print(f"  ⚠️  Falha ao criar edição no Supabase ({e}) — continuando")

        # FASE 1 — Coleta de conteúdo (Gmail, RSS, YouTube)
        print("\n\n═══ FASE 1: COLETA DE CONTEÚDO ═══")
        atualizar_status('em_coleta')
        coleta = executar_coleta_conteudo()
        report['coleta'] = coleta
        print(f"\n  Resumo coleta: {coleta}")

        # FASE 2 — Triagem
        print("\n\n═══ FASE 2: TRIAGEM ═══")
        atualizar_status('triagem')
        triagem = executar_triagem()
        report['triagem'] = triagem
        print(f"\n  Resumo triagem: {triagem}")

        # GATE 1 — Limiar de conteúdo
        print("\n\n═══ GATE 1: LIMIAR DE CONTEÚDO ═══")
        tipo_edicao = avaliar_gate1(triagem, config)
        report['decisao']['tipo_edicao'] = tipo_edicao

        if tipo_edicao == 'abortado':
            report['decisao']['justificativa'] = (
                f"Conteúdo insuficiente: ALTO={triagem.get('alto', 0)}, "
                f"MEDIO={triagem.get('medio', 0)}"
            )
            salvar_orchestration_report(report)
            print("\n❌ Pipeline encerrado — conteúdo insuficiente para gerar edição.")
            sys.exit(1)

        # GATE EDITORIAL — Score 0-10 por linha editorial (Story 1.12)
        # Não bloqueante: falha gera warning, pipeline continua
        print("\n\n═══ GATE EDITORIAL: PONTUAÇÃO DE LINHAS ═══")
        gate_editorial_ok = executar_script('05b_editorial_gate.py')
        if not gate_editorial_ok:
            print("  ⚠️  Gate editorial falhou — pipeline continua sem scores editoriais")
        report['decisao']['gate_editorial_ok'] = gate_editorial_ok

        # GATE FINANCEIRO — Coleta condicional de APIs (pós-triagem)
        # Prioriza scores do gate editorial; fallback para análise de keywords
        print("\n\n═══ GATE FINANCEIRO: DECISÃO DE APIs ═══")
        gate_fin = avaliar_gate_financeiro(tickers_base)

        # Override: se gate editorial indicou linha_1 ativa, forçar APIs financeiras
        scores_editorial_path = Path('data/scores_editorial.json')
        if scores_editorial_path.exists():
            try:
                scores_data = json.loads(scores_editorial_path.read_text(encoding='utf-8'))
                linha_1_score = scores_data.get('scores', {}).get('linha_1', 0)
                if linha_1_score >= 6 and not gate_fin.get('chamar_brapi'):
                    print(f"  💡 Gate Editorial → linha_1 score={linha_1_score}/10 >= 6: ativando Brapi + Fintz")
                    gate_fin['chamar_brapi'] = True
                    gate_fin['chamar_fintz'] = True
                    gate_fin['justificativa'] = (
                        f"[Override Gate Editorial] linha_1 score={linha_1_score} | "
                        + gate_fin.get('justificativa', '')
                    )
            except (json.JSONDecodeError, IOError) as e:
                print(f"  ⚠️  Falha ao ler scores_editorial.json: {e}")

        report['decisao']['gate_financeiro'] = gate_fin

        coleta_fin = executar_coleta_financeira(gate_fin)
        coleta.update(coleta_fin)
        report['coleta'].update(coleta_fin)

        # AGENTES DE LINHA — Execução com ReAct Loop (Story 1.12)
        # Não bloqueante: falha gera warning, 06_generate usa fallback
        print("\n\n═══ AGENTES DE LINHA: EXECUÇÃO ReAct ═══")
        agentes_ok = executar_script('05c_run_line_agents.py')
        if not agentes_ok:
            print("  ⚠️  Agentes de linha falharam — 06_generate usará fallback")
        report['decisao']['agentes_linha_ok'] = agentes_ok

        # GATE 2 — Composição de nodes
        print("\n\n═══ GATE 2: COMPOSIÇÃO DE NODES ═══")
        nodes_incluidos = compor_nodes(triagem, coleta, config, tipo_edicao)
        node_config = {
            'nodes': nodes_incluidos,
            'tipo_edicao': tipo_edicao,
            'clone_sugerido': gate_fin.get('clone_detectado'),
        }
        report['decisao']['nodes_incluidos'] = nodes_incluidos
        report['decisao']['justificativa'] = (
            f"Tipo '{tipo_edicao}' — {len(nodes_incluidos)} nodes | "
            f"Gate financeiro: {gate_fin.get('justificativa', '')}"
        )

        # FASE 3 — Geração de conteúdo
        print("\n\n═══ FASE 3: GERAÇÃO DE CONTEÚDO ═══")
        atualizar_status('geracao')
        if not executar_geracao(node_config):
            raise RuntimeError("Geração de conteúdo falhou")

        # DETECTOR DE SENSIBILIDADE (Story 1.13) — não-bloqueante
        print("\n\n═══ DETECTOR DE SENSIBILIDADE ═══")
        sensibilidade_ok = executar_script('06b_sensitivity_detector.py')
        if not sensibilidade_ok:
            print("  ⚠️  Detector de sensibilidade falhou — 08_notify usará comportamento padrão")
        report['decisao']['sensibilidade_ok'] = sensibilidade_ok

        # FASE 4 — Template HTML
        print("\n\n═══ FASE 4: TEMPLATE HTML ═══")
        if not executar_template(node_config):
            raise RuntimeError("População do template falhou")

        # FASE 5 — Notificação
        print("\n\n═══ FASE 5: NOTIFICAÇÃO ═══")
        atualizar_status('aguardando_aprovacao')
        executar_notificacao()  # Não bloqueia mesmo se falhar

        # Salvar relatório final
        salvar_orchestration_report(report)

        print("\n\n✅ Pipeline concluído com sucesso!")
        print(f"   Edição: {edicao_numero} | Tipo: {tipo_edicao} | Nodes: {len(nodes_incluidos)}")

    except Exception as e:
        report['decisao']['justificativa'] = f"Erro fatal: {str(e)}"
        salvar_orchestration_report(report)
        print(f"\n❌ Erro fatal no pipeline: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
