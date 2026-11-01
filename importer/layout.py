"""Offsets e tamanhos das structs legadas.

Fonte: docs/03-DADOS-LEGADOS.md, derivado de Basedef.h (alinhamento natural
MSVC x86). Todos os offsets sao absolutos dentro do arquivo de conta, exceto
quando indicado como relativo a uma sub-struct.

Nao alterar sem atualizar docs/03-DADOS-LEGADOS.md e os testes de fixture.
"""

from __future__ import annotations

ACCOUNT_SIZE_CURRENT = 7952
ACCOUNT_SIZE_LEGACY_4294 = 4294
ACCOUNT_SIZE_INTERMEDIATE_MIN = 7500
ACCOUNT_SIZE_INTERMEDIATE_MAX = 7600

# --- STRUCT_ACCOUNTINFO (216 bytes) ---------------------------------------
INFO_OFFSET = 0
INFO_NAME = 0
INFO_PASSWORD = 16
INFO_REAL_NAME = 28
INFO_SSN1 = 52
INFO_SSN2 = 56
INFO_EMAIL = 60
INFO_TELEPHONE = 108
INFO_ADDRESS = 124
INFO_NUMERIC_TOKEN = 202
INFO_YEAR = 208
INFO_YEAR_DAY = 212
INFO_SIZE = 216

# --- STRUCT_MOB[4] ---------------------------------------------------------
CHAR_BASE = 216
CHAR_SIZE = 816
CHAR_COUNT = 4

MOB_NAME = 0
MOB_CLAN = 16
MOB_MERCHANT = 17
MOB_GUILD = 18
MOB_CLASS = 20
MOB_RSV = 22
MOB_QUEST = 24
MOB_COIN = 28
MOB_EXP = 32
MOB_SPX = 40
MOB_SPY = 42
MOB_BASE_SCORE = 44
MOB_CURRENT_SCORE = 92
MOB_EQUIP = 140
MOB_CARRY = 268
MOB_LEARNED_SKILL = 780
MOB_MAGIC = 784
MOB_SCORE_BONUS = 788
MOB_SPECIAL_BONUS = 790
MOB_SKILL_BONUS = 792
MOB_CRITICAL = 794
MOB_SAVE_MANA = 795
MOB_SKILL_BAR = 796
MOB_GUILD_LEVEL = 800
MOB_REGEN_HP = 802
MOB_REGEN_MP = 804
MOB_RESIST = 806
MOB_PADDING_END = 810

EQUIP_COUNT = 16
CARRY_COUNT = 64

# --- STRUCT_SCORE (48 bytes, relativo) ------------------------------------
SCORE_LEVEL = 0
SCORE_AC = 4
SCORE_DAMAGE = 8
SCORE_MERCHANT = 12
SCORE_ATTACK_RUN = 13
SCORE_DIRECTION = 14
SCORE_CHAOS_RATE = 15
SCORE_MAX_HP = 16
SCORE_MAX_MP = 20
SCORE_HP = 24
SCORE_MP = 28
SCORE_STR = 32
SCORE_INT = 34
SCORE_DEX = 36
SCORE_CON = 38
SCORE_SPECIAL = 40
SCORE_SIZE = 48

# --- STRUCT_ITEM (8 bytes, relativo) --------------------------------------
ITEM_SIZE = 8
ITEM_INDEX = 0
ITEM_EFFECTS = 2
ITEM_EFFECT_COUNT = 3
ITEM_EFFECT_SIZE = 2

# --- STRUCT_MOBEXTRA (552 bytes) ------------------------------------------
MOBEXTRA_SIZE = 552
ME_CLASS_MASTER = 0       # short
ME_CITIZEN = 2            # char
ME_FAME = 8               # int  (pad apos Citizen + long SecLearnedSkill)
ME_SOUL = 12              # char
ME_MORTAL_FACE = 14       # short
ME_QUEST_INFO = 16        # struct aninhado, 146 bytes (145 + pad para align 2)

# QuestInfo.Arch: QuestInfo(16) + Mortal(35) = 51.
# Mortal = 5 chars + EMPTY[30], alinhamento 1: nao ha padding antes de Arch.
ME_MORTAL_SLOT = 51
ME_MORTAL_LEVEL = 52
ME_LEVEL355 = 53
ME_LEVEL370 = 54
ME_ARCH_CRISTAL = 55

# QuestInfo.Celestial: 16 + 35 + 35 = 86. Os shorts exigem align 2 (86 e par).
# 86 + 3 shorts (6) + 8 chars + EMPTY[30] = 130; Circle em 130; EMPTY[30] ate 160;
# QuestInfo fecha em 162 (145 uteis + 1 de padding para align 2).
ME_ARCH_LEVEL = 86        # short
ME_CELESTIAL_LEVEL = 88   # short
ME_SUB_CELESTIAL_LEVEL = 90
ME_LV40 = 92
ME_LV90 = 93
ME_ADD120 = 94
ME_ADD150 = 95
ME_ADD180 = 96
ME_ADD200 = 97
ME_ARCANA = 98
ME_CELESTIAL_RESET = 99

# --- STRUCT_AFFECT (8 bytes) ---------------------------------------------
AFFECT_SIZE = 8
AFFECT_TYPE = 0           # unsigned char
AFFECT_VALUE = 1          # unsigned char
AFFECT_LEVEL = 2          # unsigned short
AFFECT_TIME = 4           # unsigned int
AFFECT_PER_CHAR = 32

# --- Tail do STRUCT_ACCOUNTFILE -------------------------------------------
CARGO_OFFSET = 3480
CARGO_COUNT = 128
CARGO_GOLD_OFFSET = 4504
SHORT_SKILL_OFFSET = 4508
SHORT_SKILL_PER_CHAR = 16
AFFECT_OFFSET = 4572
MOBEXTRA_OFFSET = 5600
DONATE_OFFSET = 7808
TEMP_KEY_OFFSET = 7812
RECEIVED_ITEM_OFFSET = 7864
# Derivado do alinhamento natural: 7872 + 56 (QUEST) + 16 (BlockPass) = 7944.
# O total 7952 fecha com 7 bytes de padding final.
IS_BLOCKED_OFFSET = 7944

# --- Versoes reconhecidas -------------------------------------------------
VERSION_CURRENT = "current_7952"
VERSION_LEGACY_4294 = "legacy_4294"
VERSION_INTERMEDIATE = "intermediate_7500_7600"
VERSION_INTERMEDIATE_PADDED = "intermediate_7500_7600_padded"


def detect_version(size: int) -> str | None:
    """Retorna a versao do layout ou None se o tamanho nao for reconhecido."""
    if size == ACCOUNT_SIZE_CURRENT:
        return VERSION_CURRENT
    if size == ACCOUNT_SIZE_LEGACY_4294:
        return VERSION_LEGACY_4294
    if ACCOUNT_SIZE_INTERMEDIATE_MIN <= size <= ACCOUNT_SIZE_INTERMEDIATE_MAX:
        return VERSION_INTERMEDIATE
    return None


def is_supported(size: int, *, allow_padded_legacy: bool = False) -> bool:
    """7952 sempre; 7500..7600 so com opt-in; 4294 nunca."""
    if size == ACCOUNT_SIZE_CURRENT:
        return True
    return (
        allow_padded_legacy
        and ACCOUNT_SIZE_INTERMEDIATE_MIN <= size <= ACCOUNT_SIZE_INTERMEDIATE_MAX
    )


def class_master_name(value: int) -> str:
    return {
        1: "ARCH",
        2: "MORTAL",
        3: "CELESTIAL",
        4: "CELESTIALCS",
        5: "SCELESTIAL",
    }.get(value, f"UNKNOWN_{value}")
