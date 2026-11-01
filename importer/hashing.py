"""Hash de senha e PIN.

argon2id e o alvo (docs/03-DADOS-LEGADOS.md §7.4). Se argon2-cffi nao estiver
instalado, usa PBKDF2-HMAC-SHA256 com 600k iteracoes; o algoritmo fica gravado
em accounts.password_algo para permitir rehash futuro.

Texto plano nunca e retornado, logado ou escrito.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

try:  # pragma: no cover - depende do ambiente
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    _ARGON2 = PasswordHasher(
        time_cost=2,
        memory_cost=19_456,  # KiB (19 MiB, minimo OWASP)
        parallelism=1,
        hash_len=32,
        salt_len=16,
    )
except ImportError:  # pragma: no cover - fallback testado via monkeypatch
    PasswordHasher = None  # type: ignore[assignment]
    VerifyMismatchError = Exception  # type: ignore[assignment,misc]
    _ARGON2 = None

PBKDF2_ITERATIONS = 600_000
PBKDF2_PREFIX = "pbkdf2-sha256"


def argon2_available() -> bool:
    return _ARGON2 is not None


def hash_password(password: str) -> tuple[str, str]:
    """Retorna (hash, algoritmo). Nunca retorna o texto plano."""
    if _ARGON2 is not None:
        return _ARGON2.hash(password), "argon2id"

    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32
    )
    encoded = "$".join(
        (
            PBKDF2_PREFIX,
            str(PBKDF2_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(derived).decode("ascii"),
        )
    )
    return encoded, PBKDF2_PREFIX


def verify_password(stored: str, password: str) -> bool:
    if stored.startswith("$argon2"):
        if _ARGON2 is None:
            return False
        try:
            return _ARGON2.verify(stored, password)
        except VerifyMismatchError:
            return False

    if stored.startswith(PBKDF2_PREFIX + "$"):
        try:
            _, iterations, salt_b64, hash_b64 = stored.split("$", 3)
            salt = base64.b64decode(salt_b64)
            expected = base64.b64decode(hash_b64)
            derived = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, int(iterations), dklen=len(expected)
            )
            return secrets.compare_digest(derived, expected)
        except (ValueError, TypeError):
            return False

    return False
