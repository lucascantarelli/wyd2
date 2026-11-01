#!/usr/bin/env python3
"""Extrai a tabela de balanceamento classe x arma de BASE_GetCurrentScore.

Fonte: reference/w2pp-OpenWYD/Source/Code/Basedef.cpp (GPLv3), bloco
"// Balanceamento" (~linha 3249+). O codigo repete a mesma tabela dentro de
cada gate de skill aprendida; este script deduplica e registra o gate.

Saida: data/class_weapon_coefficients.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reference" / "w2pp-OpenWYD" / "Source" / "Code" / "Basedef.cpp"
OUT = ROOT / "data" / "class_weapon_coefficients.json"

CLASSES = {0: "TransKnight", 1: "Foema", 2: "BeastMaster", 3: "Huntress"}
WEAPONS = {
    41: "Balmung",
    42: "Arco",
    43: "Garra",
    44: "Lanca",
    45: "Caliburn",
    46: "Hermai",
    47: "Cajado/Cetro",
    48: "Espada 2 maos",
    49: "Martelo",
}


def block_after(text: str, start: int) -> str:
    """Conteudo do primeiro bloco { ... } que comeca em/after `start`."""
    open_at = text.find("{", start)
    if open_at < 0:
        return ""
    depth = 1
    i = open_at + 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[open_at + 1 : i - 1]


def find_class_block(text: str, class_id: int) -> str:
    match = re.search(rf"if\s*\(MOB\.Class\s*==\s*{class_id}\)", text)
    if not match:
        return ""
    return block_after(text, match.start())


def gate_name(comment: str) -> str:
    return re.sub(r"\s+", " ", comment).strip() or "(sem comentario)"


def parse_gates(block: str) -> list[dict]:
    rows: list[dict] = []
    # Cada gate comeca numa linha "if (MOB.LearnedSkill & (1 << N)) // nome"
    gate_iter = list(
        re.finditer(r"if\s*\(MOB\.LearnedSkill\s*&\s*\(1\s*<<\s*(\d+)\)\)\s*(?://\s*(.*))?", block)
    )
    for index, gate in enumerate(gate_iter):
        bit = int(gate.group(1))
        name = gate_name(gate.group(2) or "")
        end = gate_iter[index + 1].start() if index + 1 < len(gate_iter) else len(block)
        body = block[gate.start() : end]

        for weapon in re.finditer(r"if\s*\(ArmaUnique\s*==\s*(\d+)\)\s*(?://\s*(.*))?", body):
            uid = int(weapon.group(1))
            seq_end = body.find("if (ArmaUnique", weapon.end())
            segment = body[weapon.end() : seq_end if seq_end > 0 else len(body)]

            physical = re.search(
                r"CurrentScore\.Damage\s*=\s*MOB\.CurrentScore\.Damage\s*\+\s*"
                r"\(\(MOB\.CurrentScore\.Dex\s*\*\s*([\d.]+)\)\s*\+\s*"
                r"\(MOB\.CurrentScore\.Str\s*\*\s*([\d.]+)\)\)",
                segment,
            )
            magic = re.search(
                r"magic\s*=\s*magic\s*\+\s*\(\(\(MOB\.CurrentScore\.Dex\s*\*\s*([\d.]+)\)\s*\+\s*"
                r"\(MOB\.CurrentScore\.Int\s*\*\s*([\d.]+)\)\)\s*/\s*100\)",
                segment,
            )
            if physical:
                rows.append(
                    {
                        "gate_bit": bit,
                        "gate": name,
                        "weapon_unique": uid,
                        "weapon": WEAPONS.get(uid, f"unique {uid}"),
                        "kind": "physical",
                        "dex_coefficient": float(physical.group(1)),
                        "str_coefficient": float(physical.group(2)),
                    }
                )
            elif magic:
                rows.append(
                    {
                        "gate_bit": bit,
                        "gate": name,
                        "weapon_unique": uid,
                        "weapon": WEAPONS.get(uid, f"unique {uid}"),
                        "kind": "magic",
                        "dex_coefficient": float(magic.group(1)),
                        "int_coefficient": float(magic.group(2)),
                    }
                )

        # Modificadores planos que nao dependem de arma
        for flat in re.finditer(r"CurrentScore\.Damage\s*\+=\s*(\d+)", body):
            rows.append(
                {
                    "gate_bit": bit,
                    "gate": name,
                    "weapon_unique": None,
                    "weapon": "(qualquer)",
                    "kind": "flat_damage",
                    "flat_damage": int(flat.group(1)),
                }
            )

    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    """Mantem a primeira ocorrencia de (kind, weapon, coefs) e lista os gates."""
    merged: dict[tuple, dict] = {}
    for row in rows:
        key = (
            row["kind"],
            row["weapon_unique"],
            row.get("dex_coefficient"),
            row.get("str_coefficient"),
            row.get("int_coefficient"),
            row.get("flat_damage"),
        )
        if key in merged:
            merged[key]["gates"].append({"bit": row["gate_bit"], "name": row["gate"]})
        else:
            entry = dict(row)
            entry.pop("gate_bit")
            entry.pop("gate")
            entry["gates"] = [{"bit": row["gate_bit"], "name": row["gate"]}]
            merged[key] = entry
    return list(merged.values())


def main() -> None:
    text = SOURCE.read_text(encoding="latin-1")
    payload = {
        "_source": "reference/w2pp-OpenWYD/Source/Code/Basedef.cpp (bloco // Balanceamento)",
        "_note": (
            "Coeficientes aplicados a CurrentScore.Damage ou a variavel `magic` em "
            "BASE_GetCurrentScore. Cada gate e uma skill aprendida (bit em LearnedSkill); "
            "a tabela se repete por gate, por isso as linhas estao deduplicadas."
        ),
        "classes": {},
    }
    for class_id, class_name in CLASSES.items():
        block = find_class_block(text, class_id)
        rows = dedupe(parse_gates(block)) if block else []
        payload["classes"][class_name] = rows

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for class_name, rows in payload["classes"].items():
        physical = [r for r in rows if r["kind"] == "physical"]
        magic = [r for r in rows if r["kind"] == "magic"]
        print(f"{class_name}: {len(physical)} variantes fisicas, {len(magic)} magicas, {len(rows)} linhas")


if __name__ == "__main__":
    main()
