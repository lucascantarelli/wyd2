from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from importer.catalog import (
    EFFECT_COLUMNS,
    ITEM_COLUMNS,
    SKILL_COLUMNS,
    Catalog,
    build_catalog,
    catalog_run_id,
    item_rows,
    load_catalog_sql,
    read_used_items,
    reconcile,
    skill_rows,
    verify_package,
    write_package,
)
from importer.client_tables import (
    ITEM_RECORD_SIZE,
    SKILL_RECORD_SIZE,
    ItemRecord,
    ItemTable,
    SkillRecord,
    SkillTable,
    encode_item_table,
    encode_skill_table,
)
from importer.errors import ClientTableError

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "reference" / "WYD Global"
SCHEMA = (ROOT / "schema" / "002_catalog.sql").read_text(encoding="utf-8")


def skill(skill_id: int, skill_point: int = 10) -> SkillRecord:
    return SkillRecord(
        skill_point=skill_point,
        target_type=3,
        mana=15,
        delay=4,
        range=2,
        instance_type=4,
        instance_value=10,
        tick_type=0,
        tick_value=0,
        affect_type=0,
        affect_value=0,
        affect_time=0,
        instance_attribute=b"\x0a\x00\x00\x0a\x00\x00\x00\x00",
        tick_attribute=b"\x0a\x00\x00\x0a\x00\x00\x00\x00",
        tail_values=(4, 0, 1, 13, 0, 3, 0, 1),
        skill_id=skill_id,
        flag=0,
    )


def item(name: str, price: int = 0, effects=((18, 1), (3, 30))) -> ItemRecord:
    return ItemRecord(
        name=name,
        mesh=9,
        texture=0,
        visual_effect=0,
        req_level=134,
        req_str=0,
        req_int=93,
        req_dex=0,
        req_con=0,
        effects=tuple(effects) + ((255, 0),) * (12 - len(effects)),
        price=price,
        unique=0,
        extra=0,
        position=2,
        grade=0,
        extension=bytes(32),
        name_fill=0xFE if name else 0x00,
    )


def write_fake_client(directory: Path, items, skills) -> Path:
    client = directory / "client"
    client.mkdir(parents=True, exist_ok=True)
    (client / "ItemList.bin").write_bytes(encode_item_table(ItemTable(trailer=5, records=tuple(items))))
    (client / "SkillData.bin").write_bytes(encode_skill_table(SkillTable(trailer=7, records=tuple(skills))))
    return client


class ItemRowsTest(unittest.TestCase):
    def test_slots_vazios_nao_viram_item(self) -> None:
        table = ItemTable(trailer=0, records=(item(""), item("Steel_Helmet")))
        rows, effects, warnings = item_rows(table)
        self.assertEqual([row["item_index"] for row in rows], [1])
        self.assertEqual(rows[0]["name"], "Steel_Helmet")
        self.assertEqual(warnings, [])

    def test_sentinela_nao_vira_efeito(self) -> None:
        table = ItemTable(trailer=0, records=(item("A", effects=((18, 1),)),))
        _, effects, _ = item_rows(table)
        self.assertEqual(len(effects), 1)
        self.assertEqual(effects[0], {"item_index": 0, "slot": 0, "effect": 18, "value": 1})

    def test_source_offset_aponta_para_o_registro(self) -> None:
        table = ItemTable(trailer=0, records=(item("A"), item("B"), item("C")))
        rows, _, _ = item_rows(table)
        self.assertEqual(rows[2]["source_offset"], 2 * ITEM_RECORD_SIZE + 4)

    def test_skill_rows_cobrem_todos_os_slots(self) -> None:
        rows = skill_rows(SkillTable(trailer=0, records=(skill(0), skill(7))))
        self.assertEqual([row["slot"] for row in rows], [0, 1])
        self.assertEqual([row["skill_id"] for row in rows], [0, 7])
        self.assertEqual(rows[1]["tail_values"], (4, 0, 1, 13, 0, 3, 0, 1))
        self.assertEqual(rows[1]["source_offset"], SKILL_RECORD_SIZE + 4)


class ReconcileTest(unittest.TestCase):
    def test_tudo_coberto(self) -> None:
        result = reconcile([1, 2, 3], [1, 3])
        self.assertTrue(result["ok"])
        self.assertEqual(result["matched"], 2)
        self.assertEqual(result["missing_total"], 0)

    def test_item_ausente(self) -> None:
        result = reconcile([1, 2], [1, 999])
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing_sample"], [999])

    def test_item_fora_do_int16(self) -> None:
        result = reconcile([1], [40000])
        self.assertFalse(result["ok"])
        self.assertEqual(result["out_of_range_total"], 1)


class PackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = Catalog(
            items=[
                {
                    "item_index": 1,
                    "name": "Transknight",
                    "mesh": 0,
                    "texture": 0,
                    "visual_effect": 0,
                    "req_level": 0,
                    "req_str": 0,
                    "req_int": 0,
                    "req_dex": 0,
                    "req_con": 0,
                    "price": 0,
                    "position": 1,
                    "grade": 0,
                    "unique_id": 0,
                    "extra": 0,
                    "canonical_id": 1,
                    "source_file": "ItemList.bin",
                    "source_offset": 4,
                }
            ],
            effects=[{"item_index": 1, "slot": 0, "effect": 18, "value": 1}],
            skills=skill_rows(SkillTable(trailer=7, records=(skill(1),))),
            skill_sha256="a" * 64,
            item_sha256="b" * 64,
            skill_trailer=7,
            item_trailer=5,
            skill_records=1,
            item_records=1,
        )
        self.report = {
            "run_id": "00000000-0000-0000-0000-000000000001",
            "client_dir": "client",
            "reconciliation": {"checked": True, "ok": True, "missing_total": 0, "out_of_range_total": 0},
        }

    def test_pacote_grava_arquivos_e_sql_idempotente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "catalog"
            checks = write_package(outdir, self.catalog, self.report, ok=True)
            self.assertFalse([c for c in checks if c["status"] == "fail"], checks)
            for name in ("items.csv", "item_effects.csv", "skills.csv", "load_catalog.sql"):
                self.assertTrue((outdir / name).is_file(), name)
            sql = (outdir / "load_catalog.sql").read_text(encoding="utf-8")
            self.assertIn("ON CONFLICT (item_index) DO UPDATE", sql)
            self.assertIn("ON CONFLICT (slot) DO UPDATE", sql)
            self.assertIn("NOT IN (SELECT item_index FROM stage_items)", sql)
            # Troca de skill entre slots nao pode esbarrar no indice unico
            # parcial: os ids sao zerados antes do upsert.
            self.assertIn("SET skill_id = 0", sql)
            self.assertLess(sql.index("SET skill_id = 0"), sql.index("INSERT INTO catalog.skills"))
            self.assertIn("BEGIN;", sql)
            self.assertIn("COMMIT;", sql)
            self.assertIn("catalog.load_runs", sql)
            self.assertNotIn("LOAD_BLOCKED", sql)

    def test_pacote_bloqueado_nao_deixa_sql(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "catalog"
            write_package(outdir, self.catalog, self.report, ok=False)
            self.assertTrue((outdir / "LOAD_BLOCKED.txt").is_file())
            self.assertFalse((outdir / "load_catalog.sql").exists())

    def test_csv_tem_uma_linha_por_registro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "catalog"
            write_package(outdir, self.catalog, self.report, ok=True)
            with (outdir / "items.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "Transknight")

    def test_arquivo_nome_escapado_no_sql(self) -> None:
        report = dict(self.report, client_dir="C:/cliente d'água")
        sql = load_catalog_sql(self.catalog, report)
        self.assertIn("C:/cliente d''água", sql)

    def test_verificacao_pega_efeito_sentinela(self) -> None:
        self.catalog.effects = [{"item_index": 1, "slot": 0, "effect": 255, "value": 0}]
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "catalog"
            checks = verify_package(outdir, self.catalog, self.report, ok=False)
            failed = [c["code"] for c in checks if c["status"] == "fail"]
            self.assertIn("catalog_no_sentinel_effect", failed)


class UsedItemsTest(unittest.TestCase):
    def test_le_item_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "items.csv"
            path.write_text("id,item_index,slot\nx,7,0\ny,9,1\n", encoding="utf-8")
            self.assertEqual(read_used_items(path), [7, 9])

    def test_coluna_ausente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "items.csv"
            path.write_text("id,slot\nx,0\n", encoding="utf-8")
            with self.assertRaises(ClientTableError):
                read_used_items(path)


def schema_columns(table: str) -> list[str]:
    match = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", SCHEMA, re.S)
    if match is None:
        raise AssertionError(f"tabela ausente no schema: {table}")
    columns = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("CONSTRAINT", "PRIMARY", "CHECK", "UNIQUE")):
            continue
        column = re.match(r"([a-z_][a-z0-9_]*)\s+", stripped)
        if column:
            columns.append(column.group(1))
    return columns


class SchemaTest(unittest.TestCase):
    def test_colunas_emitidas_batem_com_o_schema(self) -> None:
        # O contrato entre o emissor e o DDL: as colunas do CSV precisam existir
        # no schema, na mesma ordem. O emissor pode omitir colunas com default
        # (updated_at), mas nunca inventar ou reordenar as demais.
        for table, emitted in (
            ("catalog.items", ITEM_COLUMNS),
            ("catalog.item_effects", EFFECT_COLUMNS),
            ("catalog.skills", SKILL_COLUMNS),
        ):
            with self.subTest(table=table):
                schema = schema_columns(table)
                self.assertTrue(set(emitted) <= set(schema), set(emitted) - set(schema))
                positions = [schema.index(column) for column in emitted]
                self.assertEqual(positions, sorted(positions))

    def test_tabelas_e_views(self) -> None:
        for name in ("catalog.load_runs", "catalog.items", "catalog.item_effects", "catalog.skills"):
            self.assertIn(f"CREATE TABLE {name}", SCHEMA)
        for view in ("catalog.item_usage", "catalog.missing_items", "catalog.out_of_range_items", "catalog.coverage"):
            self.assertIn(f"CREATE VIEW {view}", SCHEMA)

    def test_constraints_principais(self) -> None:
        self.assertIn("CHECK (item_index > 0)", SCHEMA)
        self.assertIn("CHECK (effect BETWEEN 1 AND 254)", SCHEMA)
        self.assertIn("CHECK (slot BETWEEN 0 AND 11)", SCHEMA)
        self.assertIn("CHECK (array_length(tail_values, 1) = 8)", SCHEMA)
        self.assertIn("WHERE skill_id > 0", SCHEMA)

    def test_ordem_de_aplicacao_documentada(self) -> None:
        self.assertLess(SCHEMA.index("001_init.sql"), SCHEMA.index("002_catalog.sql") + 1)


class CliTest(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "importer.catalog", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_dry_run_sem_emit_nao_grava_pacote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = write_fake_client(Path(tmp), [item(""), item("Steel_Helmet", price=70000)], [skill(1)])
            result = self.run_cli("--client", str(client))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("itens      : 1 nomeados", result.stdout)
            self.assertFalse((client / "items.csv").exists())

    def test_emit_grava_pacote_e_reconcilia(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = write_fake_client(Path(tmp), [item(""), item("Steel_Helmet")], [skill(1)])
            used = Path(tmp) / "used.csv"
            used.write_text("id,item_index\nx,1\n", encoding="utf-8")
            outdir = Path(tmp) / "catalog"
            result = self.run_cli(
                "--client", str(client), "--emit", str(outdir), "--used-items", str(used)
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((outdir / "report.json").read_text(encoding="utf-8"))
            self.assertTrue(report["ok"])
            self.assertEqual(report["reconciliation"]["matched"], 1)
            self.assertTrue((outdir / "load_catalog.sql").is_file())

    def test_strict_bloqueia_quando_falta_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = write_fake_client(Path(tmp), [item(""), item("Steel_Helmet")], [skill(1)])
            used = Path(tmp) / "used.csv"
            used.write_text("id,item_index\nx,999\n", encoding="utf-8")
            outdir = Path(tmp) / "catalog"
            result = self.run_cli(
                "--client", str(client), "--emit", str(outdir), "--used-items", str(used), "--strict"
            )
            self.assertEqual(result.returncode, 1)
            self.assertTrue((outdir / "LOAD_BLOCKED.txt").is_file())
            self.assertFalse((outdir / "load_catalog.sql").exists())

    def test_cliente_invalido_falha_alto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli("--client", str(Path(tmp)))
            self.assertEqual(result.returncode, 1)
            self.assertIn("arquivo do cliente ausente", result.stderr)


@unittest.skipUnless(CLIENT.is_dir(), "cliente WYD Global ausente (reference/ nao versionado)")
class ClienteRealTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = build_catalog(CLIENT)

    def test_contagens(self) -> None:
        self.assertEqual(self.catalog.item_records, 14500)
        self.assertEqual(self.catalog.skill_records, 248)
        self.assertEqual(len(self.catalog.items), 4300)
        self.assertEqual(len(self.catalog.skills), 248)
        self.assertEqual(len([row for row in self.catalog.skills if row["skill_id"] > 0]), 152)
        self.assertEqual(self.catalog.item_trailer, 18467)
        self.assertEqual(self.catalog.skill_trailer, 41)

    def test_nomes_e_efeitos(self) -> None:
        first = self.catalog.items[0]
        self.assertEqual(first["item_index"], 1)
        self.assertEqual(first["name"], "Transknight")
        self.assertGreater(len(self.catalog.effects), 10000)
        self.assertTrue(all(row["effect"] != 255 for row in self.catalog.effects))

    def test_run_id_deterministico(self) -> None:
        self.assertEqual(
            catalog_run_id(self.catalog.skill_sha256, self.catalog.item_sha256),
            catalog_run_id(self.catalog.skill_sha256, self.catalog.item_sha256),
        )

    def test_pacote_real_passa_nas_verificacoes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            used = Path(tmp) / "used.csv"
            used.write_text("id,item_index\nx,1\ny,412\n", encoding="utf-8")
            reconciliation = reconcile(
                (row["item_index"] for row in self.catalog.items), read_used_items(used)
            )
            self.assertTrue(reconciliation["ok"])
            report = {
                "run_id": str(catalog_run_id(self.catalog.skill_sha256, self.catalog.item_sha256)),
                "client_dir": str(CLIENT),
                "reconciliation": reconciliation,
            }
            checks = write_package(Path(tmp) / "catalog", self.catalog, report, ok=True)
            failed = [check for check in checks if check["status"] == "fail"]
            self.assertEqual(failed, [])
            self.assertTrue((Path(tmp) / "catalog" / "load_catalog.sql").is_file())


if __name__ == "__main__":
    unittest.main()
