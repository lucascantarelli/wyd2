"""Decodificacao do refino legado.

O efeito EF_SANC (43) nao guarda o nivel puro:

    niveis 0..9   cValue = nivel + 10 * pity
    niveis 10..15 cValue = 230 + 4*(nivel-10) + gem

Fonte: docs/05-PROGRESSAO-E-REFINO.md §6.2, derivado de BASE_SetItemSanc
(Basedef.cpp:2282-2330) e BASE_GetItemSanc (Basedef.cpp:2136-2190).
"""

from __future__ import annotations

EF_SANC = 43
EF_SANC_ALT_MIN = 116
EF_SANC_ALT_MAX = 125

PACKED_LEVEL_10_BASE = 230


def find_sanc_value(effects) -> int | None:
    """Retorna o cValue do primeiro portador de EF_SANC, ou None."""
    for effect in effects:
        if effect.type == EF_SANC or EF_SANC_ALT_MIN <= effect.type <= EF_SANC_ALT_MAX:
            return effect.value
    return None


def decode_sanc_value(value: int | None) -> tuple[int, int | None, int]:
    """Converte o cValue cru em (nivel, gem, pity).

    * nivel  : 0..15
    * gem    : 0..3 apenas para nivel >= 10, senao None
    * pity   : contador de falhas 0..20 (apenas nivel < 10)

    Valores fora do intervalo conhecido sao decodificados de forma tolerante e
    caberao ao reconciliador sinalizar (`refine_out_of_range`).
    """
    if value is None:
        return 0, None, 0

    if PACKED_LEVEL_10_BASE <= value <= 253:
        level = 10 + (value - PACKED_LEVEL_10_BASE) // 4
        gem = (value - PACKED_LEVEL_10_BASE) % 4
        return level, gem, 0

    level = value % 10
    pity = value // 10
    return level, None, pity


def is_valid_refine(level: int, pity: int) -> bool:
    return 0 <= level <= 15 and 0 <= pity <= 20
