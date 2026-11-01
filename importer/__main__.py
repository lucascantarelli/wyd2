"""CLI do importador.

    python -m importer --source legacy/accounts            # dry-run (padrao)
    python -m importer --source legacy/accounts --emit out # pacote para COPY
    python -m importer --source legacy/accounts --report out/report.json

Sem `--emit`, nada e gravado alem do relatorio. O pacote (CSV + JSONL +
load.sql) so e gerado com `--emit`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import SCHEMA_VERSION, TOOL_NAME, __version__
from . import ids
from . import layout as L
from .decode import decode_account
from .emit import write_package
from .errors import LegacyFormatError
from .migrate import migrate_account
from .reconcile import Reconciler


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def discover(source: Path) -> list[Path]:
    """Arquivos de conta sob `source`, em ordem estavel.

    Contas legadas nao tem extensao; qualquer arquivo regular e candidato. O
    detector de tamanho decide o que e conta. Arquivos ocultos sao ignorados.
    """
    if source.is_file():
        return [source]
    files = []
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if any(part.startswith(".") for part in relative.parts):
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(source).as_posix())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(source: Path, paths: Iterable[Path]) -> tuple[str, list[dict[str, Any]]]:
    """Hash deterministico do conjunto, independente da ordem de leitura.

    Inclui o caminho relativo: renomear/mover um arquivo muda o manifesto, e
    portanto o `run_id`, que e o que se quer para auditoria.
    """
    root = source if source.is_dir() else source.parent
    combined = hashlib.sha256()
    entries: list[dict[str, Any]] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        digest = sha256_file(path)
        size = path.stat().st_size
        combined.update(relative.encode("utf-8"))
        combined.update(b"\x00")
        combined.update(bytes.fromhex(digest))
        entries.append({"path": relative, "size": size, "sha256": digest})
    return combined.hexdigest(), entries


def load_catalog(path: Path) -> set[int]:
    """Le os indices da primeira coluna de ItemList.csv (cp1252/latin-1)."""
    raw = path.read_bytes()
    try:
        text = raw.decode("cp1252")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    indexes: set[int] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        first = line.split(",", 1)[0].strip()
        if first.isdigit():
            indexes.add(int(first))
    return indexes


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def print_summary(report: dict[str, Any], report_path: Path) -> None:
    totals = report["totals"]
    issues = report["issues_by_severity"]
    print(f"{TOOL_NAME} {__version__}  (schema {SCHEMA_VERSION})")
    print(f"fonte      : {report['source']}")
    print(f"run_id     : {report['run_id']}")
    print(f"manifesto  : {report['manifest_sha256']}")
    print(
        "arquivos   : {seen} vistos, {decoded} decodificados, {skipped} pulados".format(
            seen=totals["files_seen"],
            decoded=totals["files_decoded"],
            skipped=totals["files_skipped"],
        )
    )
    print(
        "conteudo   : {accounts} contas, {characters} personagens, {items} itens, "
        "{gold} gold, {exp} exp".format(
            accounts=totals["accounts"],
            characters=totals["characters"],
            items=totals["items_total"],
            gold=totals["gold_total"],
            exp=totals["exp_total"],
        )
    )
    if report.get("characters_by_tier"):
        tiers = ", ".join(f"{k}={v}" for k, v in report["characters_by_tier"].items())
        print(f"tiers      : {tiers}")
    print(f"issues     : {issues['error']} erro(s), {issues['warning']} aviso(s)")
    print(f"status     : {'OK' if report['ok'] else 'FALHOU'}")
    print(f"relatorio  : {report_path}")
    if "package" in report:
        checks = report["package"]["checks"]
        failed = [c for c in checks if c["status"] == "fail"]
        print(f"pacote     : {report['package']['path']} ({len(checks) - len(failed)}/{len(checks)} checks)")
        for check in failed:
            print(f"  FALHA {check['code']}: {check['detail']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m importer",
        description="Importa STRUCT_ACCOUNTFILE legado para o schema PostgreSQL do projeto.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="arquivo de conta ou diretorio que contem os arquivos",
    )
    parser.add_argument(
        "--emit",
        metavar="DIR",
        help="grava o pacote (CSV, JSONL, load.sql) em DIR; sem isso, dry-run",
    )
    parser.add_argument(
        "--report",
        metavar="PATH",
        help="caminho do report.json (padrao: DIR/report.json ou out/report.json)",
    )
    parser.add_argument(
        "--catalog",
        metavar="ITEMLIST_CSV",
        help="ItemList.csv para validar sIndex contra o catalogo",
    )
    parser.add_argument(
        "--allow-padded-legacy",
        action="store_true",
        help=(
            "aceita contas de 7500..7600 bytes zero-padded ate 7952 "
            "(gera aviso; 4294 continua recusado)"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="processa apenas os N primeiros arquivos (teste)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{TOOL_NAME} {__version__} (schema {SCHEMA_VERSION})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    source = Path(args.source)
    if not source.exists():
        print(f"erro: fonte nao encontrada: {source}", file=sys.stderr)
        return 2
    if args.limit is not None and args.limit <= 0:
        print("erro: --limit deve ser positivo", file=sys.stderr)
        return 2

    catalog: set[int] | None = None
    if args.catalog:
        catalog_path = Path(args.catalog)
        if not catalog_path.is_file():
            print(f"erro: catalogo nao encontrado: {catalog_path}", file=sys.stderr)
            return 2
        catalog = load_catalog(catalog_path)

    paths = discover(source)
    if args.limit is not None:
        paths = paths[: args.limit]
    if not paths:
        print(f"erro: nenhum arquivo em {source}", file=sys.stderr)
        return 2

    started_at = utc_now()
    manifest_sha256, inventory = build_manifest(source, paths)
    run_id = str(ids.import_run_id(str(source), manifest_sha256))
    reconciler = Reconciler(catalog)
    migrated = []

    for path in paths:
        try:
            data = path.read_bytes()
        except OSError as exc:
            reconciler.skip_file(
                str(path),
                0,
                None,
                "read_error",
                detail={"error": exc.__class__.__name__},
            )
            continue

        version = L.detect_version(len(data))
        if version is None:
            reconciler.skip_file(str(path), len(data), None, "unknown_account_size")
            continue
        supported = version == L.VERSION_CURRENT or (
            version == L.VERSION_INTERMEDIATE and args.allow_padded_legacy
        )
        if not supported:
            reconciler.skip_file(
                str(path),
                len(data),
                version,
                "unsupported_account_version",
                detail={
                    "supported": L.ACCOUNT_SIZE_CURRENT,
                    "hint": (
                        "use --allow-padded-legacy para 7500..7600; "
                        "4294 exige layout legado verificado"
                    ),
                },
            )
            continue

        try:
            account = decode_account(
                data,
                str(path),
                allow_padded_legacy=args.allow_padded_legacy,
            )
        except LegacyFormatError as exc:
            reconciler.skip_file(
                str(path),
                len(data),
                version,
                "decode_error",
                detail={"error": exc.__class__.__name__, "message": str(exc)},
            )
            continue

        first_seen = reconciler.register_login(account)
        if first_seen is not None:
            reconciler.skip_file(
                str(path),
                len(data),
                version,
                "duplicate_account_login",
                detail={
                    "login": account.info.name.strip().lower(),
                    "first_seen": first_seen,
                },
            )
            continue

        reconciler.count_file(account.version, len(data), skipped=False)
        reconciler.check_account(account)
        migrated.append(migrate_account(account))

    finished_at = utc_now()
    report = reconciler.report(
        run_id=run_id,
        source=str(source),
        manifest_sha256=manifest_sha256,
        mode="commit" if args.emit else "dry_run",
        started_at=started_at,
        finished_at=finished_at,
    )
    report["files"] = inventory
    report["ok"] = bool(report["ok"])

    if args.emit:
        outdir = Path(args.emit)
        package_checks = write_package(outdir, migrated, report, ok=report["ok"])
        failed = [check for check in package_checks if check["status"] == "fail"]
        report["package"] = {
            "path": str(outdir),
            "checks": package_checks,
        }
        if failed:
            report["ok"] = False
        report_path = Path(args.report) if args.report else outdir / "report.json"
    else:
        report_path = Path(args.report) if args.report else Path("out") / "report.json"

    report["finished_at"] = finished_at
    write_report(report_path, report)
    print_summary(report, report_path)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
