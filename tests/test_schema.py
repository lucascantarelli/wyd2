from __future__ import annotations

import re
import unittest
from pathlib import Path

from importer.emit import TABLES, load_sql

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "schema" / "001_init.sql").read_text(encoding="utf-8")


def schema_columns() -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    for match in re.finditer(r"CREATE TABLE (\w+) \((.*?)\n\);", SCHEMA, re.S):
        name, body = match.group(1), match.group(2)
        columns = []
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("CONSTRAINT", "PRIMARY", "CHECK", "UNIQUE")):
                continue
            column = re.match(r"([a-z_][a-z0-9_]*)\s+", stripped)
            if column:
                columns.append(column.group(1))
        tables[name] = columns
    return tables


class SchemaTest(unittest.TestCase):
    def test_colunas_batem_com_o_emissor(self) -> None:
        tables = schema_columns()
        for spec in TABLES:
            with self.subTest(table=spec.name):
                self.assertIn(spec.name, tables)
                schema = tables[spec.name]
                emitted = list(spec.columns)
                # O emissor pode omitir colunas com default/identity (id,
                # created_at), mas nunca inventar ou reordenar as demais.
                self.assertTrue(set(emitted) <= set(schema), set(emitted) - set(schema))
                positions = [schema.index(column) for column in emitted]
                self.assertEqual(positions, sorted(positions))

    def test_load_sql_usa_as_mesmas_colunas(self) -> None:
        sql = load_sql({"run_id": "00000000-0000-0000-0000-000000000001"})
        for spec in TABLES:
            columns = ", ".join(spec.columns)
            self.assertIn(f"stage_{spec.name} ({columns})", sql)
            self.assertIn(f"INSERT INTO wyd.{spec.name} ({columns})", sql)

        # id identity nao e copiado por LIKE; o staging precisa aceitar NULL.
        self.assertIn(
            "ALTER TABLE stage_item_ledger ALTER COLUMN id DROP NOT NULL;", sql
        )
        self.assertIn(
            "ALTER TABLE stage_import_issues ALTER COLUMN id DROP NOT NULL;", sql
        )

    def test_ledger_e_append_only(self) -> None:
        self.assertIn("CREATE TRIGGER item_ledger_no_update", SCHEMA)
        self.assertIn("CREATE TRIGGER item_ledger_no_delete", SCHEMA)
        self.assertIn("CREATE TRIGGER item_ledger_no_truncate", SCHEMA)

    def test_item_tem_uuid_e_um_dono(self) -> None:
        self.assertIn("id                  uuid PRIMARY KEY", SCHEMA)
        self.assertIn("items_owner_exactly_one", SCHEMA)
        self.assertIn("items_character_slot_uq", SCHEMA)


if __name__ == "__main__":
    unittest.main()
