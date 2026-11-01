"""Reconciliacao da importacao.

O relatorio responde tres perguntas:
1. Todo arquivo foi lido, recusado explicitamente ou ignorado por tamanho?
2. Todo personagem/item/ouro/EXP decodificado foi contabilizado?
3. Ha dados que o banco vai recusar (nome duplicado, classe invalida, etc.)?

Nenhum hash ou senha em texto plano entra no relatorio.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from . import SCHEMA_VERSION, TOOL_NAME, __version__
from .layout import VERSION_INTERMEDIATE_PADDED, class_master_name
from .model import AccountFile, ImportIssue


CLASS_NAMES = {0: "TransKnight", 1: "Foema", 2: "BeastMaster", 3: "Huntress"}


def _item_iter(account: AccountFile):
    for character in account.characters:
        yield from character.equip
        yield from character.carry
    yield from account.cargo


class Reconciler:
    def __init__(self, catalog: set[int] | None = None) -> None:
        self.catalog = catalog
        self.issues: list[ImportIssue] = []
        self.checks: list[dict[str, Any]] = []
        self.account_summaries: list[dict[str, Any]] = []
        self.versions: Counter[str] = Counter()
        self.skipped: list[dict[str, Any]] = []
        self._seen_names: dict[str, str] = {}
        self._seen_logins: dict[str, str] = {}
        self.totals: dict[str, int] = {
            "files_seen": 0,
            "files_decoded": 0,
            "files_skipped": 0,
            "accounts": 0,
            "characters": 0,
            "equip_items": 0,
            "carry_items": 0,
            "cargo_items": 0,
            "items_total": 0,
            "gold_total": 0,
            "exp_total": 0,
            "donate_total": 0,
        }
        self.characters_by_tier: Counter[str] = Counter()
        self.characters_by_class: Counter[str] = Counter()

    # -- registros ---------------------------------------------------------

    def issue(
        self,
        severity: str,
        code: str,
        *,
        account: str | None = None,
        path: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.issues.append(
            ImportIssue(
                severity=severity,
                code=code,
                account=account,
                path=path,
                detail=detail or {},
            )
        )

    def check(
        self,
        code: str,
        ok: bool,
        *,
        account: str | None = None,
        detail: dict[str, Any] | None = None,
        severity: str = "error",
    ) -> None:
        self.checks.append(
            {
                "code": code,
                "status": "pass" if ok else ("warn" if severity == "warning" else "fail"),
                "account": account,
                "detail": detail or {},
            }
        )
        if not ok:
            self.issue(
                severity,
                code,
                account=account,
                detail=detail,
            )

    def count_file(self, version: str | None, size: int, *, skipped: bool) -> None:
        self.totals["files_seen"] += 1
        if skipped:
            self.totals["files_skipped"] += 1
        else:
            self.totals["files_decoded"] += 1
        self.versions[version or f"unknown_{size}"] += 1

    def skip_file(
        self,
        path: str,
        size: int,
        version: str | None,
        reason: str,
        *,
        severity: str = "error",
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.count_file(version, size, skipped=True)
        self.skipped.append(
            {"path": path, "size": size, "version": version, "reason": reason}
        )
        payload: dict[str, Any] = {"size": size, "version": version}
        if detail:
            payload.update(detail)
        self.issue(severity, reason, path=path, detail=payload)

    def register_login(self, account: AccountFile) -> str | None:
        """Retorna o caminho da primeira conta se o login ja foi reivindicado."""
        canonical = account.info.name.strip().lower()
        if canonical in self._seen_logins:
            return self._seen_logins[canonical]
        self._seen_logins[canonical] = account.path
        return None

    # -- conta -------------------------------------------------------------

    def check_account(self, account: AccountFile) -> None:
        login = account.info.name.strip()
        canonical = login.lower()

        self.totals["accounts"] += 1
        self.check("account_login_present", bool(login), account=canonical or account.path)

        if account.version == VERSION_INTERMEDIATE_PADDED:
            self.issue(
                "warning",
                "legacy_account_zero_padded",
                account=canonical,
                path=account.path,
                detail={
                    "size": account.size,
                    "padding_bytes": account.padding_bytes,
                    "note": "Donate/IsBlocked e o fim de mobExtra podem estar zerados",
                },
            )

        if not account.info.password:
            self.issue("warning", "empty_password", account=canonical, path=account.path)

        if not account.characters:
            self.issue("warning", "account_without_characters", account=canonical, path=account.path)

        names_in_account: set[str] = set()
        for character in account.characters:
            name = character.name.strip()
            self.totals["characters"] += 1
            self.totals["equip_items"] += len(character.equip)
            self.totals["carry_items"] += len(character.carry)
            self.totals["gold_total"] += character.coin
            self.totals["exp_total"] += character.exp

            tier = class_master_name(character.extra.class_master)
            self.characters_by_tier[tier] += 1
            self.characters_by_class[CLASS_NAMES.get(character.char_class, f"unknown_{character.char_class}")] += 1

            if not name:
                self.issue(
                    "error",
                    "character_name_empty",
                    account=canonical,
                    path=account.path,
                    detail={"slot": character.slot},
                )
            else:
                lowered = name.lower()
                if lowered in names_in_account:
                    self.issue(
                        "error",
                        "duplicate_character_name_in_account",
                        account=canonical,
                        path=account.path,
                        detail={"name": name, "slot": character.slot},
                    )
                names_in_account.add(lowered)

                if lowered in self._seen_names:
                    self.issue(
                        "error",
                        "duplicate_character_name_global",
                        account=canonical,
                        path=account.path,
                        detail={
                            "name": name,
                            "slot": character.slot,
                            "first_seen": self._seen_names[lowered],
                        },
                    )
                else:
                    self._seen_names[lowered] = f"{account.path}#slot:{character.slot}"

            if not 0 <= character.char_class <= 3:
                self.issue(
                    "error",
                    "character_class_invalid",
                    account=canonical,
                    path=account.path,
                    detail={"slot": character.slot, "class": character.char_class},
                )
            if not 0 <= character.extra.class_master <= 5:
                self.issue(
                    "error",
                    "class_master_invalid",
                    account=canonical,
                    path=account.path,
                    detail={"slot": character.slot, "class_master": character.extra.class_master},
                )
            if not 0 <= character.base.level <= 999:
                self.issue(
                    "error",
                    "character_level_out_of_range",
                    account=canonical,
                    path=account.path,
                    detail={"slot": character.slot, "level": character.base.level},
                )
            if not 0 <= character.extra.arch_level <= 255:
                self.issue(
                    "error",
                    "arch_level_out_of_range",
                    account=canonical,
                    path=account.path,
                    detail={"slot": character.slot, "arch_level": character.extra.arch_level},
                )
            if character.extra.celestial_level < 0 or character.extra.sub_celestial_level < 0:
                self.issue(
                    "error",
                    "celestial_level_negative",
                    account=canonical,
                    path=account.path,
                    detail={
                        "slot": character.slot,
                        "celestial_level": character.extra.celestial_level,
                        "sub_celestial_level": character.extra.sub_celestial_level,
                    },
                )
            if character.extra.fame < 0:
                self.issue(
                    "error",
                    "fame_negative",
                    account=canonical,
                    path=account.path,
                    detail={"slot": character.slot, "fame": character.extra.fame},
                )
            if character.coin < 0:
                self.issue(
                    "error",
                    "character_gold_negative",
                    account=canonical,
                    path=account.path,
                    detail={"slot": character.slot, "gold": character.coin},
                )
            if character.exp < 0:
                self.issue(
                    "error",
                    "character_exp_negative",
                    account=canonical,
                    path=account.path,
                    detail={"slot": character.slot, "exp": character.exp},
                )

        self.totals["cargo_items"] += len(account.cargo)
        self.totals["donate_total"] += account.donate
        self.totals["gold_total"] += account.cargo_gold

        if account.cargo_gold < 0:
            self.issue(
                "error",
                "cargo_gold_negative",
                account=canonical,
                path=account.path,
                detail={"cargo_gold": account.cargo_gold},
            )
        if account.donate < 0:
            self.issue(
                "error",
                "donate_negative",
                account=canonical,
                path=account.path,
                detail={"donate": account.donate},
            )

        # Refino fora de faixa e itens fora do catalogo.
        bad_refines: list[dict[str, Any]] = []
        missing_items: set[int] = set()
        for item in _item_iter(account):
            if not (0 <= item.refine <= 15) or not (0 <= item.pity <= 20):
                bad_refines.append(
                    {"container": item.container, "slot": item.slot, "refine": item.refine, "pity": item.pity}
                )
            if self.catalog is not None and item.item_index not in self.catalog:
                missing_items.add(item.item_index)

        if bad_refines:
            self.issue(
                "warning",
                "refine_out_of_range",
                account=canonical,
                path=account.path,
                detail={"items": bad_refines[:20], "count": len(bad_refines)},
            )
        if missing_items:
            self.issue(
                "warning",
                "catalog_missing_item",
                account=canonical,
                path=account.path,
                detail={"indexes": sorted(missing_items)[:20], "count": len(missing_items)},
            )

        self.account_summaries.append(
            {
                "login": canonical,
                "path": account.path,
                "size": account.size,
                "version": account.version,
                "sha256": account.sha256,
                "characters": len(account.characters),
                "equip_items": sum(len(c.equip) for c in account.characters),
                "carry_items": sum(len(c.carry) for c in account.characters),
                "cargo_items": len(account.cargo),
                "gold": sum(c.coin for c in account.characters) + account.cargo_gold,
                "exp": sum(c.exp for c in account.characters),
            }
        )

    # -- relatorio ---------------------------------------------------------

    def report(
        self,
        *,
        run_id: str,
        source: str,
        manifest_sha256: str,
        mode: str,
        started_at: str,
        finished_at: str,
        extra_checks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.totals["items_total"] = (
            self.totals["equip_items"] + self.totals["carry_items"] + self.totals["cargo_items"]
        )

        checks = self.checks + (extra_checks or [])
        errors = sum(1 for issue in self.issues if issue.severity == "error")
        warnings = sum(1 for issue in self.issues if issue.severity == "warning")

        return {
            "tool": {"name": TOOL_NAME, "version": __version__},
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "source": source,
            "manifest_sha256": manifest_sha256,
            "mode": mode,
            "started_at": started_at,
            "finished_at": finished_at,
            "ok": errors == 0,
            "totals": dict(self.totals),
            "versions": dict(sorted(self.versions.items())),
            "characters_by_tier": dict(sorted(self.characters_by_tier.items())),
            "characters_by_class": dict(sorted(self.characters_by_class.items())),
            "issues_by_severity": {"error": errors, "warning": warnings},
            "checks": checks,
            "issues": [issue.to_dict() for issue in self.issues],
            "accounts": self.account_summaries,
            "skipped": self.skipped,
        }
