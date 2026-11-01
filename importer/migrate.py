"""Conversao de `AccountFile` para o modelo persistivel.

A senha e o PIN em texto plano existem apenas dentro desta funcao: saem do
`AccountFile`, viram hash e o objeto resultante (`MigratedAccount`) nao expoe
mais o texto plano.
"""

from __future__ import annotations

from . import ids
from .hashing import hash_password
from .model import AccountFile, MigratedAccount


def migrate_account(account: AccountFile) -> MigratedAccount:
    login = account.info.name.strip()
    password_hash, password_algo = hash_password(account.info.password)

    token = account.info.numeric_token.strip()
    token_hash = hash_password(token)[0] if token else None

    email = account.info.email.strip() or None

    return MigratedAccount(
        id=str(ids.account_id(login)),
        login=login,
        password_hash=password_hash,
        password_algo=password_algo,
        numeric_token_hash=token_hash,
        email=email,
        blocked=bool(account.is_blocked),
        must_reset_password=True,
        donate=account.donate,
        cargo_gold=account.cargo_gold,
        legacy_key=ids.account_legacy_key(login),
        legacy_source=account.path,
        source=account,
    )
