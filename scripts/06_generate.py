"""
SCRIPT 06 — Geração de Conteúdo (IA)
======================================
Clone com Heurísticas (Finance/Invest — geração de conteúdo)

Arquitetura: main() é o orquestrador dos agentes operacionais de geração.
Cada agente operacional = 1 função Python + 1 chamada dedicada à API.

Agentes operacionais:
  - agente_editorial()  → editorial de abertura + campos base (Haiku)
  - agente_conteudo()   → corpo completo da edição como sections[] (Sonnet)

O agente_conteudo() decide livremente a estrutura da edição:
  - Quantas seções, de quais tipos, em que ordem
  - Se inclui análise de investidores, tabela Brapi, checklist, etc.
  - A identidade visual é responsabilidade do script 07 (renderer)

Clones de investidores carregados dinamicamente de:
  prompts/clones/finance-investments/

Credenciais necessárias (GitHub Secrets):
  - ANTHROPIC_API_KEY : chave da API da Anthropic

Variáveis de ambiente passadas pelo orquestrador (00_orchestrator.py):
  - TEMA_FORCADO : (opcional) força o tema da edição
"""

import os
import json
import anthropic
from pathlib import Path
from datetime import datetime


def carregar_clones(area: str) -> str:
    """
    Carrega todos os clones de uma área dinamicamente.
    Extensível: adicionar novo clone = criar novo arquivo .md no diretório.
    """
    diretorio = Path(f'prompts/clones/{area}')
    if not diretorio.exists():
        return f"Nenhum clone encontrado para área: {area}"
    clones = []
    for arquivo in sorted(diretorio.glob('*.md')):
        nome = arquivo.stem.replace('-', ' ').title()
        conteudo = arquivo.read_text(encoding='utf-8')
        clones.append(f"## {nome}\n{conteudo}")
    return '\n\n---\n\n'.join(clones)


def carregar_prompt_agente(nome: str) -> str:
    """Carrega o prompt de um agente operacional pelo nome."""
    return Path(f'prompts/agents/{nome}.md').read_text(encoding='utf-8')


def resumir_conteudo_triado(triados: list) -> str:
    """Formata o conteúdo triado para injetar no contexto dos agentes."""
    resumos = []
    for item in triados[:15]:  # Usa os 15 mais relevantes
        triagem = item.get('triagem', {})
        resumos.append(
            f"FONTE: {item.get('fonte', 'desconhecida')}\n"
            f"TÍTULO: {item.get('titulo', item.get('assunto', ''))}\n"
            f"RELEVÂNCIA: {triagem.get('relevancia', '')}\n"
            f"TEMA: {', '.join(triagem.get('temas_identificados', []))}\n"
            f"ÂNGULO: {triagem.get('angulo_potencial_para_newsletter', '')}\n"
            f"RESUMO: {triagem.get('resumo_em_3_linhas', '')}\n"
            "---"
        )
    return '\n'.join(resumos)


def resumir_dados_mercado(acoes_brapi: list, dados_fintz: dict) -> str:
    """
    Formata os dados de mercado (Brapi + Fintz) para injetar no contexto dos agentes.
    Merge automático: Fintz complementa campos ausentes no Brapi (especialmente DY).
    """
    # Monta índice Fintz por ticker para merge
    fintz_por_ticker = {}
    for acao in dados_fintz.get("acoes", []):
        fintz_por_ticker[acao.get("ticker", "")] = acao

    # Une Brapi + Fintz: usa Brapi como base, Fintz complementa campos ausentes
    acoes_unificadas = []
    tickers_processados = set()

    for acao_brapi in acoes_brapi:
        ticker = acao_brapi.get("ticker", "")
        tickers_processados.add(ticker)
        merged = {**acao_brapi}

        # Complementa com Fintz (DY, métricas de endividamento, etc.)
        acao_fintz = fintz_por_ticker.get(ticker, {})
        for campo in ["dy", "ev_ebitda", "divida_bruta_pl", "divida_liq_ebitda",
                      "roic", "margem_ebitda", "proventos_total_12m"]:
            if campo not in merged and campo in acao_fintz:
                merged[campo] = acao_fintz[campo]

        # Prefere Fintz para P/L quando Brapi não tem
        if "pl" not in merged and "pl" in acao_fintz:
            merged["pl"] = acao_fintz["pl"]

        acoes_unificadas.append(merged)

    # Adiciona tickers que só estão no Fintz
    for ticker, acao_fintz in fintz_por_ticker.items():
        if ticker not in tickers_processados:
            acoes_unificadas.append(acao_fintz)

    if not acoes_unificadas:
        return "Dados financeiros não disponíveis nesta edição."

    def fmt(val, pct=False, mult=False):
        if val is None:
            return "N/D"
        if pct:
            return f"{val * 100:.1f}%"
        if mult:
            return f"{val:.1f}x"
        return str(round(val, 2))

    linhas = ["Dados financeiros atuais das ações monitoradas (Brapi + Fintz):"]
    for acao in acoes_unificadas:
        linhas.append(
            f"- {acao.get('ticker')}: "
            f"P/L={fmt(acao.get('pl'), mult=True)}, "
            f"P/VP={fmt(acao.get('pvp'), mult=True)}, "
            f"DY={fmt(acao.get('dy'), pct=True)}, "
            f"ROE={fmt(acao.get('roe'), pct=True)}, "
            f"EV/EBITDA={fmt(acao.get('ev_ebitda'), mult=True)}, "
            f"Dívida/PL={fmt(acao.get('divida_bruta_pl'), mult=True)}"
        )

    # Adiciona contexto do Tesouro Direto se disponível
    tesouro = dados_fintz.get("tesouro", [])
    if tesouro:
        linhas.append("\nTesouro Direto disponível (referência de taxa livre de risco):")
        for titulo in tesouro[:5]:  # Limita a 5 títulos
            linhas.append(f"  - {titulo['nome']} (vence {titulo['vencimento']})")

    return '\n'.join(linhas)


def resumir_dados_brapi(acoes: list) -> str:
    """Compatibilidade retroativa — chama resumir_dados_mercado sem Fintz."""
    return resumir_dados_mercado(acoes, {})


def extrair_json(texto: str, agente: str) -> dict:
    """Extrai e parseia o JSON da resposta do agente operacional."""
    inicio = texto.find('{')
    fim = texto.rfind('}') + 1
    if inicio < 0 or fim <= inicio:
        raise ValueError(f"Agente {agente} não retornou JSON válido. Resposta: {texto[:300]}")
    return json.loads(texto[inicio:fim])


# =============================================================================
# AGENTES OPERACIONAIS
# =============================================================================

def agente_editorial(contexto: dict, cliente: anthropic.Anthropic) -> dict:
    """
    Agente Operacional: Clone com Heurísticas
    Gera o editorial de abertura da edição + campos base (título, tags, tempo).
    Modelo: Haiku (criativo, baixo custo)
    Output: editorial, titulo_edicao, tempo_leitura, tags
    """
    print("  [agente_editorial] Gerando editorial...")
    prompt = carregar_prompt_agente('agente-editorial')
    prompt_final = f"""{prompt}

## Contexto da Edição
Tema: {contexto['tema']}
Tipo de edição: {contexto['tipo_edicao']}

## Conteúdo Selecionado na Triagem
{contexto['conteudo_triado']}
"""
    resposta = cliente.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt_final}]
    )
    return extrair_json(resposta.content[0].text.strip(), 'agente_editorial')


def agente_conteudo(contexto: dict, clones_texto: str, cliente: anthropic.Anthropic) -> dict:
    """
    Agente Operacional: Clone com Heurísticas
    Gera o corpo completo da edição como um array de sections.
    Decide livremente a estrutura: quais seções, em que ordem, com quais tipos.
    Modelo: Sonnet (qualidade e raciocínio necessários para estruturar bem)
    Output: {"sections": [...]}
    """
    print("  [agente_conteudo] Gerando corpo da edição (sections)...")
    prompt = carregar_prompt_agente('agente-conteudo')
    prompt_com_clones = prompt.replace('{{CLONES}}', clones_texto) if '{{CLONES}}' in prompt else prompt

    prompt_final = f"""{prompt_com_clones}

## Tema da Edição
{contexto['tema']}

## Dados Financeiros Disponíveis (Brapi)
{contexto['dados_brapi']}

## Conteúdo Selecionado na Triagem
{contexto['conteudo_triado']}

## Clones de Investidores Disponíveis (use apenas se o tema pedir)
{clones_texto}
"""
    resposta = cliente.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt_final}]
    )
    return extrair_json(resposta.content[0].text.strip(), 'agente_conteudo')


# =============================================================================
# SALVAMENTO
# =============================================================================

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


# =============================================================================
# ORQUESTRADOR DOS AGENTES OPERACIONAIS
# =============================================================================

def main():
    print("✍️  Iniciando geração de conteúdo...")

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY não configurado!")

    # Carregar dados brutos
    triados = json.loads(Path('data/conteudo_triado.json').read_text(encoding='utf-8'))

    acoes_brapi = (
        json.loads(Path('data/brapi_raw.json').read_text(encoding='utf-8'))
        if Path('data/brapi_raw.json').exists()
        else []
    )
    dados_fintz = (
        json.loads(Path('data/fintz_raw.json').read_text(encoding='utf-8'))
        if Path('data/fintz_raw.json').exists()
        else {}
    )
    tema_forcado = os.environ.get('TEMA_FORCADO', '').strip()

    # Contexto compartilhado passado para todos os agentes operacionais
    contexto = {
        'tema': tema_forcado if tema_forcado else 'Escolha o tema mais relevante com base no conteúdo triado',
        'conteudo_triado': resumir_conteudo_triado(triados),
        'dados_brapi': resumir_dados_mercado(acoes_brapi, dados_fintz),
        'tipo_edicao': 'completa',
    }

    cliente = anthropic.Anthropic(api_key=api_key)
    resultado = {}

    # Agente 1: editorial + campos base
    resultado.update(agente_editorial(contexto, cliente))

    # Agente 2: corpo da edição (sections livres)
    clones_texto = carregar_clones('finance-investments')
    resultado.update(agente_conteudo(contexto, clones_texto, cliente))

    # Metadados do pipeline
    resultado['data_geracao'] = datetime.now().strftime('%d/%m/%Y às %H:%M')
    resultado['acoes_brapi'] = acoes[:6]  # mantido para referência futura

    salvar_resultado(resultado, 'conteudo_gerado.json')

    titulo = resultado.get('titulo_edicao', 'sem título')
    n_sections = len(resultado.get('sections', []))
    print(f"✅ Edição gerada: '{titulo}'")
    print(f"  Sections geradas: {n_sections} | Salvo em data/conteudo_gerado.json")


if __name__ == '__main__':
    main()
