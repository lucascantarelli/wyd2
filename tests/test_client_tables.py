from __future__ import annotations

import unittest
from pathlib import Path

from importer.client_tables import (
    ITEM_RECORD_SIZE,
    NAME_LENGTH,
    SKILL_RECORD_SIZE,
    ItemRecord,
    ItemTable,
    SkillRecord,
    SkillTable,
    encode_item_table,
    encode_skill_table,
    parse_item_table,
    parse_skill_table,
    xor_bytes,
)
from importer.errors import ClientTableError

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "reference" / "WYD Global"


def make_skill(skill_id: int, skill_point: int = 10, flag: int = 0) -> SkillRecord:
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
        flag=flag,
    )


def make_item(name: str, price: int = 0, position: int = 0) -> ItemRecord:
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
        effects=((18, 1), (3, 30)) + ((255, 0),) * 10,
        price=price,
        unique=0,
        extra=0,
        position=position,
        grade=0,
        extension=bytes(ITEM_RECORD_SIZE - 140),
        name_fill=0xFE if name else 0x00,
    )


class XorTest(unittest.TestCase):
    def test_xor_e_simetrico(self) -> None:
        data = bytes(range(64))
        self.assertEqual(xor_bytes(xor_bytes(data)), data)

    def test_xor_muda_os_bytes(self) -> None:
        self.assertNotEqual(xor_bytes(bytes(8)), bytes(8))


class SkillTableTest(unittest.TestCase):
    def test_round_trip_sintetico(self) -> None:
        table = SkillTable(trailer=41, records=(make_skill(1), make_skill(2, skill_point=48, flag=1)))
        raw = encode_skill_table(table)
        self.assertEqual(len(raw), 2 * SKILL_RECORD_SIZE + 4)
        self.assertEqual(parse_skill_table(raw), table)

    def test_campos_sobrevivem_ao_round_trip(self) -> None:
        table = SkillTable(trailer=7, records=(make_skill(99, skill_point=350),))
        record = parse_skill_table(encode_skill_table(table)).records[0]
        self.assertEqual(record.skill_point, 350)
        self.assertEqual(record.skill_id, 99)
        self.assertEqual(record.instance_attribute, b"\x0a\x00\x00\x0a\x00\x00\x00\x00")
        self.assertEqual(record.tail_values, (4, 0, 1, 13, 0, 3, 0, 1))

    def test_payload_de_tamanho_invalido(self) -> None:
        with self.assertRaises(ClientTableError):
            parse_skill_table(b"\x00" * (SKILL_RECORD_SIZE + 3))

    def test_arquivo_curto(self) -> None:
        with self.assertRaises(ClientTableError):
            parse_skill_table(b"\x00" * 8)


class ItemTableTest(unittest.TestCase):
    def test_round_trip_sintetico(self) -> None:
        table = ItemTable(
            trailer=18467,
            records=(make_item(""), make_item("Steel_Helmet", price=70000, position=2)),
        )
        raw = encode_item_table(table)
        self.assertEqual(len(raw), 2 * ITEM_RECORD_SIZE + 4)
        self.assertEqual(parse_item_table(raw), table)

    def test_mesh_negativo_sobrevive(self) -> None:
        # 0xFFFF no arquivo e mesh -1, nao 65535: o campo e assinado.
        record = make_item("Sem_Mesh")
        object.__setattr__(record, "mesh", -1)
        table = ItemTable(trailer=0, records=(record,))
        parsed = parse_item_table(encode_item_table(table)).records[0]
        self.assertEqual(parsed.mesh, -1)
        self.assertEqual(encode_item_table(table), encode_item_table(ItemTable(trailer=0, records=(parsed,))))

    def test_nome_longo_demais(self) -> None:
        with self.assertRaises(ClientTableError):
            encode_item_table(ItemTable(trailer=0, records=(make_item("X" * NAME_LENGTH),)))

    def test_vazio_nao_tem_nome(self) -> None:
        record = parse_item_table(encode_item_table(ItemTable(trailer=0, records=(make_item(""),)))).records[0]
        self.assertTrue(record.is_empty)
        self.assertEqual(record.name_fill, 0x00)


@unittest.skipUnless(CLIENT.is_dir(), "cliente WYD Global ausente (reference/ nao versionado)")
class ClienteRealTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_skill = (CLIENT / "SkillData.bin").read_bytes()
        cls.raw_item = (CLIENT / "ItemList.bin").read_bytes()
        cls.skill = parse_skill_table(cls.raw_skill)
        cls.item = parse_item_table(cls.raw_item)

    def test_skill_contagem_e_trailer(self) -> None:
        self.assertEqual(len(self.skill.records), 248)
        self.assertEqual(self.skill.trailer, 41)

    def test_skill_round_trip_exato(self) -> None:
        self.assertEqual(encode_skill_table(self.skill), self.raw_skill)

    def test_skill_ids_dentro_do_array(self) -> None:
        ids = [record.skill_id for record in self.skill.records]
        self.assertEqual(min(ids), 0)
        self.assertLessEqual(max(ids), len(self.skill.records))
        self.assertTrue(all(value in (0, 1) for value in (record.flag for record in self.skill.records)))

    def test_item_contagem_e_trailer(self) -> None:
        self.assertEqual(len(self.item.records), 14500)
        self.assertEqual(self.item.trailer, 18467)

    def test_item_round_trip_exato(self) -> None:
        self.assertEqual(encode_item_table(self.item), self.raw_item)

    def test_item_nomes_e_preenchimento(self) -> None:
        records = self.item.records
        self.assertEqual(records[1].name, "Transknight")
        usados = [record for record in records if not record.is_empty]
        self.assertEqual(len(usados), 4300)
        self.assertTrue(all(record.name_fill == 0xFE for record in usados))
        self.assertTrue(all(record.name_fill == 0x00 for record in records if record.is_empty))

    def test_item_campos_verificados(self) -> None:
        helmet = self.item.records[100]
        self.assertEqual(helmet.name, "Steel_Helmet")
        self.assertEqual(helmet.price, 70000)
        self.assertEqual(helmet.position, 2)
        self.assertEqual(helmet.req_level, 134)
        circle = self.item.records[448]
        self.assertEqual(circle.name, "Pure_Divine_Circle")
        self.assertEqual(circle.position, 8192)
        self.assertEqual(min(record.mesh for record in self.item.records), -1)
        self.assertEqual(max(record.position for record in self.item.records), 32768)

    def test_item_id_canonico(self) -> None:
        records = self.item.records
        self.assertEqual(records[1].canonical_id, 1)
        self.assertEqual(records[2452].canonical_id, 2451)
        self.assertEqual(records[2452].name, records[2451].name)
        self.assertTrue(all(record.canonical_id < len(records) for record in records if not record.is_empty))


if __name__ == "__main__":
    unittest.main()
