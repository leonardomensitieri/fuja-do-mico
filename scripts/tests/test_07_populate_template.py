"""
Testes unitários para scripts/07_populate_template.py.

Mock puro — nenhuma chamada HTTP real.
Cobre os cenários da AC 6:
    1. render_mermaid com mock urlopen → retorna string com <img
    2. render_mermaid com urlopen lançando exception → retorna string com <pre (fallback)
    3. render_mermaid sem code → retorna string vazia sem crash
    4. render_image com url, alt, caption → retorna HTML com <img
    5. render_image sem url → retorna string vazia sem crash
    6. SECTION_RENDERERS contém 'mermaid' e 'image'
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── Carregamento do módulo com prefixo numérico ───────────────────────────────

def _carregar_modulo_07():
    """Carrega scripts/07_populate_template.py via importlib (prefixo numérico)."""
    path = Path(__file__).resolve().parent.parent / "07_populate_template.py"
    spec = importlib.util.spec_from_file_location("_script_07", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _carregar_modulo_07()


# ── Testes de render_mermaid ───────────────────────────────────────────────────

class TestRenderMermaid:

    def test_com_mock_urlopen_retorna_img(self):
        """render_mermaid com urlopen mockado deve retornar HTML com <img."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.return_value = MagicMock()
            resultado = _mod.render_mermaid({'code': 'graph TD\n  A-->B'})
        assert '<img' in resultado

    def test_fallback_pre_quando_urlopen_falha(self):
        """render_mermaid com urlopen lançando exception deve retornar <pre (fallback)."""
        with patch('urllib.request.urlopen', side_effect=Exception('timeout')):
            resultado = _mod.render_mermaid({'code': 'graph TD\n  A-->B'})
        assert '<pre' in resultado

    def test_sem_code_retorna_vazio(self):
        """render_mermaid sem code deve retornar string vazia sem crash."""
        resultado = _mod.render_mermaid({})
        assert resultado == ''

    def test_code_vazio_retorna_vazio(self):
        """render_mermaid com code vazio deve retornar string vazia."""
        resultado = _mod.render_mermaid({'code': '   '})
        assert resultado == ''

    def test_com_caption_inclui_legenda_no_sucesso(self):
        """render_mermaid com caption deve incluir legenda quando HTTP funciona."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.return_value = MagicMock()
            resultado = _mod.render_mermaid({
                'code': 'graph TD\n  A-->B',
                'caption': 'Legenda do diagrama',
            })
        assert 'Legenda do diagrama' in resultado

    def test_com_caption_inclui_legenda_no_fallback(self):
        """render_mermaid com caption deve incluir legenda também no fallback <pre>."""
        with patch('urllib.request.urlopen', side_effect=Exception('erro')):
            resultado = _mod.render_mermaid({
                'code': 'graph TD\n  A-->B',
                'caption': 'Legenda fallback',
            })
        assert 'Legenda fallback' in resultado
        assert '<pre' in resultado


# ── Testes de render_image ─────────────────────────────────────────────────────

class TestRenderImage:

    def test_com_url_alt_caption_retorna_img(self):
        """render_image com campos completos deve retornar HTML com <img."""
        resultado = _mod.render_image({
            'url': 'https://exemplo.com/grafico.png',
            'alt': 'Gráfico PETR4',
            'caption': 'Fonte: Brapi',
        })
        assert '<img' in resultado

    def test_url_presente_no_src(self):
        """render_image deve incluir a URL no atributo src da imagem."""
        url = 'https://exemplo.com/imagem.png'
        resultado = _mod.render_image({'url': url})
        assert url in resultado

    def test_alt_presente_no_atributo(self):
        """render_image deve incluir o alt no atributo alt da imagem."""
        resultado = _mod.render_image({
            'url': 'https://exemplo.com/img.png',
            'alt': 'Descrição da imagem',
        })
        assert 'Descrição da imagem' in resultado

    def test_caption_presente_quando_fornecido(self):
        """render_image deve incluir legenda quando caption é fornecido."""
        resultado = _mod.render_image({
            'url': 'https://exemplo.com/img.png',
            'caption': 'Legenda da imagem',
        })
        assert 'Legenda da imagem' in resultado

    def test_sem_url_retorna_vazio(self):
        """render_image sem url deve retornar string vazia sem crash."""
        resultado = _mod.render_image({})
        assert resultado == ''

    def test_url_vazia_retorna_vazio(self):
        """render_image com url vazia deve retornar string vazia sem crash."""
        resultado = _mod.render_image({'url': '   '})
        assert resultado == ''

    def test_max_width_presente(self):
        """render_image deve aplicar max-width:100% para compatibilidade de email."""
        resultado = _mod.render_image({'url': 'https://exemplo.com/img.png'})
        assert 'max-width:100%' in resultado


# ── Testes de SECTION_RENDERERS ───────────────────────────────────────────────

class TestSectionRenderers:

    def test_contem_mermaid(self):
        """SECTION_RENDERERS deve conter a chave 'mermaid'."""
        assert 'mermaid' in _mod.SECTION_RENDERERS

    def test_contem_image(self):
        """SECTION_RENDERERS deve conter a chave 'image'."""
        assert 'image' in _mod.SECTION_RENDERERS

    def test_mermaid_e_callable(self):
        """SECTION_RENDERERS['mermaid'] deve ser uma função chamável."""
        assert callable(_mod.SECTION_RENDERERS['mermaid'])

    def test_image_e_callable(self):
        """SECTION_RENDERERS['image'] deve ser uma função chamável."""
        assert callable(_mod.SECTION_RENDERERS['image'])

    def test_renderers_existentes_preservados(self):
        """Todos os 11 section types existentes devem permanecer intactos."""
        tipos_existentes = [
            'h1', 'h2', 'paragraph', 'highlight', 'formula',
            'blockquote', 'investor', 'separator', 'table', 'checklist', 'list',
        ]
        for tipo in tipos_existentes:
            assert tipo in _mod.SECTION_RENDERERS, f"Renderer existente '{tipo}' não encontrado"
