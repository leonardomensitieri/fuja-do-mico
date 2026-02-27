"""
CloneLoader — carregamento de prompts do catálogo de clones editoriais.

Decision tree: Worker Script — I/O de arquivo, sem lógica de negócio.
Localiza a ficha em config/clone_catalog/clone-{clone_id}.md,
extrai a seção ## Prompt Base e substitui placeholders via str.format_map().

Nota de design: FileNotFoundError é intencional aqui — ao contrário dos Tool.execute(),
que encapsulam erros, o loader falha ruidosamente para que o chamador detecte
imediatamente um clone_id incorreto no momento da configuração do agente.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

# Localização do catálogo relativa a este arquivo:
# scripts/clones/loader.py → ../../config/clone_catalog/
_CATALOG_DIR = Path(__file__).parent.parent.parent / "config" / "clone_catalog"


def load_clone_prompt(clone_id: str, **kwargs) -> str:
    """
    Carrega o Prompt Base de uma ficha de clone e substitui placeholders.

    Args:
        clone_id: identificador do clone (ex: "graham", "buffett", "contextual_l1")
        **kwargs: placeholders a substituir no prompt (ex: ticker="PETR4", tema="dividendos")

    Returns:
        String com o prompt pronto para uso como system_prompt do ReActAgent.

    Raises:
        FileNotFoundError: se clone_id não existir no catálogo
        ValueError: se a ficha não contiver a seção ## Prompt Base
    """
    ficha_path = _CATALOG_DIR / f"clone-{clone_id}.md"

    if not ficha_path.exists():
        disponiveis = _listar_clones()
        raise FileNotFoundError(
            f"Clone '{clone_id}' não encontrado em {_CATALOG_DIR}. "
            f"Clone_ids disponíveis ({len(disponiveis)}): {disponiveis}"
        )

    conteudo = ficha_path.read_text(encoding="utf-8")
    prompt = _extrair_prompt_base(conteudo, clone_id)

    if kwargs:
        prompt = prompt.format_map(kwargs)

    return prompt


def _extrair_prompt_base(conteudo: str, clone_id: str = "") -> str:
    """Extrai o conteúdo da seção ## Prompt Base do markdown da ficha."""
    match = re.search(
        r"##\s+Prompt Base\s*\n(.*?)(?=\n##\s|\Z)",
        conteudo,
        re.DOTALL,
    )
    if not match:
        raise ValueError(
            f"Seção '## Prompt Base' não encontrada na ficha do clone '{clone_id}'. "
            "Verifique o formato da ficha em config/clone_catalog/."
        )
    return match.group(1).strip()


def _listar_clones() -> List[str]:
    """Retorna lista ordenada de clone_ids disponíveis no catálogo."""
    if not _CATALOG_DIR.exists():
        return []
    return [
        p.stem.replace("clone-", "")
        for p in sorted(_CATALOG_DIR.glob("clone-*.md"))
    ]
