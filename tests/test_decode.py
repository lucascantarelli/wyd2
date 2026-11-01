from __future__ import annotations

import hashlib
import unittest

from importer import layout as L
from importer.decode import decode_account
from importer.errors import DecodeError, UnsupportedAccountSize
from tests.fixtures import LOGIN, PASSWORD, PIN, build_account


class DecodeAccountTest(unittest.TestCase):
    def setUp(self) -> None:
        self.account = decode_account(build_account(), "fixture")

    def test_header_e_tamanho(self) -> None:
        self.assertEqual(self.account.size, 7952)
        self.assertEqual(self.account.version, L.VERSION_CURRENT)
        self.assertEqual(self.account.info.name, LOGIN)
        self.assertEqual(self.account.info.password, PASSWORD)
        self.assertEqual(self.account.info.numeric_token, PIN)
        self.assertEqual(self.account.info.email, "teste@example.com")
        self.assertTrue(self.account.is_blocked)

    def test_personagens(self) -> None:
        self.assertEqual(len(self.account.characters), 2)
        hero, mage = self.account.characters
        self.assertEqual(hero.name, "Hero")
        self.assertEqual(hero.char_class, 0)
        self.assertEqual(hero.base.level, 50)
        self.assertEqual(hero.exp, 250_000)
        self.assertEqual(hero.coin, 1500)
        self.assertEqual(hero.current.max_hp, 1200)
        self.assertEqual(hero.current.special, (1, 2, 3, 4))
        self.assertEqual(hero.resist, (-5, 0, 0, 0))
        self.assertEqual(hero.short_skills[:4], (1, 2, 3, 4))
        self.assertEqual(len(hero.affects), 1)
        self.assertEqual(hero.affects[0].type, 1)
        self.assertEqual(hero.affects[0].time_value, 100)
        self.assertEqual(hero.extra.class_master, 2)
        self.assertEqual(hero.extra.mortal_level, 50)
        self.assertEqual(hero.extra.arch_level, 1)
        self.assertEqual(hero.extra.celestial_level, 2)
        self.assertEqual(hero.extra.celestial_reset, 1)
        self.assertEqual(len(hero.extra.raw), L.MOBEXTRA_SIZE)
        self.assertEqual(mage.name, "Mage")
        self.assertEqual(mage.extra.mortal_level, 10)

    def test_itens_e_refino(self) -> None:
        hero = self.account.characters[0]
        self.assertEqual(len(hero.equip), 2)
        self.assertEqual(len(hero.carry), 1)
        self.assertEqual(hero.equip[0].item_index, 100)
        self.assertEqual(hero.equip[0].refine, 10)
        self.assertEqual(hero.equip[0].gem, 0)
        self.assertEqual(hero.equip[0].pity, 0)
        self.assertEqual(hero.equip[1].item_index, 101)
        self.assertEqual(hero.equip[1].refine, 0)
        self.assertIsNone(hero.equip[1].gem)
        self.assertEqual(hero.carry[0].refine, 5)
        self.assertEqual(hero.carry[0].pity, 1)

        self.assertEqual(len(self.account.cargo), 2)
        self.assertEqual(self.account.cargo[0].item_index, 300)
        self.assertEqual(self.account.cargo[0].refine, 12)
        self.assertEqual(self.account.cargo[0].gem, 2)
        self.assertEqual(self.account.cargo[0].slot, 0)
        self.assertEqual(self.account.cargo[1].slot, 10)
        self.assertEqual(self.account.cargo_gold, 500)
        self.assertEqual(self.account.donate, 7)

    def test_conta_vazia_decodifica(self) -> None:
        account = decode_account(bytes(7952), "vazia")
        self.assertEqual(account.characters, ())
        self.assertEqual(account.cargo, ())
        self.assertEqual(account.cargo_gold, 0)
        self.assertFalse(account.is_blocked)

    def test_tamanhos_nao_suportados(self) -> None:
        with self.assertRaises(UnsupportedAccountSize):
            decode_account(bytes(4294), "antiga")
        with self.assertRaises(UnsupportedAccountSize):
            decode_account(bytes(7600), "intermediaria")
        with self.assertRaises(UnsupportedAccountSize):
            decode_account(bytes(4294), "antiga", allow_padded_legacy=True)
        with self.assertRaises(DecodeError):
            decode_account(bytes(7951), "truncada")
        with self.assertRaises(DecodeError):
            decode_account(bytes(7953), "maior")

    def test_intermediario_zero_padded(self) -> None:
        raw = build_account()[:7600]
        account = decode_account(raw, "intermediaria", allow_padded_legacy=True)
        self.assertEqual(account.size, 7600)
        self.assertEqual(account.version, L.VERSION_INTERMEDIATE_PADDED)
        self.assertEqual(account.padding_bytes, 352)
        self.assertEqual(account.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(account.info.name, LOGIN)
        self.assertEqual(len(account.characters), 2)
        self.assertEqual(account.characters[0].extra.arch_level, 1)
        self.assertEqual(account.characters[0].extra.celestial_level, 2)
        self.assertEqual(len(account.cargo), 2)
        self.assertEqual(len(account.characters[0].affects), 1)
        # O corte em 7600 perde Donate/IsBlocked; ambos ficam zerados.
        self.assertEqual(account.donate, 0)
        self.assertFalse(account.is_blocked)
        self.assertEqual(len(account.characters[0].extra.raw), L.MOBEXTRA_SIZE)


if __name__ == "__main__":
    unittest.main()
