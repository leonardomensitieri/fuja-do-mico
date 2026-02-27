"""
Módulo clones — carregamento de prompts do catálogo de clones editoriais.

Export principal:
    load_clone_prompt(clone_id, **kwargs) -> str
        Carrega o Prompt Base da ficha e substitui placeholders.
        Lança FileNotFoundError se clone_id não existir.
"""

from scripts.clones.loader import load_clone_prompt

__all__ = ["load_clone_prompt"]
