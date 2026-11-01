"""Erros do decodificador de arquivos legados."""

from __future__ import annotations


class LegacyFormatError(Exception):
    """Base para falhas de formato legado."""


class UnsupportedAccountSize(LegacyFormatError):
    """Tamanho de arquivo reconhecido como legado, mas sem layout mapeado."""

    def __init__(self, size: int) -> None:
        self.size = size
        super().__init__(f"tamanho de conta sem layout mapeado: {size} bytes")


class TruncatedAccount(LegacyFormatError):
    """Arquivo menor que o layout declarado."""


class DecodeError(LegacyFormatError):
    """Campo fora dos limites ou bytes insuficientes durante o decode."""


class ClientTableError(LegacyFormatError):
    """Tabela de conteudo do cliente com tamanho ou layout inesperado."""
