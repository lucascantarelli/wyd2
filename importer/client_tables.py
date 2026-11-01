"""Decodificador das tabelas de conteudo do cliente WYD Global.

Cobre `SkillData.bin` e `ItemList.bin` do cliente em `reference/WYD Global`.
O formato foi medido nos arquivos reais (ver docs/03-DADOS-LEGADOS.md §6.5):

- todo o payload e XOR 0x5A;
- os ultimos 4 bytes sao um `int32` cru, **sem** XOR (o mesmo `nRand` que o
  escritor do 7662 anexa depois do array);
- `SkillData.bin` = 248 registros de 104 bytes;
- `ItemList.bin` = 14.500 registros de 172 bytes, com nome NUL-terminado e
  preenchimento 0xFE nos registros usados (0x00 nos vazios).

O encode e o inverso exato do decode: `encode_*(parse_*(raw)) == raw`. Se um
campo deixar de ser coberto, o round-trip quebra — e e isso que o teste cobra.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .errors import ClientTableError

XOR_KEY = 0x5A
TRAILER_SIZE = 4

NAME_LENGTH = 64
NAME_FILL_USED = 0xFE
NAME_FILL_EMPTY = 0x00
MAX_STATICEFFECT = 12

SKILL_RECORD_SIZE = 104
ITEM_RECORD_SIZE = 172

# --- SkillData.bin: offsets relativos ao inicio do registro ----------------
SKILL_FIELDS = (
    "skill_point",
    "target_type",
    "mana",
    "delay",
    "range",
    "instance_type",
    "instance_value",
    "tick_type",
    "tick_value",
    "affect_type",
    "affect_value",
    "affect_time",
)
SKILL_ATTRIBUTE_ARRAYS = (48, 56)  # dois blocos de 8 bytes
SKILL_TAIL_VALUES = 64  # 8 ints
SKILL_TAIL_COUNT = 8
SKILL_ID = 96
SKILL_FLAG = 100

# --- ItemList.bin: offsets relativos ao inicio do registro ----------------
ITEM_MESH = 64
ITEM_EFFECTS = 80
ITEM_PRICE = 128
ITEM_UNIQUE = 132
ITEM_EXTRA = 134
ITEM_POSITION = 136
ITEM_GRADE = 138
ITEM_EXTENSION = 140
ITEM_EXTENSION_SIZE = 32
# dentro da extensao: id canonico, igual ao indice na maioria dos registros
ITEM_CANONICAL_ID = 28


def xor_bytes(data: bytes) -> bytes:
    """Aplica o XOR do cliente. Simetrico: serve para decodificar e codificar."""
    return bytes(byte ^ XOR_KEY for byte in data)


@dataclass(frozen=True, slots=True)
class SkillRecord:
    """Um registro de `SkillData.bin`.

    Os 12 primeiros campos seguem a ordem do `STRUCT_SPELL` do 7662
    (`docs/03-DADOS-LEGADOS.md` §6.2); a correspondencia e derivada da faixa de
    valores medida, nao de uma fonte do cliente.
    """

    skill_point: int
    target_type: int
    mana: int
    delay: int
    range: int
    instance_type: int
    instance_value: int
    tick_type: int
    tick_value: int
    affect_type: int
    affect_value: int
    affect_time: int
    instance_attribute: bytes
    tick_attribute: bytes
    tail_values: tuple[int, ...]
    skill_id: int
    flag: int


@dataclass(frozen=True, slots=True)
class ItemRecord:
    """Um registro de `ItemList.bin`.

    `extension` guarda os 32 bytes finais, cuja semantica nao foi identificada.
    `canonical_id` e o `u16` no offset 28 dela: igual ao indice do registro em
    3.868 dos 4.300 registros nomeados e, nos demais, aponta para o primeiro
    registro com o mesmo nome.
    """

    name: str
    mesh: int
    texture: int
    visual_effect: int
    req_level: int
    req_str: int
    req_int: int
    req_dex: int
    req_con: int
    effects: tuple[tuple[int, int], ...]
    price: int
    unique: int
    extra: int
    position: int
    grade: int
    extension: bytes
    name_fill: int = NAME_FILL_EMPTY

    @property
    def canonical_id(self) -> int:
        return struct.unpack_from("<H", self.extension, ITEM_CANONICAL_ID)[0]

    @property
    def is_empty(self) -> bool:
        return not self.name


@dataclass(frozen=True, slots=True)
class SkillTable:
    trailer: int
    records: tuple[SkillRecord, ...]


@dataclass(frozen=True, slots=True)
class ItemTable:
    trailer: int
    records: tuple[ItemRecord, ...]


def _split(raw: bytes, record_size: int, label: str) -> tuple[bytes, int, int]:
    """Separa payload ofuscado, trailer cru e contagem de registros."""
    minimum = TRAILER_SIZE + record_size
    if len(raw) < minimum:
        raise ClientTableError(f"{label}: {len(raw)} bytes, minimo {minimum}")
    payload = xor_bytes(raw[:-TRAILER_SIZE])
    if len(payload) % record_size:
        raise ClientTableError(
            f"{label}: payload de {len(payload)} bytes nao divide em registros de {record_size}"
        )
    trailer = struct.unpack("<I", raw[-TRAILER_SIZE:])[0]
    return payload, trailer, len(payload) // record_size


def parse_skill_table(raw: bytes) -> SkillTable:
    """Decodifica `SkillData.bin` inteiro."""
    payload, trailer, count = _split(raw, SKILL_RECORD_SIZE, "SkillData.bin")
    records = []
    for index in range(count):
        base = index * SKILL_RECORD_SIZE
        values = struct.unpack_from("<12i", payload, base)
        first, second = (struct.unpack_from("<8s", payload, base + offset)[0] for offset in SKILL_ATTRIBUTE_ARRAYS)
        tail = struct.unpack_from(f"<{SKILL_TAIL_COUNT}i", payload, base + SKILL_TAIL_VALUES)
        skill_id, flag = struct.unpack_from("<2i", payload, base + SKILL_ID)
        records.append(
            SkillRecord(
                *values,
                instance_attribute=first,
                tick_attribute=second,
                tail_values=tail,
                skill_id=skill_id,
                flag=flag,
            )
        )
    return SkillTable(trailer=trailer, records=tuple(records))


def encode_skill_table(table: SkillTable) -> bytes:
    """Reconstroi os bytes de `SkillData.bin` a partir do modelo."""
    payload = bytearray()
    for record in table.records:
        payload += struct.pack("<12i", *(getattr(record, name) for name in SKILL_FIELDS))
        payload += record.instance_attribute
        payload += record.tick_attribute
        payload += struct.pack(f"<{SKILL_TAIL_COUNT}i", *record.tail_values)
        payload += struct.pack("<2i", record.skill_id, record.flag)
    return xor_bytes(bytes(payload)) + struct.pack("<I", table.trailer)


def _decode_name(field: bytes) -> str:
    head, _, _ = field.partition(b"\0")
    return head.decode("latin-1")


def _encode_name(name: str, fill: int) -> bytes:
    encoded = name.encode("latin-1")
    if len(encoded) > NAME_LENGTH - 1:
        raise ClientTableError(f"nome de item com {len(encoded)} bytes excede {NAME_LENGTH - 1}")
    return encoded + b"\0" + bytes([fill]) * (NAME_LENGTH - len(encoded) - 1)


def parse_item_table(raw: bytes) -> ItemTable:
    """Decodifica `ItemList.bin` inteiro."""
    payload, trailer, count = _split(raw, ITEM_RECORD_SIZE, "ItemList.bin")
    records = []
    for index in range(count):
        base = index * ITEM_RECORD_SIZE
        field = payload[base : base + NAME_LENGTH]
        name = _decode_name(field)
        # Mesh/textura/requisitos sao assinados: 0xFFFF e -1 (mesh ausente),
        # nao 65535. Posicao/grade ficam sem sinal (nPos usa o bit 15).
        shorts = struct.unpack_from("<8h", payload, base + ITEM_MESH)
        effects = tuple(
            struct.unpack_from("<2H", payload, base + ITEM_EFFECTS + 4 * slot) for slot in range(MAX_STATICEFFECT)
        )
        price = struct.unpack_from("<I", payload, base + ITEM_PRICE)[0]
        unique, extra, position, grade = struct.unpack_from("<4H", payload, base + ITEM_UNIQUE)
        extension = payload[base + ITEM_EXTENSION : base + ITEM_EXTENSION + ITEM_EXTENSION_SIZE]
        name_fill = field[NAME_LENGTH - 1] if name else NAME_FILL_EMPTY
        records.append(
            ItemRecord(
                name=name,
                mesh=shorts[0],
                texture=shorts[1],
                visual_effect=shorts[2],
                req_level=shorts[3],
                req_str=shorts[4],
                req_int=shorts[5],
                req_dex=shorts[6],
                req_con=shorts[7],
                effects=effects,
                price=price,
                unique=unique,
                extra=extra,
                position=position,
                grade=grade,
                extension=extension,
                name_fill=name_fill,
            )
        )
    return ItemTable(trailer=trailer, records=tuple(records))


def encode_item_table(table: ItemTable) -> bytes:
    """Reconstroi os bytes de `ItemList.bin` a partir do modelo."""
    payload = bytearray()
    for record in table.records:
        payload += _encode_name(record.name, record.name_fill)
        payload += struct.pack(
            "<8h",
            record.mesh,
            record.texture,
            record.visual_effect,
            record.req_level,
            record.req_str,
            record.req_int,
            record.req_dex,
            record.req_con,
        )
        for effect, value in record.effects:
            payload += struct.pack("<2H", effect, value)
        payload += struct.pack("<I", record.price)
        payload += struct.pack("<4H", record.unique, record.extra, record.position, record.grade)
        payload += record.extension
    return xor_bytes(bytes(payload)) + struct.pack("<I", table.trailer)
