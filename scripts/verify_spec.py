#!/usr/bin/env python3
"""Verifica a especificacao contra a fonte de referencia.

Checks:
1. Links relativos em toda a documentacao (README.md, docs/, roadmap/, skills/,
   .agents/skills/)
   apontam para arquivos existentes.
2. data/xp_*.csv batem com os arrays C (reextracao em memoria).
3. spec/opcodes.yaml contem os valores de fio canonicos.
4. Contagens minimas dos artefatos.

Uso: python scripts/verify_spec.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import extract_reference_data as ref  # noqa: E402

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def check_xp() -> None:
    text = ref.SOURCE.read_text(encoding="latin-1")
    mortal = ref.numbers(ref.array_body(text, "g_pNextLevel"))
    celestial = ref.numbers(ref.array_body(text, "g_pNextLevel_2"))

    for name, values in (("xp_mortal_arch.csv", mortal), ("xp_celestial.csv", celestial)):
        rows = read_csv(ROOT / "data" / name)
        check(len(rows) == len(values), f"{name}: {len(rows)} linhas, esperado {len(values)}")
        for level, cumulative in ((0, values[0]), (1, values[1]), (min(399, len(values) - 1), values[min(399, len(values) - 1)])):
            if level < len(rows):
                got = int(rows[level]["cumulative_xp"])
                check(got == cumulative, f"{name} nivel {level}: {got} != {cumulative}")

    # Marcos citados na documentacao
    check(mortal[1] == 500, f"XP nivel 1 = {mortal[1]}, esperado 500")
    check(mortal[399] == 4_000_000_000, f"XP nivel 399 = {mortal[399]}")
    check(celestial[199] == 4_000_000_000, f"XP celestial 199 = {celestial[199]}")


def check_opcodes() -> None:
    text = (ROOT / "spec" / "opcodes.yaml").read_text(encoding="utf-8")
    expected = {
        "_MSG_AccountLogin": 525,
        "_MSG_CharacterLogin": 531,
        "_MSG_MessageChat": 819,
        "_MSG_MessageWhisper": 820,
        "_MSG_Attack": 871,
        "_MSG_Action": 876,
        "_MSG_UseItem": 883,
        "_MSG_CombineItem": 934,
    }
    for name, value in expected.items():
        pattern = rf"constant: {re.escape(name)}\n\s+value: (\d+)"
        match = re.search(pattern, text)
        check(match is not None, f"opcode ausente: {name}")
        if match:
            check(int(match.group(1)) == value, f"{name} = {match.group(1)}, esperado {value}")


DOC_DIRS = ("docs", "roadmap", "skills", ".agents")


def markdown_files() -> list[Path]:
    """Toda documentacao versionada: raiz, docs/, roadmap/, skills/ e .agents/.

    ``reference/`` e ``out/`` ficam de fora: o primeiro e a fonte de
    referencia (gitignored) e o segundo e pacote de importacao.
    """
    files = [ROOT / "README.md"]
    for directory in DOC_DIRS:
        files.extend(sorted((ROOT / directory).rglob("*.md")))
    return files


def check_links() -> None:
    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for md in markdown_files():
        for target in link_re.findall(md.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = (md.parent / target.split("#")[0]).resolve()
            check(path.exists(), f"{md.relative_to(ROOT)}: link quebrado -> {target}")


def check_artifacts() -> None:
    check(len(read_csv(ROOT / "data" / "xp_mortal_arch.csv")) == 597, "xp_mortal_arch: esperado 597 linhas")
    check(len(read_csv(ROOT / "data" / "xp_celestial.csv")) == 401, "xp_celestial: esperado 401 linhas")

    import json

    rates = json.loads((ROOT / "data" / "refine_rates.json").read_text(encoding="utf-8"))
    check(rates["pity_rate"] == [5, 5, 5, 5, 4, 4, 3, 3, 2, 1, 0], "pity_rate divergente")

    balance = json.loads(
        (ROOT / "data" / "class_weapon_coefficients.json").read_text(encoding="utf-8")
    )
    for cls in ("TransKnight", "Foema", "BeastMaster", "Huntress"):
        physical = [r for r in balance["classes"][cls] if r["kind"] == "physical"]
        check(len(physical) == 7, f"{cls}: esperado 7 variantes fisicas, obtido {len(physical)}")


def check_source_constants() -> None:
    header = (ref.SOURCE.parent / "Basedef.h").read_text(encoding="latin-1")
    for marker, value in (
        ("APP_VERSION", "7640"),
        ("MAX_USER", "1000"),
        ("MAX_LEVEL", "399"),
        ("MAX_CLEVEL", "199"),
        ("MAX_DAMAGE", "1000000000"),
        ("MAX_SKILL", "24"),
        ("MAX_TARGET", "13"),
    ):
        match = re.search(rf"#define\s+{marker}\s+(\d+)", header)
        check(match is not None and match.group(1) == value, f"constante {marker} divergente")

    socks = (ref.SOURCE.parent / "CPSock.h").read_text(encoding="latin-1")
    check("0x1F11F311" in socks, "INITCODE ausente em CPSock.h")


def main() -> None:
    check_xp()
    check_opcodes()
    check_links()
    check_artifacts()
    check_source_constants()

    if FAILURES:
        print(f"FALHOU ({len(FAILURES)}):")
        for failure in FAILURES:
            print("  -", failure)
        raise SystemExit(1)

    print("OK: links, curvas de XP, opcodes, artefatos e constantes conferem.")


if __name__ == "__main__":
    main()
