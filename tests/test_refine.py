from __future__ import annotations

import unittest

from importer import ids
from importer.model import ItemEffect
from importer.refine import decode_sanc_value, find_sanc_value, is_valid_refine


class RefineTest(unittest.TestCase):
    def test_niveis_baixos_com_pity(self) -> None:
        self.assertEqual(decode_sanc_value(None), (0, None, 0))
        self.assertEqual(decode_sanc_value(0), (0, None, 0))
        self.assertEqual(decode_sanc_value(9), (9, None, 0))
        self.assertEqual(decode_sanc_value(15), (5, None, 1))
        self.assertEqual(decode_sanc_value(229), (9, None, 22))

    def test_niveis_altos_com_gema(self) -> None:
        self.assertEqual(decode_sanc_value(230), (10, 0, 0))
        self.assertEqual(decode_sanc_value(240), (12, 2, 0))
        self.assertEqual(decode_sanc_value(253), (15, 3, 0))

    def test_busca_do_efeito(self) -> None:
        effects = (
            ItemEffect(1, 5),
            ItemEffect(43, 230),
            ItemEffect(2, 7),
        )
        self.assertEqual(find_sanc_value(effects), 230)
        self.assertEqual(find_sanc_value((ItemEffect(116, 12),)), 12)
        self.assertIsNone(find_sanc_value((ItemEffect(1, 5),)))

    def test_faixa(self) -> None:
        self.assertTrue(is_valid_refine(0, 0))
        self.assertTrue(is_valid_refine(15, 0))
        self.assertFalse(is_valid_refine(16, 0))
        self.assertFalse(is_valid_refine(0, 21))


class IdsTest(unittest.TestCase):
    def test_login_canonico(self) -> None:
        self.assertEqual(ids.account_id("TestAccount"), ids.account_id(" testaccount "))

    def test_ids_estaveis(self) -> None:
        self.assertEqual(
            str(ids.item_id("TestAccount", 0, "equip", 3)),
            str(ids.item_id(" testaccount ", 0, "equip", 3)),
        )
        self.assertNotEqual(
            ids.item_id("TestAccount", 0, "equip", 3),
            ids.item_id("TestAccount", 0, "carry", 3),
        )
        self.assertNotEqual(
            ids.item_id("TestAccount", 0, "equip", 3),
            ids.item_id("TestAccount", 1, "equip", 3),
        )


if __name__ == "__main__":
    unittest.main()
