from __future__ import annotations

import csv
import json
import struct
import tempfile
import unittest
from pathlib import Path

from importer import layout as L
from importer.decode import decode_account
from importer.emit import write_package
from importer.migrate import migrate_account
from importer.reconcile import Reconciler
from tests.fixtures import LOGIN, PASSWORD, build_account


def make_report(account, catalog=None):
    reconciler = Reconciler(catalog)
    reconciler.count_file(L.VERSION_CURRENT, account.size, skipped=False)
    reconciler.check_account(account)
    return reconciler.report(
        run_id="00000000-0000-0000-0000-000000000001",
        source="fixture",
        manifest_sha256="0" * 64,
        mode="commit",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
    )


class PackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.account = decode_account(build_account(), "fixture")
        self.report = make_report(self.account)
        self.migrated = [migrate_account(self.account)]
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "out"
        self.checks = write_package(self.out, self.migrated, self.report, ok=self.report["ok"])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def read(self, name: str) -> list[dict[str, str]]:
        with (self.out / name).open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_relatorio_ok(self) -> None:
        self.assertTrue(self.report["ok"])
        self.assertEqual(self.report["totals"]["accounts"], 1)
        self.assertEqual(self.report["totals"]["characters"], 2)
        self.assertEqual(self.report["totals"]["items_total"], 5)
        self.assertEqual(self.report["totals"]["gold_total"], 2500)
        self.assertEqual(self.report["totals"]["exp_total"], 251_000)
        self.assertEqual(self.report["characters_by_tier"]["MORTAL"], 2)

    def test_contagens_do_pacote(self) -> None:
        self.assertEqual(len(self.read("accounts.csv")), 1)
        self.assertEqual(len(self.read("characters.csv")), 2)
        self.assertEqual(len(self.read("items.csv")), 5)
        self.assertEqual(len(self.read("item_ledger.csv")), 5)
        self.assertEqual(len(self.read("character_affects.csv")), 1)
        self.assertEqual(len(self.read("import_issues.csv")), 0)
        self.assertFalse([c for c in self.checks if c["status"] == "fail"], self.checks)

    def test_dono_dos_itens(self) -> None:
        items = self.read("items.csv")
        equip = [row for row in items if row["container"] == "equip"]
        cargo = [row for row in items if row["container"] == "cargo"]
        self.assertTrue(all(row["owner_character_id"] for row in equip))
        self.assertTrue(all(not row["owner_account_id"] for row in equip))
        self.assertTrue(all(row["owner_account_id"] for row in cargo))
        self.assertTrue(all(not row["owner_character_id"] for row in cargo))

    def test_senha_nunca_em_claro(self) -> None:
        account = self.read("accounts.csv")[0]
        self.assertEqual(account["login"], LOGIN)
        self.assertTrue(
            account["password_hash"].startswith("$argon2")
            or account["password_hash"].startswith("pbkdf2-sha256$")
        )
        self.assertNotEqual(account["password_hash"], PASSWORD)
        self.assertTrue(account["numeric_token_hash"])
        for path in self.out.iterdir():
            if path.suffix in {".csv", ".jsonl", ".sql", ".json"}:
                self.assertNotIn(PASSWORD, path.read_text(encoding="utf-8"), path.name)

    def test_jsonl_sem_hash(self) -> None:
        records = (self.out / "records.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("password_hash", records)
        types = [json.loads(line)["type"] for line in records.splitlines()]
        self.assertEqual(types.count("account"), 1)
        self.assertEqual(types.count("character"), 2)
        self.assertEqual(types.count("item"), 5)
        self.assertEqual(types[-1], "import")

    def test_load_sql(self) -> None:
        sql = (self.out / "load.sql").read_text(encoding="utf-8")
        self.assertIn("BEGIN;", sql)
        self.assertIn("COMMIT;", sql)
        self.assertIn("ON CONFLICT (id) DO UPDATE SET", sql)
        self.assertIn("\\copy stage_characters", sql)
        self.assertNotIn(PASSWORD, sql)

    def test_current_special(self) -> None:
        rows = self.read("characters.csv")
        header = (self.out / "characters.csv").read_text(encoding="utf-8").splitlines()[0]
        self.assertIn("current_special", header.split(","))
        self.assertEqual(rows[0]["current_special"], "{1,2,3,4}")


class BlockedPackageTest(unittest.TestCase):
    def test_gold_negativo_bloqueia_load(self) -> None:
        raw = bytearray(build_account())
        struct.pack_into("<i", raw, L.CHAR_BASE + L.MOB_COIN, -1)
        account = decode_account(bytes(raw), "fixture")
        report = make_report(account)
        self.assertFalse(report["ok"])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            checks = write_package(out, [migrate_account(account)], report, ok=report["ok"])
            self.assertTrue((out / "LOAD_BLOCKED.txt").exists())
            self.assertFalse((out / "load.sql").exists())
            self.assertTrue([c for c in checks if c["code"] == "package_load_sql_absent_on_error"])


if __name__ == "__main__":
    unittest.main()
