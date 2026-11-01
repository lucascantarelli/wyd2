from __future__ import annotations

import unittest

from importer import layout as L


class LayoutTest(unittest.TestCase):
    def test_blocos_do_arquivo(self) -> None:
        self.assertEqual(L.INFO_SIZE, 216)
        self.assertEqual(L.CHAR_BASE, 216)
        self.assertEqual(L.CHAR_SIZE, 816)
        self.assertEqual(L.CHAR_BASE + 4 * L.CHAR_SIZE, 3480)
        self.assertEqual(L.CARGO_OFFSET, 3480)
        self.assertEqual(L.CARGO_GOLD_OFFSET, 4504)
        self.assertEqual(L.SHORT_SKILL_OFFSET, 4508)
        self.assertEqual(L.AFFECT_OFFSET, 4572)
        self.assertEqual(L.MOBEXTRA_OFFSET, 5600)
        self.assertEqual(L.DONATE_OFFSET, 7808)
        self.assertEqual(L.IS_BLOCKED_OFFSET, 7944)
        self.assertEqual(L.ACCOUNT_SIZE_CURRENT, 7952)

    def test_campos_de_score(self) -> None:
        self.assertEqual(L.SCORE_LEVEL, 0)
        self.assertEqual(L.SCORE_MAX_HP, 16)
        self.assertEqual(L.SCORE_STR, 32)
        self.assertEqual(L.SCORE_SPECIAL, 40)
        self.assertEqual(L.SCORE_SIZE, 48)

    def test_mobextra_natural(self) -> None:
        # Derived from STRUCT_MOBEXTRA: ClassMaster(2)+Citizen(1)+pad(1)+
        # SecLearnedSkill(4)+Fame(4)+Soul(1)+pad(1)+MortalFace(2)=16.
        self.assertEqual(L.ME_QUEST_INFO, 16)
        # Mortal = 5 chars + EMPTY[30] = 35; Arch starts at 16+35 = 51.
        self.assertEqual(L.ME_MORTAL_SLOT, 51)
        self.assertEqual(L.ME_MORTAL_LEVEL, 52)
        self.assertEqual(L.ME_ARCH_CRISTAL, 55)
        # Arch ends at 86; Celestial's shorts start there (86 is even).
        self.assertEqual(L.ME_ARCH_LEVEL, 86)
        self.assertEqual(L.ME_CELESTIAL_LEVEL, 88)
        self.assertEqual(L.ME_SUB_CELESTIAL_LEVEL, 90)
        self.assertEqual(L.ME_CELESTIAL_RESET, 99)
        self.assertEqual(L.MOBEXTRA_SIZE, 552)


if __name__ == "__main__":
    unittest.main()
