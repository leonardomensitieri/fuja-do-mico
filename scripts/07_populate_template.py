"""
SCRIPT 07 — Popular Template HTML
====================================
Decision Tree: Criatividade? NÃO → Algoritmo? SIM → External API? NÃO → Worker Script

O que faz:
  - Lê o template HTML (shell) de templates/newsletter.html
  - Lê o conteúdo gerado (data/conteudo_gerado.json)
  - Renderiza cada section do array 'sections' como HTML,
    aplicando as regras visuais da identidade Liga HUB Finance (v5)
  - Substitui {{EDITORIAL}}, {{SECTIONS_HTML}}, {{ASSINANTE}} no shell
  - Salva o HTML final em output/newsletter_final.html

Sem credenciais necessárias — puro processamento local.

Variáveis de ambiente opcionais:
  - NEWSLETTER_TEMPLATE : nome do arquivo de template em templates/ (padrão: newsletter.html)

Identidade visual aplicada pelos renderers:
  - H1: fundo rosa #fce4ec, sem emoji
  - H2: limpo, sem highlight
  - highlight: fundo amarelo #fff176 + negrito
  - blockquote: borda esquerda 3px #cccccc, itálico
  - formula: Courier New, sem borda/background
  - investor: **Nome** — texto *(critério)*
  - table: bordas finas, cores semânticas inline
  - checklist: ☐ custom, separadores entre itens
"""

import base64
import json
import os
import random
import urllib.error
import urllib.request
from pathlib import Path


# Diretoria de research — usada na assinatura da newsletter
ASSINANTES = ['Leonardo Mensitieri', 'Mário Brok', 'Miguel', 'Kaique Azevedo']


# =============================================================================
# RENDERERS — cada função recebe um dict de section e retorna HTML string
# =============================================================================

def render_h1(s: dict) -> str:
    texto = s.get('text', '')
    return (
        f'<h1 style="font-family:Arial,sans-serif; font-size:28px; font-weight:700; '
        f'color:#0d1117; margin:0 0 20px 0; line-height:1.3;">'
        f'<span style="background-color:#fce4ec; padding:1px 4px;">{texto}</span>'
        f'</h1>'
    )


def render_h2(s: dict) -> str:
    texto = s.get('text', '')
    return (
        f'<h2 style="font-family:Arial,sans-serif; font-size:20px; font-weight:700; '
        f'color:#0d1117; margin:28px 0 12px 0; line-height:1.3;">{texto}</h2>'
    )


def render_paragraph(s: dict) -> str:
    texto = s.get('text', '')
    return f'<p style="margin:0 0 18px 0;">{texto}</p>'


def render_highlight(s: dict) -> str:
    """Frase de alto impacto — negrito + fundo amarelo. Máx 1-2 por edição."""
    texto = s.get('text', '')
    return (
        f'<p style="margin:0 0 18px 0;">'
        f'<strong><span style="background-color:#fff176; padding:1px 2px;">{texto}</span></strong>'
        f'</p>'
    )


def render_formula(s: dict) -> str:
    """Fórmula ou código — monospace puro, sem borda, sem background."""
    texto = s.get('text', '')
    return (
        f'<p style="font-family:\'Courier New\',Courier,monospace; font-size:14px; '
        f'margin:0 0 18px 0; color:#333333;">{texto}</p>'
    )


def render_blockquote(s: dict) -> str:
    """Citação ou lição — borda esquerda cinza, itálico."""
    label = s.get('label', '')
    texto = s.get('text', '')
    label_html = f'<strong style="font-style:normal;">{label}:</strong> ' if label else ''
    return (
        f'<blockquote style="border-left:3px solid #cccccc; margin:0 0 18px 20px; '
        f'padding:4px 0 4px 16px; color:#555555; font-style:italic;">'
        f'{label_html}{texto}'
        f'</blockquote>'
    )


def render_investor(s: dict) -> str:
    """Clone investidor — **Nome** — texto *(critério)*"""
    nome = s.get('name', '')
    texto = s.get('text', '')
    criterio = s.get('criterion', '')
    criterio_html = f' <em style="color:#555555;">({criterio})</em>' if criterio else ''
    return (
        f'<p style="margin:0 0 18px 0;">'
        f'<strong>{nome}</strong> — {texto}{criterio_html}'
        f'</p>'
    )


def render_separator(s: dict) -> str:
    return '<hr style="border:none; border-top:1px solid #e0e0e0; margin:36px 0;">'


def render_table(s: dict) -> str:
    """Tabela com headers cinza e cores semânticas inline nas células."""
    headers = s.get('headers', [])
    rows = s.get('rows', [])
    caption = s.get('caption', '')

    th_style = (
        'text-align:left; padding:8px 12px; border-bottom:1px solid #cccccc; '
        'color:#555555; font-weight:700;'
    )
    headers_html = ''.join(f'<th style="{th_style}">{h}</th>' for h in headers)

    rows_html = []
    for i, row in enumerate(rows):
        cells = row.get('cells', [])
        color = row.get('color', '#1a1a1a')
        is_last = i == len(rows) - 1
        border = '' if is_last else 'border-bottom:1px solid #eeeeee;'

        tds = []
        for j, cell in enumerate(cells):
            if j == 0:
                tds.append(
                    f'<td style="padding:8px 12px; {border}"><strong>{cell}</strong></td>'
                )
            else:
                tds.append(
                    f'<td style="padding:8px 12px; {border} color:{color}; font-weight:600;">{cell}</td>'
                )
        rows_html.append(f'<tr>{"".join(tds)}</tr>')

    caption_html = (
        f'<p style="font-size:12px; color:#999999; font-family:Arial,sans-serif; '
        f'margin:0 0 18px 0;">{caption}</p>'
    ) if caption else ''

    return (
        f'<table style="width:100%; border-collapse:collapse; font-family:Arial,sans-serif; '
        f'font-size:14px; margin:0 0 12px 0;">'
        f'<thead><tr>{headers_html}</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody>'
        f'</table>'
        f'{caption_html}'
    )


def render_checklist(s: dict) -> str:
    """Lista interativa com ☐ e separadores entre itens."""
    items = s.get('items', [])
    li_style_mid = 'padding:6px 0 6px 26px; position:relative; border-bottom:1px solid #f0f0f0;'
    li_style_last = 'padding:6px 0 6px 26px; position:relative;'
    checkbox = '<span style="position:absolute; left:0; top:5px; font-size:17px; color:#999999;">☐</span>'

    lis = []
    for i, item in enumerate(items):
        style = li_style_last if i == len(items) - 1 else li_style_mid
        lis.append(f'<li style="{style}">{checkbox}{item}</li>')

    return (
        f'<ul style="list-style:none; padding:0; margin:0 0 18px 0; '
        f'font-family:Arial,sans-serif; font-size:15px; color:#333333;">'
        f'{"".join(lis)}'
        f'</ul>'
    )


def render_list(s: dict) -> str:
    """Lista bullet padrão."""
    items = s.get('items', [])
    lis = ''.join(
        f'<li style="margin:0 0 8px 0;">{item}</li>'
        for item in items
    )
    return (
        f'<ul style="padding:0 0 0 20px; margin:0 0 18px 0; '
        f'font-family:Arial,sans-serif; font-size:15px; color:#333333;">'
        f'{lis}'
        f'</ul>'
    )


def _mermaid_url(code: str) -> str:
    """Monta a URL da imagem mermaid.ink para o código fornecido."""
    config = {'code': code, 'mermaid': {'theme': 'default'}}
    encoded = base64.b64encode(json.dumps(config).encode()).decode()
    return f'https://mermaid.ink/img/{encoded}'


def render_mermaid(s: dict) -> str:
    """Diagrama Mermaid — renderiza como imagem via mermaid.ink. Fallback: <pre>."""
    code = s.get('code', '').strip()
    caption = s.get('caption', '')
    if not code:
        return ''
    try:
        img_url = _mermaid_url(code)
        urllib.request.urlopen(img_url, timeout=10)  # Valida que a imagem existe
        caption_html = (
            f'<p style="font-size:12px; color:#999999; text-align:center; '
            f'margin:4px 0 18px 0;">{caption}</p>'
        ) if caption else '<br>'
        return (
            f'<div style="text-align:center; margin:0 0 18px 0;">'
            f'<img src="{img_url}" alt="Diagrama Mermaid" '
            f'style="max-width:100%; height:auto; border:1px solid #e0e0e0;">'
            f'</div>'
            f'{caption_html}'
        )
    except Exception as e:
        print(f'  ⚠️  mermaid.ink indisponível ({e}) — renderizando como código')
        caption_html = (
            f'<p style="font-size:12px; color:#999999; margin:0 0 18px 0;">{caption}</p>'
        ) if caption else ''
        return (
            f'<pre style="background:#f5f5f5; padding:12px; font-size:13px; '
            f'overflow-x:auto; margin:0 0 18px 0; border:1px solid #e0e0e0;">{code}</pre>'
            f'{caption_html}'
        )


def render_image(s: dict) -> str:
    """Imagem por URL — selecionada manualmente ou gerada automaticamente."""
    url = s.get('url', '').strip()
    if not url:
        return ''
    alt = s.get('alt', 'Imagem da newsletter')
    caption = s.get('caption', '')
    caption_html = (
        f'<p style="font-size:12px; color:#999999; text-align:center; '
        f'margin:4px 0 18px 0;">{caption}</p>'
    ) if caption else '<br>'
    return (
        f'<div style="text-align:center; margin:0 0 18px 0;">'
        f'<img src="{url}" alt="{alt}" '
        f'style="max-width:100%; height:auto;">'
        f'</div>'
        f'{caption_html}'
    )


# Mapa type → renderer
SECTION_RENDERERS = {
    'h1':         render_h1,
    'h2':         render_h2,
    'paragraph':  render_paragraph,
    'highlight':  render_highlight,
    'formula':    render_formula,
    'blockquote': render_blockquote,
    'investor':   render_investor,
    'separator':  render_separator,
    'table':      render_table,
    'checklist':  render_checklist,
    'list':       render_list,
    'mermaid':    render_mermaid,
    'image':      render_image,
}


def renderizar_secoes(sections: list) -> str:
    """
    Itera sobre o array de sections e renderiza cada uma como HTML.
    Types desconhecidos são ignorados silenciosamente.
    """
    partes = []
    for section in sections:
        tipo = section.get('type', '')
        renderer = SECTION_RENDERERS.get(tipo)
        if renderer:
            partes.append(renderer(section))
        else:
            print(f"  ⚠️  Section type desconhecido ignorado: '{tipo}'")
    return '\n\n'.join(partes)


def salvar_resultado(dados: dict, arquivo: str, edicao_id: str = None):
    """
    Persiste resultado localmente e no banco (se configurado).
    Retrocompatível: sem SUPABASE_URL, apenas salva o arquivo HTML.
    """
    Path('output').mkdir(exist_ok=True)
    Path(f'output/{arquivo}').write_text(dados['html'], encoding='utf-8')


def main():
    print("🎨 Populando template HTML...")

    # Carregar conteúdo gerado
    conteudo = json.loads(Path('data/conteudo_gerado.json').read_text(encoding='utf-8'))

    # Carregar shell do template
    template_file = os.environ.get('NEWSLETTER_TEMPLATE', 'newsletter.html')
    template = Path(f'templates/{template_file}').read_text(encoding='utf-8')

    # Renderizar sections
    sections = conteudo.get('sections', [])
    sections_html = renderizar_secoes(sections)

    # Substituir os 3 placeholders do shell
    html = template
    html = html.replace('{{EDITORIAL}}', conteudo.get('editorial', ''))
    html = html.replace('{{SECTIONS_HTML}}', sections_html)
    html = html.replace('{{ASSINANTE}}', random.choice(ASSINANTES))

    # Salvar HTML final
    output_name = template_file.replace('.html', '_final.html')
    salvar_resultado({'html': html}, output_name)

    print(f"✅ Template populado → output/{output_name}")
    print(f"  Sections renderizadas: {len(sections)}")
    print(f"  Tamanho do arquivo: {len(html):,} caracteres")


if __name__ == '__main__':
    main()
