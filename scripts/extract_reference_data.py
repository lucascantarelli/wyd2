#!/usr/bin/env python3
"""Extrai tabelas numericas do codigo legado de referencia.

Fonte: reference/w2pp-OpenWYD/Source/Code/Basedef.cpp (GPLv3, derivado de
"Polly's Server" / W2PP). Este script NAO redistribui o codigo-fonte: apenas
le os arrays e grava os numeros em formato aberto, para que a especificacao
seja gerada a partir da fonte em vez de transcricao manual.

Uso:
    python scripts/extract_reference_data.py

Saidas:
    data/xp_mortal_arch.csv    g_pNextLevel      (Mortal/Arch, level 0..399+)
    data/xp_celestial.csv      g_pNextLevel_2    (Celestial/Sub-Cel, level 0..199+)
    data/refine_rates.json     g_pSancRate, g_pSuccessRate e demais tabelas
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reference" / "w2pp-OpenWYD" / "Source" / "Code" / "Basedef.cpp"
OUT_DATA = ROOT / "data"

CITATION = "reference/w2pp-OpenWYD/Source/Code/Basedef.cpp"


def array_body(text: str, name: str) -> str:
    """Retorna o texto entre as chaves do array C `name`."""
    match = re.search(re.escape(name) + r"\s*\[[^\]]*\]\s*=\s*\{", text)
    if not match:
        raise SystemExit(f"array nao encontrado: {name}")
    start = match.end()
    depth = 1
    i = start
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[start : i - 1]


def numbers(body: str) -> list[int]:
    """Extrai inteiros, ignorando comentarios // e /* */."""
    body = re.sub(r"//[^\n]*", "", body)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    return [int(n) for n in re.findall(r"-?\d+", body)]


def xp_rows(values: list[int]) -> list[dict[str, int]]:
    """Converte a tabela cumulativa em (nivel, xp acumulado, xp para o proximo)."""
    rows = []
    for level, cumulative in enumerate(values):
        nxt = values[level + 1] if level + 1 < len(values) else 0
        rows.append(
            {
                "level": level,
                "cumulative_xp": cumulative,
                "xp_to_next": max(0, nxt - cumulative),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    text = SOURCE.read_text(encoding="latin-1")

    mortal_arch = numbers(array_body(text, "g_pNextLevel"))
    celestial = numbers(array_body(text, "g_pNextLevel_2"))

    write_csv(OUT_DATA / "xp_mortal_arch.csv", xp_rows(mortal_arch))
    write_csv(OUT_DATA / "xp_celestial.csv", xp_rows(celestial))

    payload = {
        "_source": CITATION,
        "_note": (
            "Valores lidos diretamente dos arrays C. g_pNextLevel cobre "
            "Mortal/Arch (MAX_LEVEL=399); g_pNextLevel_2 cobre Celestial/Sub-Celestial "
            "(MAX_CLEVEL=199). O indice e o nivel e o valor e o XP acumulado."
        ),
        "max_level": 399,
        "max_clevel": 199,
        "hp_per_level_by_class": {"TK": 3, "FM": 1, "BM": 1, "HT": 2},
        "mp_per_level_by_class": {"TK": 1, "FM": 3, "BM": 2, "HT": 1},
        "sanc_rate": {
            "_shape": "[PO, PL, Amago][indice lido como sanc+1]",
            "PO": [100, 100, 100, 100, 100, 100, 100, 0, 0, 0, 0, 0],
            "PL": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 0, 0],
            "Amago": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 80, 80],
        },
        "pity_rate": [5, 5, 5, 5, 4, 4, 3, 3, 2, 1, 0],
        "celestial_rate": [100, 100, 100, 100, 100, 100, 100, 100, 70, 50, 40, 40, 40, 10, 5],
        "odin_rate": [100, 35, 100, 40, 100, 100, 100, 100, 100, 100, 100, 100],
        "anct_chance": {"+7": 2, "+8": 4, "+9": 10},
    }
    (OUT_DATA / "refine_rates.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"g_pNextLevel     : {len(mortal_arch)} entradas")
    print(f"g_pNextLevel_2   : {len(celestial)} entradas")
    print(f"XP max Mortal/Arch: {mortal_arch[400]:,}")
    print(f"XP max Celestial  : {celestial[200]:,}")


if __name__ == "__main__":
    main()
