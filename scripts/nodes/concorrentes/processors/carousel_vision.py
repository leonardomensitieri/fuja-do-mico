"""
Processor: carousel_vision.py
==============================
Extrai texto de carrosséis Instagram via Claude Vision.
Processa cada slide individualmente; concatena com '\n---\n'.

Custo estimado: ~$0.015 por carrossel de 5 slides (Sonnet com imagem).
"""

import anthropic

PROMPT_SLIDE = (
    "Extraia todo texto, tabelas, gráficos e dados financeiros visíveis neste slide. "
    "Se houver gráfico, descreva o que mostra e os valores. "
    "Se houver tabela, extraia os dados em formato estruturado."
)


def processar_carrossel(item: dict, client: anthropic.Anthropic) -> str:
    """
    Extrai texto de todos os slides de um carrossel via Claude Vision.
    Fallback: caption original do post se Vision falhar em todos os slides.
    Tratamento por slide: falha em um slide não interrompe os demais (AC 2).
    """
    if item.get('type') != 'Sidecar' or not item.get('images'):
        return item.get('caption', '')

    texto_slides = []
    for i, img_url in enumerate(item['images']):
        try:
            response = client.messages.create(
                model='claude-sonnet-4-6',
                max_tokens=1024,
                messages=[{
                    'role': 'user',
                    'content': [
                        {'type': 'image', 'source': {'type': 'url', 'url': img_url}},
                        {'type': 'text', 'text': PROMPT_SLIDE}
                    ]
                }]
            )
            texto_slides.append(response.content[0].text)
        except Exception as e:
            print(f'  ⚠️  Vision falhou no slide {i + 1} ({e}) — continuando')

    if texto_slides:
        return '\n---\n'.join(texto_slides)

    # Fallback: caption original
    return item.get('caption', '')
