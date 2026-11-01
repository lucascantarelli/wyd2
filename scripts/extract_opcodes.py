#!/usr/bin/env python3
"""Gera spec/opcodes.yaml a partir de Basedef.h.

Cada constante `const short _MSG_X = (base | FLAG_*);` vira uma entrada com
valor decimal/hex, base e direcoes. O objetivo e ter um registro legivel por
maquina que o gateway possa carregar e o CI possa comparar com a fonte.

Fonte: reference/w2pp-OpenWYD/Source/Code/Basedef.h (GPLv3).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reference" / "w2pp-OpenWYD" / "Source" / "Code" / "Basedef.h"
OUT = ROOT / "spec" / "opcodes.yaml"

FLAGS = {
    "FLAG_GAME2CLIENT": 0x0100,
    "FLAG_CLIENT2GAME": 0x0200,
    "FLAG_DB2GAME": 0x0400,
    "FLAG_GAME2DB": 0x0800,
    "FLAG_DB2NP": 0x1000,
    "FLAG_NP2DB": 0x2000,
    "FLAG_NEW": 0x4000,
}

DIRECTIONS = {
    "FLAG_GAME2CLIENT": "game_to_client",
    "FLAG_CLIENT2GAME": "client_to_game",
    "FLAG_DB2GAME": "db_to_game",
    "FLAG_GAME2DB": "game_to_db",
    "FLAG_DB2NP": "db_to_np",
    "FLAG_NP2DB": "np_to_db",
    "FLAG_NEW": "new_family",
}

CONST_RE = re.compile(r"const\s+short\s+(_(?:MSG|S)_\w+)\s*=\s*\(([^;]+)\);")

# Mensagens que o servidor novo precisa implementar primeiro.
CORE_ENTRIES = {
    "_MSG_AccountLogin",
    "_MSG_CreateCharacter",
    "_MSG_DeleteCharacter",
    "_MSG_CharacterLogin",
    "_MSG_CharacterLogout",
    "_MSG_MessageChat",
    "_MSG_MessageWhisper",
    "_MSG_Action",
    "_MSG_Action2",
    "_MSG_Action3",
    "_MSG_Attack",
    "_MSG_AttackOne",
    "_MSG_AttackTwo",
    "_MSG_UseItem",
    "_MSG_TradingItem",
    "_MSG_Buy",
    "_MSG_Sell",
    "_MSG_Trade",
    "_MSG_QuitTrade",
    "_MSG_GetItem",
    "_MSG_DropItem",
    "_MSG_ApplyBonus",
    "_MSG_CombineItem",
    "_MSG_AccountSecure",
    "_MSG_Deposit",
    "_MSG_Withdraw",
    "_MSG_Ping",
    "_MSG_CNFAccountLogin",
    "_MSG_CNFCharacterLogin",
    "_MSG_CNFCharacterLogout",
    "_MSG_CreateMob",
    "_MSG_RemoveMob",
    "_MSG_SendItem",
    "_MSG_SetHpMp",
    "_MSG_UpdateScore",
    "_MSG_ShopList",
    "_MSG_MessagePanel",
    "_MSG_MessageBoxOk",
}

# Handlers conhecidos (cliente -> servidor), por constante.
HANDLERS = {
    "_MSG_AccountLogin": "Exec_MSG_AccountLogin",
    "_MSG_CreateCharacter": "Exec_MSG_CreateCharacter",
    "_MSG_DeleteCharacter": "Exec_MSG_DeleteCharacter",
    "_MSG_CharacterLogin": "Exec_MSG_CharacterLogin",
    "_MSG_CharacterLogout": "Exec_MSG_CharacterLogout",
    "_MSG_MessageChat": "Exec_MSG_MessageChat",
    "_MSG_MessageWhisper": "Exec_MSG_MessageWhisper",
    "_MSG_Action": "Exec_MSG_Action",
    "_MSG_Action2": "Exec_MSG_Action",
    "_MSG_Action3": "Exec_MSG_Action",
    "_MSG_Attack": "Exec_MSG_Attack",
    "_MSG_AttackOne": "Exec_MSG_Attack",
    "_MSG_AttackTwo": "Exec_MSG_Attack",
    "_MSG_UseItem": "Exec_MSG_UseItem",
    "_MSG_TradingItem": "Exec_MSG_TradingItem",
    "_MSG_Buy": "Exec_MSG_Buy",
    "_MSG_Sell": "Exec_MSG_Sell",
    "_MSG_Trade": "Exec_MSG_Trade",
    "_MSG_QuitTrade": "Exec_MSG_QuitTrade",
    "_MSG_GetItem": "Exec_MSG_GetItem",
    "_MSG_DropItem": "Exec_MSG_DropItem",
    "_MSG_ApplyBonus": "Exec_MSG_ApplyBonus",
    "_MSG_CombineItem": "Exec_MSG_CombineItem",
    "_MSG_AccountSecure": "Exec_MSG_AccountSecure",
    "_MSG_Deposit": "Exec_MSG_Deposit",
    "_MSG_Withdraw": "Exec_MSG_Withdraw",
    "_MSG_Ping": "(no-op)",
}


def evaluate(expr: str) -> tuple[int, list[str]] | None:
    """Avalia `base | FLAG_A | FLAG_B` e devolve valor + flags."""
    flags: list[str] = []
    total = 0
    found_literal = False
    for token in re.split(r"\|", expr):
        token = token.strip()
        if not token:
            continue
        if token.startswith("FLAG_"):
            if token not in FLAGS:
                return None
            total |= FLAGS[token]
            flags.append(token)
        else:
            try:
                total |= int(token, 0)
                found_literal = True
            except ValueError:
                return None
    if not found_literal:
        return None
    return total, flags


def main() -> None:
    text = SOURCE.read_text(encoding="latin-1")
    entries = []
    for name, expr in CONST_RE.findall(text):
        result = evaluate(expr)
        if result is None:
            continue
        value, flags = result
        entries.append((value, name, flags))

    entries.sort()
    lines = [
        "# Registro de opcodes do WYD (gerado automaticamente).",
        "#",
        "# Fonte: reference/w2pp-OpenWYD/Source/Code/Basedef.h",
        "# Gerado por: scripts/extract_opcodes.py -- NAO editar a mao.",
        "#",
        "# `value` e o valor de fio (base | flags). `base` e o valor sem flags.",
        "# `directions` traduz os bits FLAG_*; a mesma base pode aparecer em",
        "# familias diferentes, e as flags que desambiguam.",
        "",
        "source: " + str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "count: " + str(len(entries)),
        "opcodes:",
    ]

    for value, name, flags in entries:
        base = value
        for flag in flags:
            base &= ~FLAGS[flag]
        directions = [DIRECTIONS[f] for f in flags if f in DIRECTIONS]
        core = "true" if name in CORE_ENTRIES else "false"
        lines.append(f"  - constant: {name}")
        lines.append(f"    value: {value}")
        lines.append(f"    hex: '0x{value:04X}'")
        lines.append(f"    base: {base}")
        lines.append("    directions: [" + ", ".join(directions) + "]")
        if name in HANDLERS:
            lines.append(f"    handler: {HANDLERS[name]}")
        lines.append(f"    core: {core}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(entries)} opcodes -> {OUT}")
    print(f"core: {sum(1 for _, n, _ in entries if n in CORE_ENTRIES)}")


if __name__ == "__main__":
    main()
