"""Leitura binaria das structs legadas.

Layout: alinhamento natural MSVC x86 (little-endian), NAO pack(1).
Ver importer/layout.py e docs/03-DADOS-LEGADOS.md.
"""

from __future__ import annotations

import hashlib
import struct

from . import layout as L
from .errors import DecodeError, TruncatedAccount, UnsupportedAccountSize
from .model import (
    AccountFile,
    AccountInfo,
    Affect,
    Character,
    Item,
    ItemEffect,
    MobExtra,
    Score,
)
from .refine import decode_sanc_value, find_sanc_value


def _need(data: bytes, offset: int, size: int) -> None:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise DecodeError(f"bytes insuficientes: offset={offset} size={size} total={len(data)}")


def _u8(data: bytes, offset: int) -> int:
    _need(data, offset, 1)
    return data[offset]


def _i8(data: bytes, offset: int) -> int:
    _need(data, offset, 1)
    return struct.unpack_from("<b", data, offset)[0]


def _u16(data: bytes, offset: int) -> int:
    _need(data, offset, 2)
    return struct.unpack_from("<H", data, offset)[0]


def _i16(data: bytes, offset: int) -> int:
    _need(data, offset, 2)
    return struct.unpack_from("<h", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    _need(data, offset, 4)
    return struct.unpack_from("<I", data, offset)[0]


def _i32(data: bytes, offset: int) -> int:
    _need(data, offset, 4)
    return struct.unpack_from("<i", data, offset)[0]


def _i64(data: bytes, offset: int) -> int:
    _need(data, offset, 8)
    return struct.unpack_from("<q", data, offset)[0]


def text_at(data: bytes, offset: int, size: int) -> str:
    """Le uma string C de tamanho fixo, cortando no primeiro NUL.

    O legado usa cp1252 (Latin-1 do Windows). Bytes indefinidos de cp1252 caem
    para latin-1, que aceita todos os 256 valores.
    """
    _need(data, offset, size)
    raw = data[offset : offset + size].split(b"\x00", 1)[0]
    try:
        return raw.decode("cp1252")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def decode_score(data: bytes, offset: int) -> Score:
    _need(data, offset, L.SCORE_SIZE)
    return Score(
        level=_i32(data, offset + L.SCORE_LEVEL),
        ac=_i32(data, offset + L.SCORE_AC),
        damage=_i32(data, offset + L.SCORE_DAMAGE),
        merchant=_u8(data, offset + L.SCORE_MERCHANT),
        attack_run=_u8(data, offset + L.SCORE_ATTACK_RUN),
        direction=_u8(data, offset + L.SCORE_DIRECTION),
        chaos_rate=_u8(data, offset + L.SCORE_CHAOS_RATE),
        max_hp=_i32(data, offset + L.SCORE_MAX_HP),
        max_mp=_i32(data, offset + L.SCORE_MAX_MP),
        hp=_i32(data, offset + L.SCORE_HP),
        mp=_i32(data, offset + L.SCORE_MP),
        strength=_i16(data, offset + L.SCORE_STR),
        intelligence=_i16(data, offset + L.SCORE_INT),
        dexterity=_i16(data, offset + L.SCORE_DEX),
        constitution=_i16(data, offset + L.SCORE_CON),
        special=(
            _i16(data, offset + L.SCORE_SPECIAL),
            _i16(data, offset + L.SCORE_SPECIAL + 2),
            _i16(data, offset + L.SCORE_SPECIAL + 4),
            _i16(data, offset + L.SCORE_SPECIAL + 6),
        ),
    )


def decode_item(data: bytes, offset: int, container: str, slot: int) -> Item | None:
    _need(data, offset, L.ITEM_SIZE)
    index = _i16(data, offset + L.ITEM_INDEX)
    if index <= 0:
        return None

    effects = tuple(
        ItemEffect(
            type=_u8(data, offset + L.ITEM_EFFECTS + i * L.ITEM_EFFECT_SIZE),
            value=_u8(data, offset + L.ITEM_EFFECTS + i * L.ITEM_EFFECT_SIZE + 1),
        )
        for i in range(L.ITEM_EFFECT_COUNT)
    )
    refine, gem, pity = decode_sanc_value(find_sanc_value(effects))
    return Item(
        container=container,
        slot=slot,
        item_index=index,
        refine=refine,
        gem=gem,
        pity=pity,
        effects=effects,
    )


def decode_mobextra(data: bytes, offset: int) -> MobExtra:
    _need(data, offset, L.MOBEXTRA_SIZE)
    return MobExtra(
        class_master=_i16(data, offset + L.ME_CLASS_MASTER),
        citizen=_u8(data, offset + L.ME_CITIZEN),
        fame=_i32(data, offset + L.ME_FAME),
        soul=_u8(data, offset + L.ME_SOUL),
        mortal_face=_i16(data, offset + L.ME_MORTAL_FACE),
        mortal_level=_u8(data, offset + L.ME_MORTAL_LEVEL),
        arch_level=_i16(data, offset + L.ME_ARCH_LEVEL),
        celestial_level=_i16(data, offset + L.ME_CELESTIAL_LEVEL),
        sub_celestial_level=_i16(data, offset + L.ME_SUB_CELESTIAL_LEVEL),
        celestial_reset=_u8(data, offset + L.ME_CELESTIAL_RESET),
        arch_cristal=_u8(data, offset + L.ME_ARCH_CRISTAL),
        level355=_u8(data, offset + L.ME_LEVEL355),
        level370=_u8(data, offset + L.ME_LEVEL370),
        lv40=_u8(data, offset + L.ME_LV40),
        lv90=_u8(data, offset + L.ME_LV90),
        raw=data[offset : offset + L.MOBEXTRA_SIZE],
    )


def decode_affects(data: bytes, char_slot: int) -> tuple[Affect, ...]:
    base = L.AFFECT_OFFSET + char_slot * L.AFFECT_PER_CHAR * L.AFFECT_SIZE
    affects = []
    for slot in range(L.AFFECT_PER_CHAR):
        offset = base + slot * L.AFFECT_SIZE
        affect_type = _u8(data, offset + L.AFFECT_TYPE)
        if affect_type == 0:
            continue
        affects.append(
            Affect(
                slot=slot,
                type=affect_type,
                value=_u8(data, offset + L.AFFECT_VALUE),
                level=_u16(data, offset + L.AFFECT_LEVEL),
                time_value=_u32(data, offset + L.AFFECT_TIME),
            )
        )
    return tuple(affects)


def decode_mob(data: bytes, offset: int, slot: int, short_skills: tuple[int, ...]) -> Character:
    _need(data, offset, L.CHAR_SIZE)

    equip = tuple(
        item
        for i in range(L.EQUIP_COUNT)
        if (item := decode_item(data, offset + L.MOB_EQUIP + i * L.ITEM_SIZE, "equip", i))
    )
    carry = tuple(
        item
        for i in range(L.CARRY_COUNT)
        if (item := decode_item(data, offset + L.MOB_CARRY + i * L.ITEM_SIZE, "carry", i))
    )

    return Character(
        slot=slot,
        name=text_at(data, offset + L.MOB_NAME, 16),
        clan=_u8(data, offset + L.MOB_CLAN),
        merchant=_u8(data, offset + L.MOB_MERCHANT),
        guild=_u16(data, offset + L.MOB_GUILD),
        char_class=_u8(data, offset + L.MOB_CLASS),
        rsv=_u16(data, offset + L.MOB_RSV),
        quest=_u8(data, offset + L.MOB_QUEST),
        coin=_i32(data, offset + L.MOB_COIN),
        exp=_i64(data, offset + L.MOB_EXP),
        spx=_i16(data, offset + L.MOB_SPX),
        spy=_i16(data, offset + L.MOB_SPY),
        base=decode_score(data, offset + L.MOB_BASE_SCORE),
        current=decode_score(data, offset + L.MOB_CURRENT_SCORE),
        equip=equip,
        carry=carry,
        affects=decode_affects(data, slot),
        learned_skill=_u32(data, offset + L.MOB_LEARNED_SKILL),
        magic=_u32(data, offset + L.MOB_MAGIC),
        score_bonus=_u16(data, offset + L.MOB_SCORE_BONUS),
        special_bonus=_u16(data, offset + L.MOB_SPECIAL_BONUS),
        skill_bonus=_u16(data, offset + L.MOB_SKILL_BONUS),
        critical=_u8(data, offset + L.MOB_CRITICAL),
        save_mana=_u8(data, offset + L.MOB_SAVE_MANA),
        skill_bar=tuple(_u8(data, offset + L.MOB_SKILL_BAR + i) for i in range(4)),
        short_skills=short_skills,
        guild_level=_u8(data, offset + L.MOB_GUILD_LEVEL),
        regen_hp=_u16(data, offset + L.MOB_REGEN_HP),
        regen_mp=_u16(data, offset + L.MOB_REGEN_MP),
        # STRUCT_MOB.Resist e char (signed no MSVC); resistencia negativa e
        # um valor valido e nao pode virar 246.
        resist=tuple(_i8(data, offset + L.MOB_RESIST + i) for i in range(4)),
        extra=decode_mobextra(data, L.MOBEXTRA_OFFSET + slot * L.MOBEXTRA_SIZE),
    )


def decode_account(
    data: bytes,
    path: str,
    *,
    allow_padded_legacy: bool = False,
) -> AccountFile:
    """Decodifica um STRUCT_ACCOUNTFILE.

    O layout verificado e o de 7952 bytes. Arquivos de 7500..7600 sao aceitos
    apenas com `allow_padded_legacy`: eles sao zero-padded ate 7952, como o
    DBSrv antigo faz (`CRanking.cpp`), e recebem um aviso de que campos apos o
    corte (Donate, IsBlocked, parte de mobExtra) podem estar zerados.

    4294 continua recusado: o layout de ACCOUNTINFO e diferente e nao ha
    amostra verificada para mapear os offsets.
    """
    raw = data
    size = len(raw)
    version = L.detect_version(size)
    if version is None:
        raise DecodeError(f"tamanho de arquivo desconhecido: {size} bytes")
    padding = 0
    if version == L.VERSION_INTERMEDIATE:
        if not allow_padded_legacy:
            raise UnsupportedAccountSize(size)
        padding = L.ACCOUNT_SIZE_CURRENT - size
        data = raw + bytes(padding)
        version = L.VERSION_INTERMEDIATE_PADDED
    elif version != L.VERSION_CURRENT:
        raise UnsupportedAccountSize(size)
    if len(data) < L.ACCOUNT_SIZE_CURRENT:
        raise TruncatedAccount(f"arquivo truncado: {len(data)} < {L.ACCOUNT_SIZE_CURRENT}")

    info = AccountInfo(
        name=text_at(data, L.INFO_NAME, 16),
        password=text_at(data, L.INFO_PASSWORD, 12),
        real_name=text_at(data, L.INFO_REAL_NAME, 24),
        ssn1=_i32(data, L.INFO_SSN1),
        ssn2=_i32(data, L.INFO_SSN2),
        email=text_at(data, L.INFO_EMAIL, 48),
        telephone=text_at(data, L.INFO_TELEPHONE, 16),
        address=text_at(data, L.INFO_ADDRESS, 78),
        numeric_token=text_at(data, L.INFO_NUMERIC_TOKEN, 6),
        year=_i32(data, L.INFO_YEAR),
        year_day=_i32(data, L.INFO_YEAR_DAY),
    )

    characters = []
    for slot in range(L.CHAR_COUNT):
        offset = L.CHAR_BASE + slot * L.CHAR_SIZE
        name = text_at(data, offset + L.MOB_NAME, 16)
        block = data[offset : offset + L.CHAR_SIZE]
        if not name and block.strip(b"\x00") == b"":
            continue
        short_skills = tuple(
            _u8(data, L.SHORT_SKILL_OFFSET + slot * L.SHORT_SKILL_PER_CHAR + i)
            for i in range(L.SHORT_SKILL_PER_CHAR)
        )
        characters.append(decode_mob(data, offset, slot, short_skills))

    cargo = tuple(
        item
        for i in range(L.CARGO_COUNT)
        if (item := decode_item(data, L.CARGO_OFFSET + i * L.ITEM_SIZE, "cargo", i))
    )

    return AccountFile(
        path=path,
        size=size,
        version=version,
        sha256=hashlib.sha256(raw).hexdigest(),
        info=info,
        characters=tuple(characters),
        cargo=cargo,
        cargo_gold=_i32(data, L.CARGO_GOLD_OFFSET),
        donate=_i32(data, L.DONATE_OFFSET),
        is_blocked=data[L.IS_BLOCKED_OFFSET] != 0,
        padding_bytes=padding,
    )
