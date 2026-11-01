from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "review_report", ROOT / "scripts" / "review_report.py"
)
assert SPEC and SPEC.loader
review_report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review_report)


def good_report() -> dict:
    return {
        "source": "fixture",
        "run_id": "00000000-0000-0000-0000-000000000001",
        "manifest_sha256": "0" * 64,
        "ok": True,
        "mode": "dry_run",
        "totals": {
            "files_seen": 1,
            "files_decoded": 1,
            "files_skipped": 0,
            "accounts": 1,
            "characters": 1,
            "items_total": 1,
            "gold_total": 10,
            "exp_total": 20,
        },
        "accounts": [
            {
                "login": "a",
                "characters": 1,
                "equip_items": 1,
                "carry_items": 0,
                "cargo_items": 0,
            }
        ],
        "versions": {"current_7952": 1},
        "files": [{"path": "a", "size": 7952}],
        "skipped": [],
        "issues": [],
        "issues_by_severity": {"error": 0, "warning": 0},
        "checks": [],
    }


class ReviewReportTest(unittest.TestCase):
    def test_relatorio_consistente(self) -> None:
        summary, errors, warnings, ok = review_report.review(good_report())
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertTrue(any("1 contas" in line for line in summary))

    def test_contagem_inconsistente_bloqueia(self) -> None:
        report = good_report()
        report["totals"]["files_seen"] = 2
        _, errors, _, ok = review_report.review(report)
        self.assertFalse(ok)
        self.assertTrue(any("contagem de arquivos" in error for error in errors))

    def test_limite_de_container_bloqueia(self) -> None:
        report = good_report()
        report["accounts"][0]["carry_items"] = 65
        report["totals"]["items_total"] = 65
        report["totals"]["characters"] = 1
        _, errors, _, ok = review_report.review(report)
        self.assertFalse(ok)
        self.assertTrue(any("fora do limite" in error for error in errors))

    def test_pacote_com_falha_bloqueia(self) -> None:
        report = good_report()
        report["mode"] = "commit"
        report["package"] = {
            "path": "out",
            "checks": [{"code": "package_x", "status": "fail"}],
        }
        _, errors, _, ok = review_report.review(report)
        self.assertFalse(ok)
        self.assertTrue(any("checks do pacote" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
