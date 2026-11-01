r"""Emissao do pacote de importacao.

Saidas em `out/`:
  accounts.csv, characters.csv, items.csv, character_affects.csv,
  item_ledger.csv, import_runs.csv, import_issues.csv
  records.jsonl     -- auditoria sem hash de senha
  load.sql          -- carga idempotente via psql (\copy + ON CONFLICT)
  report.json       -- gravado pelo CLI

O pacote inteiro e sensivel: contem hashes de senha. `out/` e gitignored.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from . import SCHEMA_VERSION, TOOL_NAME, __version__
from . import ids
from .model import AccountFile, Character, Item, MigratedAccount


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[str, ...]
    conflict: str | None = None
    conflict_target: str | None = None
    update: tuple[str, ...] = ()
    update_overrides: dict[str, str] = field(default_factory=dict)


ACCOUNTS = TableSpec(
    name="accounts",
    columns=(
        "id", "login", "password_hash", "password_algo", "numeric_token_hash",
        "email", "blocked", "must_reset_password", "donate", "cargo_gold",
        "legacy_key", "legacy_source",
    ),
    conflict="id",
    update=("login", "email", "blocked", "donate", "cargo_gold", "legacy_key", "legacy_source"),
    update_overrides={"email": "COALESCE(EXCLUDED.email, accounts.email)"},
)

CHARACTERS = TableSpec(
    name="characters",
    columns=(
        "id", "account_id", "slot", "name", "class", "class_master", "clan", "citizen",
        "guild_legacy_id", "guild_level", "level", "exp", "gold", "spx", "spy", "fame",
        "soul", "arch_level", "celestial_level", "sub_celestial_level", "celestial_reset",
        "arch_cristal", "mortal_level",
        "base_ac", "base_damage", "base_max_hp", "base_max_mp", "base_hp", "base_mp",
        "base_str", "base_int", "base_dex", "base_con",
        "current_ac", "current_damage", "current_max_hp", "current_max_mp",
        "current_hp", "current_mp", "current_str", "current_int", "current_dex", "current_con",
        "current_special",
        "learned_skill", "magic", "score_bonus", "special_bonus", "skill_bonus",
        "critical", "save_mana", "skill_bar", "short_skills", "regen_hp", "regen_mp",
        "resist", "merchant", "quest", "rsv", "direction", "chaos_rate", "attack_run",
        "raw_base_score", "raw_current_score", "raw_mobextra", "legacy_key", "legacy_source",
    ),
    conflict="id",
    update=(
        "account_id", "slot", "name", "class", "class_master", "clan", "citizen",
        "guild_legacy_id", "guild_level", "level", "exp", "gold", "spx", "spy", "fame",
        "soul", "arch_level", "celestial_level", "sub_celestial_level", "celestial_reset",
        "arch_cristal", "mortal_level",
        "base_ac", "base_damage", "base_max_hp", "base_max_mp", "base_hp", "base_mp",
        "base_str", "base_int", "base_dex", "base_con",
        "current_ac", "current_damage", "current_max_hp", "current_max_mp",
        "current_hp", "current_mp", "current_str", "current_int", "current_dex", "current_con",
        "current_special",
        "learned_skill", "magic", "score_bonus", "special_bonus", "skill_bonus",
        "critical", "save_mana", "skill_bar", "short_skills", "regen_hp", "regen_mp",
        "resist", "merchant", "quest", "rsv", "direction", "chaos_rate", "attack_run",
        "raw_base_score", "raw_current_score", "raw_mobextra", "legacy_key", "legacy_source",
    ),
)

AFFECTS = TableSpec(
    name="character_affects",
    columns=("character_id", "slot", "type", "value", "level", "time_value"),
    conflict_target="(character_id, slot)",
    update=("type", "value", "level", "time_value"),
)

ITEMS = TableSpec(
    name="items",
    columns=(
        "id", "owner_account_id", "owner_character_id", "container", "slot",
        "item_index", "refine", "gem",
        "effect_0_type", "effect_0_value", "effect_1_type", "effect_1_value",
        "effect_2_type", "effect_2_value", "legacy_key", "legacy_source",
    ),
    conflict="id",
    update=(
        "owner_account_id", "owner_character_id", "container", "slot", "item_index",
        "refine", "gem", "effect_0_type", "effect_0_value", "effect_1_type",
        "effect_1_value", "effect_2_type", "effect_2_value", "legacy_key", "legacy_source",
    ),
)

LEDGER = TableSpec(
    name="item_ledger",
    columns=(
        "item_id", "action", "from_character_id", "to_character_id",
        "from_container", "to_container", "from_slot", "to_slot",
        "actor", "correlation_id", "detail",
    ),
    conflict_target="(item_id, action, correlation_id)",
)

RUNS = TableSpec(
    name="import_runs",
    columns=(
        "id", "started_at", "finished_at", "mode", "status", "tool_version",
        "source_path", "schema_version", "manifest_sha256", "totals", "report",
    ),
    conflict="id",
)

ISSUES = TableSpec(
    name="import_issues",
    columns=("run_id", "severity", "code", "account_login", "legacy_path", "detail"),
    conflict_target="(run_id, code, account_login, legacy_path)",
    update=("severity", "detail"),
)

TABLES = (RUNS, ACCOUNTS, CHARACTERS, AFFECTS, ITEMS, LEDGER, ISSUES)


# ---------------------------------------------------------------------------
# Formatacao CSV / CSV COPY
# ---------------------------------------------------------------------------

def format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, bytes):
        return "\\x" + value.hex()
    if isinstance(value, (list, tuple)):
        return "{" + ",".join(str(int(v)) for v in value) + "}"
    if isinstance(value, dict):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return str(value)


def write_csv(path: Path, columns: tuple[str, ...], rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([format_value(row.get(column)) for column in columns])
            count += 1
    return count


# ---------------------------------------------------------------------------
# Linhas por tabela
# ---------------------------------------------------------------------------

def account_row(account: MigratedAccount) -> dict[str, Any]:
    return {
        "id": account.id,
        "login": account.login,
        "password_hash": account.password_hash,
        "password_algo": account.password_algo,
        "numeric_token_hash": account.numeric_token_hash,
        "email": account.email,
        "blocked": account.blocked,
        "must_reset_password": account.must_reset_password,
        "donate": account.donate,
        "cargo_gold": account.cargo_gold,
        "legacy_key": account.legacy_key,
        "legacy_source": account.legacy_source,
    }


def character_row(account: MigratedAccount, character: Character) -> dict[str, Any]:
    base = character.base
    current = character.current
    extra = character.extra
    return {
        "id": str(ids.character_id(account.login, character.slot)),
        "account_id": account.id,
        "slot": character.slot,
        "name": character.name,
        "class": character.char_class,
        "class_master": extra.class_master,
        "clan": character.clan,
        "citizen": extra.citizen,
        "guild_legacy_id": character.guild,
        "guild_level": character.guild_level,
        "level": base.level,
        "exp": character.exp,
        "gold": character.coin,
        "spx": character.spx,
        "spy": character.spy,
        "fame": extra.fame,
        "soul": extra.soul,
        "arch_level": extra.arch_level,
        "celestial_level": extra.celestial_level,
        "sub_celestial_level": extra.sub_celestial_level,
        "celestial_reset": extra.celestial_reset,
        "arch_cristal": extra.arch_cristal,
        "mortal_level": extra.mortal_level,
        "base_ac": base.ac,
        "base_damage": base.damage,
        "base_max_hp": base.max_hp,
        "base_max_mp": base.max_mp,
        "base_hp": base.hp,
        "base_mp": base.mp,
        "base_str": base.strength,
        "base_int": base.intelligence,
        "base_dex": base.dexterity,
        "base_con": base.constitution,
        "current_ac": current.ac,
        "current_damage": current.damage,
        "current_max_hp": current.max_hp,
        "current_max_mp": current.max_mp,
        "current_hp": current.hp,
        "current_mp": current.mp,
        "current_str": current.strength,
        "current_int": current.intelligence,
        "current_dex": current.dexterity,
        "current_con": current.constitution,
        "current_special": list(current.special),
        "learned_skill": character.learned_skill,
        "magic": character.magic,
        "score_bonus": character.score_bonus,
        "special_bonus": character.special_bonus,
        "skill_bonus": character.skill_bonus,
        "critical": character.critical,
        "save_mana": character.save_mana,
        "skill_bar": list(character.skill_bar),
        "short_skills": list(character.short_skills),
        "regen_hp": character.regen_hp,
        "regen_mp": character.regen_mp,
        "resist": list(character.resist),
        "merchant": character.merchant,
        "quest": character.quest,
        "rsv": character.rsv,
        "direction": current.direction,
        "chaos_rate": current.chaos_rate,
        "attack_run": current.attack_run,
        "raw_base_score": base.to_dict(),
        "raw_current_score": current.to_dict(),
        "raw_mobextra": extra.raw,
        "legacy_key": ids.character_legacy_key(account.login, character.slot),
        "legacy_source": account.legacy_source,
    }


def affect_rows(account: MigratedAccount) -> Iterator[dict[str, Any]]:
    for character in account.source.characters:
        character_id = str(ids.character_id(account.login, character.slot))
        for affect in character.affects:
            yield {
                "character_id": character_id,
                "slot": affect.slot,
                "type": affect.type,
                "value": affect.value,
                "level": affect.level,
                "time_value": affect.time_value,
            }


def _iter_items(account: MigratedAccount) -> Iterator[tuple[Character | None, Item]]:
    for character in account.source.characters:
        for item in character.equip:
            yield character, item
        for item in character.carry:
            yield character, item
    for item in account.source.cargo:
        yield None, item


def item_row(account: MigratedAccount, character: Character | None, item: Item) -> dict[str, Any]:
    char_slot = character.slot if character else None
    effects = list(item.effects) + [None] * (3 - len(item.effects))
    return {
        "id": str(ids.item_id(account.login, char_slot, item.container, item.slot)),
        "owner_account_id": account.id if character is None else None,
        "owner_character_id": str(ids.character_id(account.login, char_slot)) if character else None,
        "container": item.container,
        "slot": item.slot,
        "item_index": item.item_index,
        "refine": item.refine,
        "gem": item.gem,
        "effect_0_type": effects[0].type if effects[0] else 0,
        "effect_0_value": effects[0].value if effects[0] else 0,
        "effect_1_type": effects[1].type if effects[1] else 0,
        "effect_1_value": effects[1].value if effects[1] else 0,
        "effect_2_type": effects[2].type if effects[2] else 0,
        "effect_2_value": effects[2].value if effects[2] else 0,
        "legacy_key": ids.item_legacy_key(account.login, char_slot, item.container, item.slot),
        "legacy_source": account.legacy_source,
    }


def ledger_rows(account: MigratedAccount, run_id: str) -> Iterator[dict[str, Any]]:
    for character, item in _iter_items(account):
        char_slot = character.slot if character else None
        yield {
            "item_id": str(ids.item_id(account.login, char_slot, item.container, item.slot)),
            "action": "import",
            "from_character_id": None,
            "to_character_id": str(ids.character_id(account.login, char_slot)) if character else None,
            "from_container": None,
            "to_container": item.container,
            "from_slot": None,
            "to_slot": item.slot,
            "actor": "importer",
            "correlation_id": run_id,
            "detail": {
                "source": account.legacy_source,
                "legacy_key": ids.item_legacy_key(account.login, char_slot, item.container, item.slot),
            },
        }


def run_row(report: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "issues_by_severity": report.get("issues_by_severity", {}),
        "versions": report.get("versions", {}),
        "characters_by_tier": report.get("characters_by_tier", {}),
    }
    return {
        "id": report["run_id"],
        "started_at": report["started_at"],
        "finished_at": report["finished_at"],
        "mode": "commit",
        "status": "running",
        "tool_version": __version__,
        "source_path": report["source"],
        "schema_version": SCHEMA_VERSION,
        "manifest_sha256": report["manifest_sha256"],
        "totals": report["totals"],
        "report": compact,
    }


def issue_row(report: dict[str, Any], issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": report["run_id"],
        "severity": issue["severity"],
        "code": issue["code"],
        "account_login": issue.get("account"),
        "legacy_path": issue.get("path"),
        "detail": issue.get("detail", {}),
    }


# ---------------------------------------------------------------------------
# JSONL de auditoria
# ---------------------------------------------------------------------------

def audit_records(account: MigratedAccount, report: dict[str, Any]) -> Iterator[dict[str, Any]]:
    source: AccountFile = account.source
    yield {
        "type": "account",
        "id": account.id,
        "login": account.login,
        "password_algo": account.password_algo,
        "blocked": account.blocked,
        "donate": account.donate,
        "cargo_gold": account.cargo_gold,
        "legacy_key": account.legacy_key,
        "source": {
            "path": source.path,
            "size": source.size,
            "sha256": source.sha256,
        },
    }
    for character in source.characters:
        yield {
            "type": "character",
            "id": str(ids.character_id(account.login, character.slot)),
            "account_id": account.id,
            "slot": character.slot,
            "name": character.name,
            "class": character.char_class,
            "class_master": character.extra.class_master,
            "level": character.base.level,
            "exp": character.exp,
            "gold": character.coin,
            "legacy_key": ids.character_legacy_key(account.login, character.slot),
        }
    for character, item in _iter_items(account):
        char_slot = character.slot if character else None
        payload = item.to_dict()
        payload.update(
            {
                "type": "item",
                "id": str(ids.item_id(account.login, char_slot, item.container, item.slot)),
                "account_id": account.id,
                "character_id": str(ids.character_id(account.login, char_slot)) if character else None,
                "legacy_key": ids.item_legacy_key(account.login, char_slot, item.container, item.slot),
            }
        )
        yield payload
    yield {
        "type": "import",
        "run_id": report["run_id"],
        "manifest_sha256": report["manifest_sha256"],
        "schema_version": SCHEMA_VERSION,
        "tool": f"{TOOL_NAME} {__version__}",
    }


# ---------------------------------------------------------------------------
# load.sql
# ---------------------------------------------------------------------------

def _conflict_clause(spec: TableSpec) -> str:
    if spec.conflict is None and spec.conflict_target is None:
        return "ON CONFLICT DO NOTHING"
    target = spec.conflict_target or f"({spec.conflict})"
    if not spec.update:
        return f"ON CONFLICT {target} DO NOTHING"
    assigns = []
    for column in spec.update:
        if column in spec.update_overrides:
            assigns.append(f"{column} = {spec.update_overrides[column]}")
        else:
            assigns.append(f"{column} = EXCLUDED.{column}")
    return f"ON CONFLICT {target} DO UPDATE SET " + ", ".join(assigns)


def load_sql(report: dict[str, Any]) -> str:
    run_id = report["run_id"]
    lines = [
        "-- Gerado por wyd-importer. Nao editar a mao.",
        "-- Executar a partir do diretorio deste arquivo:",
        "--     psql -d wyd -f load.sql",
        "--",
        "-- A carga e idempotente: staging temporario + ON CONFLICT.",
        "\\set ON_ERROR_STOP on",
        "BEGIN;",
        "SET LOCAL search_path TO wyd, public;",
        "",
    ]
    for spec in TABLES:
        columns = ", ".join(spec.columns)
        lines.append(
            f"CREATE TEMP TABLE stage_{spec.name} "
            f"(LIKE wyd.{spec.name} INCLUDING DEFAULTS) ON COMMIT DROP;"
        )
        # LIKE copia NOT NULL mas nao copia GENERATED ... AS IDENTITY. Essas
        # duas tabelas tem id identity e o CSV nao o emite; sem o DROP NOT
        # NULL o COPY do staging falharia antes mesmo do INSERT.
        if spec.name in {"item_ledger", "import_issues"}:
            lines.append(
                f"ALTER TABLE stage_{spec.name} ALTER COLUMN id DROP NOT NULL;"
            )
        lines.append(
            f"\\copy stage_{spec.name} ({columns}) FROM '{spec.name}.csv' "
            "WITH (FORMAT csv, HEADER true, NULL '')"
        )
        lines.append(
            f"INSERT INTO wyd.{spec.name} ({columns}) "
            f"SELECT {columns} FROM stage_{spec.name} "
            f"{_conflict_clause(spec)};"
        )
        lines.append("")

    lines.extend(
        [
            f"UPDATE wyd.import_runs SET status = 'succeeded', finished_at = now() "
            f"WHERE id = '{run_id}';",
            "COMMIT;",
            "",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pacote + verificacao
# ---------------------------------------------------------------------------

def write_package(
    outdir: Path,
    accounts: list[MigratedAccount],
    report: dict[str, Any],
    *,
    ok: bool,
) -> list[dict[str, Any]]:
    outdir.mkdir(parents=True, exist_ok=True)

    account_rows = [account_row(account) for account in accounts]
    character_rows = [
        character_row(account, character)
        for account in accounts
        for character in account.source.characters
    ]
    affect_list = [row for account in accounts for row in affect_rows(account)]
    item_list = [item_row(account, character, item) for account in accounts for character, item in _iter_items(account)]
    ledger_list = [row for account in accounts for row in ledger_rows(account, report["run_id"])]
    issue_list = [issue_row(report, issue) for issue in report.get("issues", [])]
    run_list = [run_row(report)]

    write_csv(outdir / "accounts.csv", ACCOUNTS.columns, account_rows)
    write_csv(outdir / "characters.csv", CHARACTERS.columns, character_rows)
    write_csv(outdir / "character_affects.csv", AFFECTS.columns, affect_list)
    write_csv(outdir / "items.csv", ITEMS.columns, item_list)
    write_csv(outdir / "item_ledger.csv", LEDGER.columns, ledger_list)
    write_csv(outdir / "import_runs.csv", RUNS.columns, run_list)
    write_csv(outdir / "import_issues.csv", ISSUES.columns, issue_list)

    with (outdir / "records.jsonl").open("w", encoding="utf-8") as handle:
        for account in accounts:
            for record in audit_records(account, report):
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    if ok:
        (outdir / "load.sql").write_text(load_sql(report), encoding="utf-8")
        blocked = outdir / "LOAD_BLOCKED.txt"
        if blocked.exists():
            blocked.unlink()
    else:
        (outdir / "LOAD_BLOCKED.txt").write_text(
            "Pacote NAO carregavel: existem erros no relatorio.\n"
            "Corrija os issues de severidade 'error' e gere novamente.\n",
            encoding="utf-8",
        )
        stale = outdir / "load.sql"
        if stale.exists():
            stale.unlink()

    checks = verify_package(outdir, accounts, report, ok=ok)
    if ok and any(check["status"] == "fail" for check in checks):
        # Nunca deixar um load.sql carregavel ao lado de um pacote que falhou
        # na propria verificacao.
        (outdir / "load.sql").unlink(missing_ok=True)
        (outdir / "LOAD_BLOCKED.txt").write_text(
            "Pacote NAO carregavel: a verificacao do proprio pacote falhou.\n"
            "Ver report.json (checks com status=fail).\n",
            encoding="utf-8",
        )
        checks.append(
            {
                "code": "package_blocked_after_verification",
                "status": "fail",
                "account": None,
                "detail": {"failed": [c["code"] for c in checks if c["status"] == "fail"]},
            }
        )
    return checks


def verify_package(
    outdir: Path,
    accounts: list[MigratedAccount],
    report: dict[str, Any],
    *,
    ok: bool,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(code: str, passed: bool, detail: dict[str, Any] | None = None) -> None:
        checks.append(
            {
                "code": code,
                "status": "pass" if passed else "fail",
                "account": None,
                "detail": detail or {},
            }
        )

    def read_rows(name: str) -> list[dict[str, str]]:
        with (outdir / name).open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    expected_characters = sum(len(account.source.characters) for account in accounts)
    expected_equip = sum(len(c.equip) for a in accounts for c in a.source.characters)
    expected_carry = sum(len(c.carry) for a in accounts for c in a.source.characters)
    expected_cargo = sum(len(a.source.cargo) for a in accounts)
    expected_items = expected_equip + expected_carry + expected_cargo
    expected_affects = sum(len(c.affects) for a in accounts for c in a.source.characters)
    expected_gold = sum(
        sum(c.coin for c in a.source.characters) + a.source.cargo_gold for a in accounts
    )
    expected_exp = sum(sum(c.exp for c in a.source.characters) for a in accounts)

    account_rows = read_rows("accounts.csv")
    character_rows = read_rows("characters.csv")
    item_rows = read_rows("items.csv")
    affect_rows_read = read_rows("character_affects.csv")
    ledger_rows_read = read_rows("item_ledger.csv")

    add("package_accounts_count", len(account_rows) == len(accounts), {"got": len(account_rows), "want": len(accounts)})
    add(
        "package_characters_count",
        len(character_rows) == expected_characters,
        {"got": len(character_rows), "want": expected_characters},
    )
    add("package_items_count", len(item_rows) == expected_items, {"got": len(item_rows), "want": expected_items})
    add(
        "package_affects_count",
        len(affect_rows_read) == expected_affects,
        {"got": len(affect_rows_read), "want": expected_affects},
    )
    add(
        "package_ledger_covers_items",
        len(ledger_rows_read) == expected_items,
        {"got": len(ledger_rows_read), "want": expected_items},
    )
    add(
        "package_gold_reconciled",
        sum(int(row["gold"]) for row in character_rows) + sum(int(row["cargo_gold"]) for row in account_rows)
        == expected_gold,
        {"expected": expected_gold},
    )
    add(
        "package_exp_reconciled",
        sum(int(row["exp"]) for row in character_rows) == expected_exp,
        {"expected": expected_exp},
    )

    # Senha: hash obrigatorio e nunca igual ao texto plano.
    hash_ok = True
    secrets = [a.source.info.password for a in accounts if a.source.info.password]
    for row in account_rows:
        value = row["password_hash"]
        if not (value.startswith("$argon2") or value.startswith("pbkdf2-sha256$")):
            hash_ok = False
        if value in secrets:
            hash_ok = False
    add("package_passwords_hashed", hash_ok)

    # PIN: hash obrigatorio quando presente.
    token_ok = all(
        not row["numeric_token_hash"]
        or row["numeric_token_hash"].startswith("$argon2")
        or row["numeric_token_hash"].startswith("pbkdf2-sha256$")
        for row in account_rows
    )
    add("package_pins_hashed", token_ok)

    # Nenhum arquivo do pacote pode conter a senha em texto plano. O corte em
    # 8 caracteres evita falso positivo com numeros (gold, exp, indices).
    leaked: list[str] = []
    candidates = [pw for pw in secrets if len(pw) >= 8]
    for path in outdir.iterdir():
        if not path.is_file() or path.suffix not in {".csv", ".jsonl", ".sql", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(pw in text for pw in candidates):
            leaked.append(path.name)
    add("package_no_plaintext_password", not leaked, {"files": leaked})

    records = (outdir / "records.jsonl").read_text(encoding="utf-8")
    add("package_jsonl_has_no_hash", "password_hash" not in records)

    if ok:
        sql = (outdir / "load.sql").read_text(encoding="utf-8")
        add(
            "package_load_sql_idempotent",
            "ON CONFLICT" in sql and "BEGIN;" in sql and "COMMIT;" in sql,
        )
        add("package_load_sql_present", True)
    else:
        add("package_load_sql_blocked", (outdir / "LOAD_BLOCKED.txt").exists())
        add("package_load_sql_absent_on_error", not (outdir / "load.sql").exists())

    return checks
