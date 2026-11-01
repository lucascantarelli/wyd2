"""Modelo de dominio produzido pelo decoder.

Nada aqui contem senha em texto plano: o decoder entrega `AccountInfo.password`
apenas para o hasher, e o restante do pipeline trabalha com `MigratedAccount`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ItemEffect:
    type: int
    value: int


@dataclass(frozen=True, slots=True)
class Item:
    container: str
    slot: int
    item_index: int
    refine: int
    gem: int | None
    pity: int
    effects: tuple[ItemEffect, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "container": self.container,
            "slot": self.slot,
            "item_index": self.item_index,
            "refine": self.refine,
            "gem": self.gem,
            "pity": self.pity,
            "effects": [[e.type, e.value] for e in self.effects],
        }


@dataclass(frozen=True, slots=True)
class Score:
    level: int
    ac: int
    damage: int
    merchant: int
    attack_run: int
    direction: int
    chaos_rate: int
    max_hp: int
    max_mp: int
    hp: int
    mp: int
    strength: int
    intelligence: int
    dexterity: int
    constitution: int
    special: tuple[int, int, int, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "ac": self.ac,
            "damage": self.damage,
            "merchant": self.merchant,
            "attack_run": self.attack_run,
            "direction": self.direction,
            "chaos_rate": self.chaos_rate,
            "max_hp": self.max_hp,
            "max_mp": self.max_mp,
            "hp": self.hp,
            "mp": self.mp,
            "str": self.strength,
            "int": self.intelligence,
            "dex": self.dexterity,
            "con": self.constitution,
            "special": list(self.special),
        }


@dataclass(frozen=True, slots=True)
class Affect:
    slot: int
    type: int
    value: int
    level: int
    time_value: int


@dataclass(frozen=True, slots=True)
class MobExtra:
    class_master: int
    citizen: int
    fame: int
    soul: int
    mortal_face: int
    mortal_level: int
    arch_level: int
    celestial_level: int
    sub_celestial_level: int
    celestial_reset: int
    arch_cristal: int
    level355: int
    level370: int
    lv40: int
    lv90: int
    raw: bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_master": self.class_master,
            "citizen": self.citizen,
            "fame": self.fame,
            "soul": self.soul,
            "mortal_face": self.mortal_face,
            "mortal_level": self.mortal_level,
            "arch_level": self.arch_level,
            "celestial_level": self.celestial_level,
            "sub_celestial_level": self.sub_celestial_level,
            "celestial_reset": self.celestial_reset,
            "arch_cristal": self.arch_cristal,
        }


@dataclass(frozen=True, slots=True)
class Character:
    slot: int
    name: str
    clan: int
    merchant: int
    guild: int
    char_class: int
    rsv: int
    quest: int
    coin: int
    exp: int
    spx: int
    spy: int
    base: Score
    current: Score
    equip: tuple[Item, ...]
    carry: tuple[Item, ...]
    affects: tuple[Affect, ...]
    learned_skill: int
    magic: int
    score_bonus: int
    special_bonus: int
    skill_bonus: int
    critical: int
    save_mana: int
    skill_bar: tuple[int, int, int, int]
    short_skills: tuple[int, ...]
    guild_level: int
    regen_hp: int
    regen_mp: int
    resist: tuple[int, int, int, int]
    extra: MobExtra

    def item_count(self, container: str) -> int:
        if container == "equip":
            return len(self.equip)
        if container == "carry":
            return len(self.carry)
        return 0


@dataclass(frozen=True, slots=True)
class AccountInfo:
    name: str
    password: str
    real_name: str
    ssn1: int
    ssn2: int
    email: str
    telephone: str
    address: str
    numeric_token: str
    year: int
    year_day: int


@dataclass(frozen=True, slots=True)
class AccountFile:
    path: str
    size: int
    version: str
    sha256: str
    info: AccountInfo
    characters: tuple[Character, ...]
    cargo: tuple[Item, ...]
    cargo_gold: int
    donate: int
    is_blocked: bool
    padding_bytes: int = 0


@dataclass(frozen=True, slots=True)
class MigratedAccount:
    """Conta pronta para o banco: senha/PIN ja convertidos em hash."""

    id: str
    login: str
    password_hash: str
    password_algo: str
    numeric_token_hash: str | None
    email: str | None
    blocked: bool
    must_reset_password: bool
    donate: int
    cargo_gold: int
    legacy_key: str
    legacy_source: str
    source: AccountFile


@dataclass(slots=True)
class ImportIssue:
    severity: str
    code: str
    account: str | None = None
    path: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
        }
        if self.account is not None:
            payload["account"] = self.account
        if self.path is not None:
            payload["path"] = self.path
        if self.detail:
            payload["detail"] = self.detail
        return payload
