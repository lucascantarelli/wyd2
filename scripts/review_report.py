#!/usr/bin/env python3
"""Revisa um report.json do importador e aponta o que bloqueia a carga.

Uso:
    python scripts/review_report.py out/report.json
    python scripts/review_report.py out/report.json --markdown out/review.md

Saida: resumo legivel + achados. Codigo de saida 1 se o relatorio estiver
bloqueado (ok=false ou check de pacote com fail), 0 se estiver apto.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def load_report(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("report.json nao e um objeto")
    return data


def _int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _accounts(report: dict[str, Any]) -> list[dict[str, Any]]:
    accounts = report.get("accounts")
    return accounts if isinstance(accounts, list) else []


def review(report: dict[str, Any]) -> tuple[list[str], list[str], list[str], bool]:
    """Retorna (linhas de resumo, erros, avisos, apto)."""
    totals = report.get("totals", {})
    if not isinstance(totals, dict):
        totals = {}
    accounts = _accounts(report)
    issues = report.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    checks = report.get("checks", [])
    if not isinstance(checks, list):
        checks = []
    package = report.get("package")
    package_checks = package.get("checks", []) if isinstance(package, dict) else []

    errors: list[str] = []
    warnings: list[str] = []
    summary: list[str] = []

    files_seen = _int(totals.get("files_seen"))
    decoded = _int(totals.get("files_decoded"))
    skipped = _int(totals.get("files_skipped"))
    files_manifest = report.get("files", [])
    manifest_count = len(files_manifest) if isinstance(files_manifest, list) else 0

    if files_seen != decoded + skipped:
        errors.append(
            f"contagem de arquivos inconsistente: vistos={files_seen}, "
            f"decodificados={decoded}, pulados={skipped}"
        )
    if manifest_count and manifest_count != files_seen:
        warnings.append(
            f"manifesto lista {manifest_count} arquivo(s), mas o total e {files_seen}"
        )

    summary.append(
        f"arquivos   : {files_seen} vistos, {decoded} decodificados, {skipped} pulados"
    )
    versions = report.get("versions", {})
    if isinstance(versions, dict) and versions:
        summary.append("versoes    : " + ", ".join(f"{k}={v}" for k, v in versions.items()))

    summary.append(
        "conteudo   : {accounts} contas, {characters} personagens, {items} itens, "
        "{gold} gold, {exp} exp".format(
            accounts=_int(totals.get("accounts")),
            characters=_int(totals.get("characters")),
            items=_int(totals.get("items_total")),
            gold=_int(totals.get("gold_total")),
            exp=_int(totals.get("exp_total")),
        )
    )

    if accounts:
        if len(accounts) != _int(totals.get("accounts")):
            errors.append(
                f"relatorio tem {len(accounts)} conta(s) detalhada(s), "
                f"mas o total e {_int(totals.get('accounts'))}"
            )
        chars = sum(_int(a.get("characters")) for a in accounts)
        if chars != _int(totals.get("characters")):
            errors.append(
                f"soma de personagens por conta ({chars}) != total ({_int(totals.get('characters'))})"
            )
        items = sum(
            _int(a.get("equip_items")) + _int(a.get("carry_items")) + _int(a.get("cargo_items"))
            for a in accounts
        )
        if items != _int(totals.get("items_total")):
            errors.append(
                f"soma de itens por conta ({items}) != total ({_int(totals.get('items_total'))})"
            )

        no_chars = [a.get("login") or a.get("path") for a in accounts if _int(a.get("characters")) == 0]
        if no_chars:
            warnings.append(f"conta(s) sem personagem: {', '.join(map(str, no_chars[:10]))}")
        for account in accounts:
            label = account.get("login") or account.get("path")
            equip = _int(account.get("equip_items"))
            carry = _int(account.get("carry_items"))
            cargo = _int(account.get("cargo_items"))
            if equip > 16 or carry > 64 or cargo > 128:
                errors.append(
                    f"{label}: itens fora do limite equip={equip} carry={carry} cargo={cargo}"
                )

    issue_counts = Counter(
        str(issue.get("code")) for issue in issues if isinstance(issue, dict)
    )
    severity = report.get("issues_by_severity", {})
    if isinstance(severity, dict):
        summary.append(
            f"issues     : {severity.get('error', 0)} erro(s), {severity.get('warning', 0)} aviso(s)"
        )
    if issue_counts:
        summary.append(
            "codigos    : " + ", ".join(f"{code}={count}" for code, count in issue_counts.most_common(12))
        )

    skipped_reasons = Counter(
        str(item.get("reason")) for item in report.get("skipped", []) if isinstance(item, dict)
    )
    if skipped_reasons:
        summary.append(
            "pulados    : " + ", ".join(f"{reason}={count}" for reason, count in skipped_reasons.items())
        )

    failed_checks = [
        str(check.get("code"))
        for check in checks
        if isinstance(check, dict) and check.get("status") == "fail"
    ]
    if failed_checks:
        errors.append("checks de reconciliacao com falha: " + ", ".join(failed_checks))

    if isinstance(package, dict):
        failed_package = [
            str(check.get("code"))
            for check in package_checks
            if isinstance(check, dict) and check.get("status") == "fail"
        ]
        summary.append(
            "pacote     : {path} ({ok}/{total} checks ok)".format(
                path=package.get("path", "?"),
                ok=len(package_checks) - len(failed_package),
                total=len(package_checks),
            )
        )
        if failed_package:
            errors.append("checks do pacote com falha: " + ", ".join(failed_package))

    if not report.get("ok", False):
        errors.append("status do relatorio e ok=false")
    mode = report.get("mode")
    if mode == "dry_run" and not isinstance(package, dict):
        summary.append("modo       : dry-run (nenhum pacote gerado)")
    elif mode == "commit":
        summary.append("modo       : commit (pacote gerado)")
    elif mode:
        summary.append(f"modo       : {mode}")

    if not errors:
        if mode == "dry_run":
            summary.append("proximo    : revisar avisos e gerar o pacote com --emit")
        else:
            summary.append("proximo    : executar schema/001_init.sql e load.sql em PostgreSQL 16")
    else:
        summary.append("proximo    : corrigir os erros acima; o load.sql nao deve ser usado")

    return summary, errors, warnings, not errors


def render(report: dict[str, Any]) -> tuple[str, bool]:
    summary, errors, warnings, ok = review(report)
    lines = [
        "WYD — REVISÃO DO RELATÓRIO",
        f"fonte      : {report.get('source', '?')}",
        f"run_id     : {report.get('run_id', '?')}",
        f"manifesto  : {report.get('manifest_sha256', '?')}",
        f"status     : {'OK' if report.get('ok') else 'BLOQUEADO'}",
        "",
        *summary,
    ]
    if errors:
        lines.extend(["", "ERROS:"])
        lines.extend(f"  - {error}" for error in errors)
    if warnings:
        lines.extend(["", "AVISOS:"])
        lines.extend(f"  - {warning}" for warning in warnings)
    if not errors and not warnings:
        lines.extend(["", "Nenhum achado: relatório consistente."])
    return "\n".join(lines) + "\n", ok


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Revisa report.json do importador WYD.")
    parser.add_argument("report", help="caminho do report.json")
    parser.add_argument("--markdown", metavar="PATH", help="grava a revisão em Markdown")
    args = parser.parse_args(argv)

    path = Path(args.report)
    try:
        report = load_report(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"erro: nao foi possivel ler {path}: {exc}", file=sys.stderr)
        return 2

    text, ok = render(report)
    print(text)
    if args.markdown:
        out = Path(args.markdown)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("```text\n" + text.rstrip() + "\n```\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
