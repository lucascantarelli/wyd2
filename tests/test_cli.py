from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.fixtures import PASSWORD, build_account, write_account

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "importer", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.accounts = self.root / "accounts"
        write_account(self.accounts / "TestAccount")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_dry_run(self) -> None:
        report_path = self.root / "report.json"
        result = run_cli("--source", str(self.accounts), "--report", str(report_path))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["mode"], "dry_run")
        self.assertTrue(report["ok"])
        self.assertEqual(report["totals"]["files_decoded"], 1)
        self.assertEqual(report["totals"]["accounts"], 1)
        self.assertFalse((self.root / "out").exists())
        self.assertNotIn(PASSWORD, report_path.read_text(encoding="utf-8"))

    def test_emit(self) -> None:
        out = self.root / "out"
        result = run_cli("--source", str(self.accounts), "--emit", str(out))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue((out / "load.sql").exists())
        self.assertTrue((out / "accounts.csv").exists())
        report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["mode"], "commit")
        self.assertTrue(report["ok"])
        self.assertTrue(report["package"]["checks"])
        self.assertFalse(
            [c for c in report["package"]["checks"] if c["status"] == "fail"]
        )

    def test_tamanho_desconhecido_falha(self) -> None:
        (self.accounts / "zzz_lixo").write_bytes(b"\x00" * 100)
        report_path = self.root / "report.json"
        result = run_cli("--source", str(self.accounts), "--report", str(report_path))
        self.assertEqual(result.returncode, 1)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertFalse(report["ok"])
        self.assertEqual(report["skipped"][0]["reason"], "unknown_account_size")
        self.assertEqual(report["issues_by_severity"]["error"], 1)

    def test_login_duplicado_e_pulado(self) -> None:
        write_account(self.accounts / "zzz_duplicada")
        report_path = self.root / "report.json"
        result = run_cli("--source", str(self.accounts), "--report", str(report_path))
        self.assertEqual(result.returncode, 1)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["totals"]["accounts"], 1)
        self.assertEqual(report["totals"]["files_skipped"], 1)
        codes = [issue["code"] for issue in report["issues"]]
        self.assertIn("duplicate_account_login", codes)

    def test_catalogo_gera_aviso(self) -> None:
        catalog = self.root / "ItemList.csv"
        catalog.write_text("index,Name\n100,TransKnight\n", encoding="cp1252")
        report_path = self.root / "report.json"
        result = run_cli(
            "--source",
            str(self.accounts),
            "--catalog",
            str(catalog),
            "--report",
            str(report_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        codes = [issue["code"] for issue in report["issues"]]
        self.assertIn("catalog_missing_item", codes)

    def test_padded_legacy_exige_flag(self) -> None:
        legacy = self.root / "legacy"
        legacy.mkdir()
        (legacy / "TestAccount").write_bytes(build_account()[:7600])
        report_path = self.root / "report.json"

        result = run_cli("--source", str(legacy), "--report", str(report_path))
        self.assertEqual(result.returncode, 1)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["skipped"][0]["reason"], "unsupported_account_version")

        result = run_cli(
            "--source",
            str(legacy),
            "--allow-padded-legacy",
            "--report",
            str(report_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["versions"]["intermediate_7500_7600_padded"], 1)
        codes = [issue["code"] for issue in report["issues"]]
        self.assertIn("legacy_account_zero_padded", codes)
        self.assertEqual(report["totals"]["accounts"], 1)

    def test_limit(self) -> None:
        write_account(self.accounts / "zzz_outra", login="OtherAccount")
        report_path = self.root / "report.json"
        result = run_cli(
            "--source",
            str(self.accounts),
            "--limit",
            "1",
            "--report",
            str(report_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["totals"]["accounts"], 1)


if __name__ == "__main__":
    unittest.main()
