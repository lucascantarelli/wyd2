"""Catalogo do cliente WYD Global -> schema `catalog`.

    python -m importer.catalog --client "reference/WYD Global"                # dry-run
    python -m importer.catalog --client "reference/WYD Global" --emit out/catalog
    python -m importer.catalog --client "reference/WYD Global" \
        --emit out/catalog --used-items out/items.csv --strict

Le `ItemList.bin` e `SkillData.bin` (decoder em `client_tables.py`), emite
`items.csv`, `item_effects.csv`, `skills.csv` e `load_catalog.sql` idempotente.

`--used-items` aponta para o `items.csv` do pacote de contas: o relatorio passa
a comparar o catalogo com os `item_index` que o gateway realmente serializa.
Sem esse arquivo a reconciliacao roda so no banco, pelas views de
`schema/002_catalog.sql`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import CATALOG_SCHEMA_VERSION, SCHEMA_VERSION, TOOL_NAME, __version__
from . import ids
from .client_tables import (
    ITEM_RECORD_SIZE,
    MAX_STATICEFFECT,
    SKILL_RECORD_SIZE,
    TRAILER_SIZE,
    ItemTable,
    SkillTable,
    parse_item_table,
    parse_skill_table,
)
from .emit import write_csv
from .errors import ClientTableError

ITEM_FILE = "ItemList.bin"
SKILL_FILE = "SkillData.bin"

# O gateway escreve item_index em um campo int16 (narrow_i16).
MAX_ITEM_INDEX = 32767
EFFECT_SENTINEL = 255

ITEM_COLUMNS = (
    "item_index",
    "name",
    "mesh",
    "texture",
    "visual_effect",
    "req_level",
    "req_str",
    "req_int",
    "req_dex",
    "req_con",
    "price",
    "position",
    "grade",
    "unique_id",
    "extra",
    "canonical_id",
    "source_file",
    "source_offset",
)

EFFECT_COLUMNS = ("item_index", "slot", "effect", "value")

SKILL_COLUMNS = (
    "slot",
    "skill_id",
    "skill_point",
    "target_type",
    "mana",
    "delay",
    "range",
    "instance_type",
    "instance_value",
    "tick_type",
    "tick_value",
    "affect_type",
    "affect_value",
    "affect_time",
    "instance_attribute",
    "tick_attribute",
    "tail_values",
    "flag",
    "source_offset",
)


@dataclass
class Catalog:
    """Conteudo pronto para emissao, com a procedencia preservada."""

    items: list[dict[str, Any]] = field(default_factory=list)
    effects: list[dict[str, Any]] = field(default_factory=list)
    skills: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    distinct_names: int = 0
    duplicate_names: int = 0
    skill_sha256: str = ""
    item_sha256: str = ""
    skill_trailer: int = 0
    item_trailer: int = 0
    skill_records: int = 0
    item_records: int = 0


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def item_rows(table: ItemTable) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Converte registros do cliente em linhas de `catalog.items`/`item_effects`.

    Slots sem nome sao descartados: sao reserva de array, nao itens. Efeitos
    com o sentinela (255,0) nao viram linha.
    """
    items: list[dict[str, Any]] = []
    effects: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for offset, record in enumerate(table.records):
        if record.is_empty:
            continue
        item_index = offset
        if item_index > MAX_ITEM_INDEX:
            warnings.append(
                {
                    "code": "item_index_acima_do_int16",
                    "detail": {"item_index": item_index, "name": record.name},
                }
            )

        items.append(
            {
                "item_index": item_index,
                "name": record.name,
                "mesh": record.mesh,
                "texture": record.texture,
                "visual_effect": record.visual_effect,
                "req_level": record.req_level,
                "req_str": record.req_str,
                "req_int": record.req_int,
                "req_dex": record.req_dex,
                "req_con": record.req_con,
                "price": record.price,
                "position": record.position,
                "grade": record.grade,
                "unique_id": record.unique,
                "extra": record.extra,
                "canonical_id": record.canonical_id,
                "source_file": ITEM_FILE,
                "source_offset": offset * ITEM_RECORD_SIZE + TRAILER_SIZE,
            }
        )
        for slot, (effect, value) in enumerate(record.effects[:MAX_STATICEFFECT]):
            if effect in (0, EFFECT_SENTINEL):
                continue
            effects.append(
                {"item_index": item_index, "slot": slot, "effect": effect, "value": value}
            )
    return items, effects, warnings


def skill_rows(table: SkillTable) -> list[dict[str, Any]]:
    """Uma linha por slot de `SkillData.bin` (inclusive slots nao usados)."""
    rows = []
    for slot, record in enumerate(table.records):
        rows.append(
            {
                "slot": slot,
                "skill_id": record.skill_id,
                "skill_point": record.skill_point,
                "target_type": record.target_type,
                "mana": record.mana,
                "delay": record.delay,
                "range": record.range,
                "instance_type": record.instance_type,
                "instance_value": record.instance_value,
                "tick_type": record.tick_type,
                "tick_value": record.tick_value,
                "affect_type": record.affect_type,
                "affect_value": record.affect_value,
                "affect_time": record.affect_time,
                "instance_attribute": "\\x" + record.instance_attribute.hex(),
                "tick_attribute": "\\x" + record.tick_attribute.hex(),
                "tail_values": record.tail_values,
                "flag": record.flag,
                "source_offset": slot * SKILL_RECORD_SIZE + TRAILER_SIZE,
            }
        )
    return rows


def build_catalog(client_dir: Path) -> Catalog:
    """Le os dois `.bin` do cliente e monta o catalogo em memoria."""
    item_path = client_dir / ITEM_FILE
    skill_path = client_dir / SKILL_FILE
    for path in (item_path, skill_path):
        if not path.is_file():
            raise ClientTableError(f"arquivo do cliente ausente: {path}")

    raw_item = item_path.read_bytes()
    raw_skill = skill_path.read_bytes()
    item_table = parse_item_table(raw_item)
    skill_table = parse_skill_table(raw_skill)

    items, effects, warnings = item_rows(item_table)
    names = [row["name"] for row in items]
    catalog = Catalog(
        items=items,
        effects=effects,
        skills=skill_rows(skill_table),
        warnings=warnings,
        distinct_names=len(set(names)),
        duplicate_names=len(names) - len(set(names)),
        item_sha256=sha256_bytes(raw_item),
        skill_sha256=sha256_bytes(raw_skill),
        item_trailer=item_table.trailer,
        skill_trailer=skill_table.trailer,
        item_records=len(item_table.records),
        skill_records=len(skill_table.records),
    )
    return catalog


def read_used_items(path: Path) -> list[int]:
    """Le a coluna `item_index` de um `items.csv` do pacote de contas."""
    indexes: list[int] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "item_index" not in reader.fieldnames:
            raise ClientTableError(f"{path}: coluna item_index ausente")
        for row in reader:
            raw = (row.get("item_index") or "").strip()
            if raw:
                indexes.append(int(raw))
    return indexes


def reconcile(catalog_indexes: Iterable[int], used_indexes: Iterable[int]) -> dict[str, Any]:
    """Compara o catalogo com os indices que o gateway vai serializar."""
    catalog = set(catalog_indexes)
    used = sorted(set(used_indexes))
    missing = [index for index in used if index not in catalog]
    out_of_range = [index for index in used if index > MAX_ITEM_INDEX]
    return {
        "checked": True,
        "catalog_indexes": len(catalog),
        "used_indexes": len(used),
        "matched": len(used) - len(missing),
        "missing_total": len(missing),
        "missing_sample": missing[:50],
        "out_of_range_total": len(out_of_range),
        "out_of_range_sample": out_of_range[:50],
        "ok": not missing and not out_of_range,
    }


def catalog_run_id(skill_sha256: str, item_sha256: str) -> uuid.UUID:
    return uuid.uuid5(ids.NAMESPACE, f"catalog:{skill_sha256}:{item_sha256}")


def _upsert_assigns(columns: Iterable[str], exclude: Iterable[str] = ()) -> str:
    skip = set(exclude)
    return ", ".join(f"{column} = EXCLUDED.{column}" for column in columns if column not in skip)


def sql_literal(text: str) -> str:
    """Escapa um valor textual para uso dentro de um literal SQL."""
    return text.replace("'", "''")


def load_catalog_sql(catalog: Catalog, report: dict[str, Any]) -> str:
    """SQL idempotente: staging + upsert + remocao do que sumiu do cliente."""
    run_id = report["run_id"]
    item_columns = ", ".join(ITEM_COLUMNS)
    effect_columns = ", ".join(EFFECT_COLUMNS)
    skill_columns = ", ".join(SKILL_COLUMNS)
    item_updates = _upsert_assigns([c for c in ITEM_COLUMNS if c != "item_index"], exclude=("source_file",))
    skill_updates = _upsert_assigns([c for c in SKILL_COLUMNS if c != "slot"])
    lines = [
        "-- Gerado por wyd-importer. Nao editar a mao.",
        "-- Executar a partir do diretorio deste arquivo:",
        "--     psql -d wyd -f load_catalog.sql",
        "--",
        "-- Idempotente e full-refresh: upsert do que veio + remocao do que sumiu.",
        "\\set ON_ERROR_STOP on",
        "BEGIN;",
        "SET LOCAL search_path TO catalog, public;",
        "",
        "CREATE TEMP TABLE stage_items (LIKE catalog.items INCLUDING DEFAULTS) ON COMMIT DROP;",
        f"\\copy stage_items ({item_columns}) FROM 'items.csv' "
        "WITH (FORMAT csv, HEADER true, NULL '')",
        f"INSERT INTO catalog.items ({item_columns}) SELECT {item_columns} FROM stage_items "
        f"ON CONFLICT (item_index) DO UPDATE SET {item_updates}, "
        "updated_at = now();",
        "DELETE FROM catalog.items WHERE item_index NOT IN (SELECT item_index FROM stage_items);",
        "",
        "CREATE TEMP TABLE stage_item_effects (LIKE catalog.item_effects INCLUDING DEFAULTS) "
        "ON COMMIT DROP;",
        f"\\copy stage_item_effects ({effect_columns}) FROM 'item_effects.csv' "
        "WITH (FORMAT csv, HEADER true, NULL '')",
        # Sem DELETE por item nao ha como distinguir slot que deixou de existir
        # de slot que continua igual. O full-refresh resolve os dois casos.
        "DELETE FROM catalog.item_effects "
        "WHERE item_index IN (SELECT item_index FROM stage_items);",
        f"INSERT INTO catalog.item_effects ({effect_columns}) "
        f"SELECT {effect_columns} FROM stage_item_effects "
        "ON CONFLICT (item_index, slot) DO UPDATE SET "
        "effect = EXCLUDED.effect, value = EXCLUDED.value;",
        "",
        "CREATE TEMP TABLE stage_skills (LIKE catalog.skills INCLUDING DEFAULTS) ON COMMIT DROP;",
        f"\\copy stage_skills ({skill_columns}) FROM 'skills.csv' "
        "WITH (FORMAT csv, HEADER true, NULL '')",
        # Duas skills que trocam de slot no mesmo arquivo colidem no indice
        # unico parcial (skill_id) no meio do upsert, dependendo da ordem das
        # linhas. Zerar os slots que serao regravados tira a colisao; 0 nao
        # entra no indice e o INSERT logo abaixo repoe os ids do arquivo.
        "UPDATE catalog.skills SET skill_id = 0 "
        "WHERE slot IN (SELECT slot FROM stage_skills) AND skill_id > 0;",
        f"INSERT INTO catalog.skills ({skill_columns}) SELECT {skill_columns} FROM stage_skills "
        f"ON CONFLICT (slot) DO UPDATE SET {skill_updates}, updated_at = now();",
        "DELETE FROM catalog.skills WHERE slot NOT IN (SELECT slot FROM stage_skills);",
        "",
        "INSERT INTO catalog.load_runs "
        "(id, client_dir, skill_sha256, item_sha256, skill_records, item_records, "
        " skill_trailer, item_trailer, tool_version) VALUES (",
        f"    '{run_id}',",
        f"    '{sql_literal(report['client_dir'])}',",
        f"    '{catalog.skill_sha256}',",
        f"    '{catalog.item_sha256}',",
        f"    {catalog.skill_records}, {catalog.item_records},",
        f"    {catalog.skill_trailer}, {catalog.item_trailer},",
        f"    '{TOOL_NAME} {__version__}'",
        ") ON CONFLICT (id) DO UPDATE SET "
        "loaded_at = now(), tool_version = EXCLUDED.tool_version;",
        "COMMIT;",
        "",
    ]
    return "\n".join(lines)


def verify_package(
    outdir: Path,
    catalog: Catalog,
    report: dict[str, Any],
    *,
    ok: bool,
) -> list[dict[str, Any]]:
    """Confere o pacote gerado; falha alto em vez de gerar carga enganosa."""
    checks: list[dict[str, Any]] = []

    def add(code: str, passed: bool, detail: Any = None) -> None:
        checks.append({"code": code, "status": "ok" if passed else "fail", "detail": detail})

    for name in ("items.csv", "item_effects.csv", "skills.csv"):
        add(f"catalog_{name}_present", (outdir / name).is_file())
    add("catalog_items_non_empty", len(catalog.items) > 0, {"items": len(catalog.items)})
    add("catalog_skills_non_empty", len(catalog.skills) > 0, {"skills": len(catalog.skills)})
    add(
        "catalog_no_sentinel_effect",
        all(row["effect"] != EFFECT_SENTINEL for row in catalog.effects),
    )
    add(
        "catalog_effects_within_slots",
        all(0 <= row["slot"] < MAX_STATICEFFECT for row in catalog.effects),
    )
    add(
        "catalog_skill_ids_unique",
        len({row["skill_id"] for row in catalog.skills if row["skill_id"] > 0})
        == len([row for row in catalog.skills if row["skill_id"] > 0]),
    )

    reconciliation = report.get("reconciliation", {})
    if reconciliation.get("checked"):
        add(
            "catalog_reconciliation",
            bool(reconciliation.get("ok")),
            {
                "missing_total": reconciliation.get("missing_total"),
                "out_of_range_total": reconciliation.get("out_of_range_total"),
            },
        )

    if ok:
        sql_path = outdir / "load_catalog.sql"
        sql = sql_path.read_text(encoding="utf-8") if sql_path.is_file() else ""
        add(
            "catalog_sql_idempotent",
            "ON CONFLICT" in sql and "BEGIN;" in sql and "COMMIT;" in sql,
        )
        add("catalog_sql_full_refresh", "NOT IN (SELECT" in sql)
        add("catalog_sql_has_schema", "catalog.items" in sql and "catalog.skills" in sql)
    return checks


def write_package(outdir: Path, catalog: Catalog, report: dict[str, Any], *, ok: bool) -> list[dict[str, Any]]:
    outdir.mkdir(parents=True, exist_ok=True)

    write_csv(outdir / "items.csv", ITEM_COLUMNS, catalog.items)
    write_csv(outdir / "item_effects.csv", EFFECT_COLUMNS, catalog.effects)
    write_csv(outdir / "skills.csv", SKILL_COLUMNS, catalog.skills)

    stale = outdir / "load_catalog.sql"
    blocked = outdir / "LOAD_BLOCKED.txt"
    if ok:
        stale.write_text(load_catalog_sql(catalog, report), encoding="utf-8")
        blocked.unlink(missing_ok=True)
    else:
        stale.unlink(missing_ok=True)
        blocked.write_text(
            "Catalogo NAO carregavel: a reconciliacao falhou.\n"
            "Veja report.json (catalog_reconciliation) ou rode com --strict.\n",
            encoding="utf-8",
        )

    checks = verify_package(outdir, catalog, report, ok=ok)
    if ok and any(check["status"] == "fail" for check in checks):
        stale.unlink(missing_ok=True)
        blocked.write_text(
            "Catalogo NAO carregavel: a verificacao do pacote falhou.\n"
            "Veja report.json (checks com status=fail).\n",
            encoding="utf-8",
        )
    return checks


def build_report(
    catalog: Catalog,
    *,
    client_dir: Path,
    reconciliation: dict[str, Any],
    ok: bool,
) -> dict[str, Any]:
    return {
        "tool": f"{TOOL_NAME} {__version__}",
        "schema_version": CATALOG_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "client_dir": str(client_dir),
        "run_id": str(catalog_run_id(catalog.skill_sha256, catalog.item_sha256)),
        "skill": {
            "file": SKILL_FILE,
            "sha256": catalog.skill_sha256,
            "records": catalog.skill_records,
            "trailer": catalog.skill_trailer,
            "used": len([row for row in catalog.skills if row["skill_id"] > 0]),
        },
        "item": {
            "file": ITEM_FILE,
            "sha256": catalog.item_sha256,
            "records": catalog.item_records,
            "named": len(catalog.items),
            "distinct_names": catalog.distinct_names,
            "duplicate_names": catalog.duplicate_names,
            "effects": len(catalog.effects),
            "trailer": catalog.item_trailer,
            "max_index": max((row["item_index"] for row in catalog.items), default=0),
        },
        "reconciliation": reconciliation,
        "warnings": catalog.warnings,
        "ok": ok,
    }


def print_summary(report: dict[str, Any], report_path: Path | None) -> None:
    item = report["item"]
    skill = report["skill"]
    print(f"{report['tool']}  (schema {report['schema_version']})")
    print(f"cliente    : {report['client_dir']}")
    print(f"itens      : {item['named']} nomeados em {item['records']} slots, {item['effects']} efeitos")
    print(f"skills     : {skill['used']} usados em {skill['records']} slots")
    print(f"trailers   : item={item['trailer']} skill={skill['trailer']}")
    reconciliation = report.get("reconciliation", {})
    if reconciliation.get("checked"):
        print(
            "reconciliacao: {matched}/{used} indices usados no catalogo, "
            "{missing} ausente(s), {oor} fora do int16".format(
                matched=reconciliation["matched"],
                used=reconciliation["used_indexes"],
                missing=reconciliation["missing_total"],
                oor=reconciliation["out_of_range_total"],
            )
        )
    else:
        print("reconciliacao: nao executada (sem --used-items)")
    print(f"avisos     : {len(report['warnings'])}")
    print(f"status     : {'OK' if report['ok'] else 'FALHOU'}")
    if report_path is not None:
        print(f"relatorio  : {report_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m importer.catalog",
        description="Importa o catalogo de itens e skills do cliente WYD Global para o schema catalog.",
    )
    parser.add_argument("--client", required=True, help="diretorio do cliente (com ItemList.bin e SkillData.bin)")
    parser.add_argument("--emit", metavar="DIR", help="grava o pacote do catalogo em DIR; sem isso, dry-run")
    parser.add_argument("--report", metavar="PATH", help="caminho do report.json")
    parser.add_argument(
        "--used-items",
        metavar="CSV",
        help="items.csv do pacote de contas, para reconciliar item_index usado x catalogo",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="bloqueia load_catalog.sql quando a reconciliacao acusa item ausente ou fora do int16",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{TOOL_NAME} {__version__} (schema {SCHEMA_VERSION}+{CATALOG_SCHEMA_VERSION})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    client_dir = Path(args.client)
    if not client_dir.is_dir():
        print(f"erro: diretorio do cliente nao encontrado: {client_dir}", file=sys.stderr)
        return 2

    try:
        catalog = build_catalog(client_dir)
    except ClientTableError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    reconciliation: dict[str, Any] = {"checked": False}
    if args.used_items:
        used_path = Path(args.used_items)
        if not used_path.is_file():
            print(f"erro: items.csv nao encontrado: {used_path}", file=sys.stderr)
            return 2
        try:
            used = read_used_items(used_path)
        except ClientTableError as exc:
            print(f"erro: {exc}", file=sys.stderr)
            return 1
        reconciliation = reconcile((row["item_index"] for row in catalog.items), used)

    ok = not (args.strict and not reconciliation.get("ok", True))
    report = build_report(catalog, client_dir=client_dir, reconciliation=reconciliation, ok=ok)

    if args.emit:
        outdir = Path(args.emit)
        report["checks"] = write_package(outdir, catalog, report, ok=ok)
        if any(check["status"] == "fail" for check in report["checks"]):
            report["ok"] = False
            ok = False
        report_path = Path(args.report) if args.report else outdir / "report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        report_path = Path(args.report) if args.report else None
        if report_path is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

    print_summary(report, report_path)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
