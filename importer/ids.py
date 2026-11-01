"""Identidade deterministica para a importacao.

Trocar o namespace quebra a idempotencia: uma reimportacao criaria novas
linhas em vez de atualizar as existentes. Nao alterar sem migracao explicita.
"""

from __future__ import annotations

import uuid

# Namespace fixo do projeto. UUIDv5(namespace, chave) e reproduzivel.
NAMESPACE = uuid.UUID("2f1c9b7e-5d4a-4e3b-9c81-7a6f0d2e4b13")


def canonical_login(login: str) -> str:
    return login.strip().lower()


def account_legacy_key(login: str) -> str:
    return f"account:{canonical_login(login)}"


def account_id(login: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, account_legacy_key(login))


def character_legacy_key(login: str, slot: int) -> str:
    return f"account:{canonical_login(login)}#slot:{slot}"


def character_id(login: str, slot: int) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, character_legacy_key(login, slot))


def item_legacy_key(login: str, char_slot: int | None, container: str, slot: int) -> str:
    if container == "cargo":
        return f"account:{canonical_login(login)}#cargo:{slot}"
    return f"account:{canonical_login(login)}#char:{char_slot}:{container}:{slot}"


def item_id(login: str, char_slot: int | None, container: str, slot: int) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, item_legacy_key(login, char_slot, container, slot))


def import_run_id(source_path: str, manifest_sha256: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"import:{source_path}:{manifest_sha256}")
