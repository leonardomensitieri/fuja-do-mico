"""
Teste local da lógica do orquestrador (sem chamadas reais a APIs).
Testa os 3 cenários do Gate 1: completa, reduzida e abortado.
Executa apenas as funções de decisão — não chama scripts externos.
"""

import json
import sys
from pathlib import Path

import importlib.util

# Carrega o orquestrador via importlib (nome começa com dígito — não importável diretamente)
_spec = importlib.util.spec_from_file_location(
    'orchestrator',
    Path(__file__).parent / 'scripts' / '00_orchestrator.py'
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

carregar_config = _mod.carregar_config
avaliar_gate1 = _mod.avaliar_gate1
compor_nodes = _mod.compor_nodes


def testar_cenario(nome: str, triagem: dict, coleta: dict, config: dict):
    print(f"\n{'═' * 50}")
    print(f"CENÁRIO: {nome}")
    print(f"{'═' * 50}")
    print(f"  Triagem: ALTO={triagem['alto']}, MEDIO={triagem['medio']}")

    tipo = avaliar_gate1(triagem, config)
    print(f"  Gate 1 → {tipo}")

    if tipo != 'abortado':
        nodes = compor_nodes(triagem, coleta, config, tipo)
        print(f"  Gate 2 → {nodes}")
    else:
        print("  Gate 2 → PULADO (pipeline abortado)")

    return tipo


def main():
    print("🧪 Testando lógica de decisão do orquestrador...\n")

    # Carregar config real
    config = carregar_config()
    print(f"Config carregada: thresholds={config.get('thresholds')}")
    print(f"Nodes configurados: {[n['id'] for n in config.get('nodes', [])]}")

    coleta_com_brapi = {'brapi_disponivel': True}
    coleta_sem_brapi = {'brapi_disponivel': False}

    # CENÁRIO 1: Edição completa (ALTO >= 3)
    tipo1 = testar_cenario(
        "EDIÇÃO COMPLETA (ALTO=3)",
        triagem={'alto': 3, 'medio': 1, 'baixo': 5, 'total_aprovados': 4},
        coleta=coleta_com_brapi,
        config=config
    )
    assert tipo1 == 'completa', f"Esperado 'completa', obtido '{tipo1}'"

    # CENÁRIO 2: Edição reduzida (ALTO=1)
    tipo2 = testar_cenario(
        "EDIÇÃO REDUZIDA (ALTO=1)",
        triagem={'alto': 1, 'medio': 2, 'baixo': 8, 'total_aprovados': 3},
        coleta=coleta_sem_brapi,
        config=config
    )
    assert tipo2 == 'reduzida', f"Esperado 'reduzida', obtido '{tipo2}'"

    # CENÁRIO 3: Edição reduzida por MEDIO >= 3
    tipo3 = testar_cenario(
        "EDIÇÃO REDUZIDA (MEDIO=3)",
        triagem={'alto': 0, 'medio': 3, 'baixo': 10, 'total_aprovados': 3},
        coleta=coleta_com_brapi,
        config=config
    )
    assert tipo3 == 'reduzida', f"Esperado 'reduzida', obtido '{tipo3}'"

    # CENÁRIO 4: Abortado
    tipo4 = testar_cenario(
        "ABORTADO (ALTO=0, MEDIO=2)",
        triagem={'alto': 0, 'medio': 2, 'baixo': 12, 'total_aprovados': 2},
        coleta=coleta_com_brapi,
        config=config
    )
    assert tipo4 == 'abortado', f"Esperado 'abortado', obtido '{tipo4}'"

    print(f"\n\n{'═' * 50}")
    print("✅ TODOS OS CENÁRIOS PASSARAM!")
    print(f"{'═' * 50}")


if __name__ == '__main__':
    main()
