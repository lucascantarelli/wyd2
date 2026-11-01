"""Fixtures sinteticas de STRUCT_ACCOUNTFILE.

Nao sao dados reais: servem para provar offsets, deteccao de tamanho, refino e
contagem. O layout segue importer/layout.py.
"""

from __future__ import annotations

import struct
from pathlib import Path

from importer import layout as L

LOGIN = "TestAccount"
PASSWORD = "Secret123!"
PIN = "123456"


def put_text(
    buf: bytearray,
    offset: int,
    size: int,
    value: str,
    *,
    allow_full: bool = False,
) -> None:
    limit = size if allow_full else size - 1
    raw = value.encode("cp1252", errors="replace")[:limit]
    buf[offset : offset + len(raw)] = raw
    buf[offset + len(raw) : offset + size] = b"\x00" * (size - len(raw))


def put_score(
    buf: bytearray,
    offset: int,
    *,
    level: int,
    ac: int = 0,
    damage: int = 0,
    max_hp: int = 0,
    max_mp: int = 0,
    hp: int = 0,
    mp: int = 0,
    strength: int = 0,
    intelligence: int = 0,
    dexterity: int = 0,
    constitution: int = 0,
    special: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> None:
    struct.pack_into("<i", buf, offset + L.SCORE_LEVEL, level)
    struct.pack_into("<i", buf, offset + L.SCORE_AC, ac)
    struct.pack_into("<i", buf, offset + L.SCORE_DAMAGE, damage)
    struct.pack_into("<i", buf, offset + L.SCORE_MAX_HP, max_hp)
    struct.pack_into("<i", buf, offset + L.SCORE_MAX_MP, max_mp)
    struct.pack_into("<i", buf, offset + L.SCORE_HP, hp)
    struct.pack_into("<i", buf, offset + L.SCORE_MP, mp)
    struct.pack_into("<h", buf, offset + L.SCORE_STR, strength)
    struct.pack_into("<h", buf, offset + L.SCORE_INT, intelligence)
    struct.pack_into("<h", buf, offset + L.SCORE_DEX, dexterity)
    struct.pack_into("<h", buf, offset + L.SCORE_CON, constitution)
    for index, value in enumerate(special):
        struct.pack_into("<h", buf, offset + L.SCORE_SPECIAL + index * 2, value)


def put_item(
    buf: bytearray,
    offset: int,
    index: int,
    effects: tuple[tuple[int, int], ...] = (),
) -> None:
    struct.pack_into("<h", buf, offset + L.ITEM_INDEX, index)
    for slot, (effect_type, value) in enumerate(effects[: L.ITEM_EFFECT_COUNT]):
        buf[offset + L.ITEM_EFFECTS + slot * 2] = effect_type
        buf[offset + L.ITEM_EFFECTS + slot * 2 + 1] = value


def build_account(
    *,
    login: str = LOGIN,
    password: str = PASSWORD,
    pin: str = PIN,
    blocked: bool = True,
) -> bytes:
    buf = bytearray(L.ACCOUNT_SIZE_CURRENT)

    # Info
    put_text(buf, L.INFO_NAME, 16, login)
    put_text(buf, L.INFO_PASSWORD, 12, password)
    put_text(buf, L.INFO_REAL_NAME, 24, "Conta de Teste")
    struct.pack_into("<i", buf, L.INFO_SSN1, 123456789)
    struct.pack_into("<i", buf, L.INFO_SSN2, 987654321)
    put_text(buf, L.INFO_EMAIL, 48, "teste@example.com")
    put_text(buf, L.INFO_TELEPHONE, 16, "5551-1234")
    put_text(buf, L.INFO_ADDRESS, 78, "Rua dos Testes, 42")
    put_text(buf, L.INFO_NUMERIC_TOKEN, 6, pin, allow_full=True)
    struct.pack_into("<i", buf, L.INFO_YEAR, 2024)
    struct.pack_into("<i", buf, L.INFO_YEAR_DAY, 100)

    # Personagem 0: completo, com itens e afetos.
    c0 = L.CHAR_BASE
    put_text(buf, c0 + L.MOB_NAME, 16, "Hero")
    buf[c0 + L.MOB_CLAN] = 1
    buf[c0 + L.MOB_CLASS] = 0
    struct.pack_into("<i", buf, c0 + L.MOB_COIN, 1500)
    struct.pack_into("<q", buf, c0 + L.MOB_EXP, 250_000)
    struct.pack_into("<h", buf, c0 + L.MOB_SPX, 100)
    struct.pack_into("<h", buf, c0 + L.MOB_SPY, 200)
    put_score(
        buf,
        c0 + L.MOB_BASE_SCORE,
        level=50,
        ac=10,
        damage=20,
        max_hp=1000,
        max_mp=500,
        hp=800,
        mp=300,
        strength=30,
        intelligence=10,
        dexterity=20,
        constitution=25,
        special=(1, 2, 3, 4),
    )
    put_score(
        buf,
        c0 + L.MOB_CURRENT_SCORE,
        level=50,
        ac=12,
        damage=25,
        max_hp=1200,
        max_mp=600,
        hp=700,
        mp=250,
        strength=31,
        intelligence=11,
        dexterity=21,
        constitution=26,
        special=(1, 2, 3, 4),
    )
    # Equip 0: +10 com gema 0 (cValue 230); efeitos extras preservados.
    put_item(buf, c0 + L.MOB_EQUIP, 100, ((43, 230), (1, 5), (0, 0)))
    # Equip 1: sem refino.
    put_item(buf, c0 + L.MOB_EQUIP + 1 * L.ITEM_SIZE, 101, ((2, 7),))
    # Carry 0: +5 com pity 1 (cValue 15).
    put_item(buf, c0 + L.MOB_CARRY, 200, ((43, 15),))

    # Personagem 1: minimo.
    c1 = L.CHAR_BASE + L.CHAR_SIZE
    put_text(buf, c1 + L.MOB_NAME, 16, "Mage")
    buf[c1 + L.MOB_CLASS] = 1
    struct.pack_into("<i", buf, c1 + L.MOB_COIN, 500)
    struct.pack_into("<q", buf, c1 + L.MOB_EXP, 1000)
    put_score(buf, c1 + L.MOB_BASE_SCORE, level=10, max_hp=200, max_mp=800)
    put_score(buf, c1 + L.MOB_CURRENT_SCORE, level=10, max_hp=200, max_mp=800, hp=150, mp=700)

    # Cargo: +12 com gema 2 (cValue 240) e um item sem efeito.
    put_item(buf, L.CARGO_OFFSET, 300, ((43, 240),))
    put_item(buf, L.CARGO_OFFSET + 10 * L.ITEM_SIZE, 301)
    struct.pack_into("<i", buf, L.CARGO_GOLD_OFFSET, 500)

    # Resist[4] e char assinado no layout MSVC: -5 testa o sinal.
    buf[c0 + L.MOB_RESIST] = 0xFB

    # ShortSkill do personagem 0.
    buf[L.SHORT_SKILL_OFFSET : L.SHORT_SKILL_OFFSET + 4] = bytes((1, 2, 3, 4))

    # Affect do personagem 0.
    a0 = L.AFFECT_OFFSET
    buf[a0 + L.AFFECT_TYPE] = 1
    buf[a0 + L.AFFECT_VALUE] = 2
    struct.pack_into("<H", buf, a0 + L.AFFECT_LEVEL, 3)
    struct.pack_into("<I", buf, a0 + L.AFFECT_TIME, 100)

    # MobExtra 0. Os offsets absolutos sao 5600 + 51/86/88/90/99; os
    # constantes de layout sao verificados em tests/test_layout.py.
    m0 = L.MOBEXTRA_OFFSET
    struct.pack_into("<h", buf, m0 + L.ME_CLASS_MASTER, 2)
    buf[m0 + L.ME_CITIZEN] = 1
    struct.pack_into("<i", buf, m0 + L.ME_FAME, 100)
    buf[m0 + L.ME_SOUL] = 1
    buf[m0 + L.ME_MORTAL_LEVEL] = 50
    buf[m0 + L.ME_ARCH_CRISTAL] = 4
    struct.pack_into("<h", buf, m0 + L.ME_ARCH_LEVEL, 1)
    struct.pack_into("<h", buf, m0 + L.ME_CELESTIAL_LEVEL, 2)
    struct.pack_into("<h", buf, m0 + L.ME_SUB_CELESTIAL_LEVEL, 3)
    buf[m0 + L.ME_CELESTIAL_RESET] = 1

    # MobExtra 1.
    m1 = L.MOBEXTRA_OFFSET + L.MOBEXTRA_SIZE
    struct.pack_into("<h", buf, m1 + L.ME_CLASS_MASTER, 2)
    buf[m1 + L.ME_MORTAL_LEVEL] = 10

    struct.pack_into("<i", buf, L.DONATE_OFFSET, 7)
    buf[L.IS_BLOCKED_OFFSET] = 1 if blocked else 0

    return bytes(buf)


def write_account(path: Path, **kwargs) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_account(**kwargs))
    return path
