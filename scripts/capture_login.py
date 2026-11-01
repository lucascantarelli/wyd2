"""Escuta o primeiro contato do cliente WYD e grava os bytes crus.

Serve para a captura da R02: o cliente e apontado para este processo e o
primeiro pacote (MSG_AccountLogin) fica registrado em `out/capture/`. O
arquivo gerado contem a senha em texto plano, por isso ele nunca sai de
`out/` (que e gitignored) e o resumo no console nao imprime o corpo.

Uso:

    python scripts/capture_login.py --listen 0.0.0.0:8281 --once

O handshake do CPSock comeca com o INITCODE de 4 bytes; depois cada frame tem
um header de 12 bytes cujo primeiro campo e `Size` (u16 little-endian). O
script valida esses dois pontos e resume tipo/tamanho. Para ver o hexdump
completo (inclui credenciais), use `--show-payload`.

Como apontar o cliente para ca: o cliente conecta no servidor que veio do
launcher, entao a captura exige desviar esse destino (ver docs/08-CLIENTE-ALVO
secao 6.1). Enquanto o cliente estiver em sessao, nao adicione o alias de IP:
a rota local derruba a conexao em andamento.
"""

from __future__ import annotations

import argparse
import datetime as dt
import socket
import sys
from pathlib import Path

INIT_CODE = 0x1F11F311
HEADER_SIZE = 12
MAX_CAPTURE = 64 * 1024


def parse_endpoint(value: str) -> tuple[str, int]:
    host, _, port = value.rpartition(":")
    if not host or not port.isdigit():
        raise argparse.ArgumentTypeError(f"endpoint invalido: {value!r} (use host:porta)")
    return host, int(port)


def hexdump(data: bytes, limit: int = 256) -> str:
    lines = []
    for offset in range(0, min(len(data), limit), 16):
        chunk = data[offset : offset + 16]
        hex_part = " ".join(f"{byte:02x}" for byte in chunk)
        text = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
        lines.append(f"{offset:08x}  {hex_part:<47}  {text}")
    if len(data) > limit:
        lines.append(f"... {len(data) - limit} bytes omitidos")
    return "\n".join(lines)


def describe(raw: bytes) -> list[str]:
    """Valida INITCODE e resume os frames sem imprimir o corpo."""
    lines = []
    if len(raw) < 4:
        lines.append("captura curta: nem o INITCODE chegou")
        return lines
    init = int.from_bytes(raw[0:4], "little")
    status = "ok" if init == INIT_CODE else f"INESPERADO (esperado {INIT_CODE:#010x})"
    lines.append(f"INITCODE: {init:#010x} {status}")

    offset = 4
    index = 0
    while offset + HEADER_SIZE <= len(raw):
        size = int.from_bytes(raw[offset : offset + 2], "little")
        message_type = int.from_bytes(raw[offset + 2 : offset + 4], "little")
        lines.append(
            f"frame {index}: size={size} type={message_type:#06x} "
            f"body={max(size - HEADER_SIZE, 0)} bytes"
        )
        if size < HEADER_SIZE or offset + size > len(raw):
            lines.append("frame incompleto ou Size invalido; parando o resumo")
            break
        offset += size
        index += 1
    if index == 0 and len(raw) > 4:
        lines.append(
            f"{len(raw) - 4} bytes apos o INITCODE, insuficientes para um header de {HEADER_SIZE}"
        )
    return lines


def capture(sock: socket.socket, idle_timeout: float) -> bytes:
    chunks = []
    received = 0
    sock.settimeout(idle_timeout)
    while received < MAX_CAPTURE:
        try:
            chunk = sock.recv(4096)
        except TimeoutError:
            break
        if not chunk:
            break
        chunks.append(chunk)
        received += len(chunk)
    return b"".join(chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Captura o handshake do cliente WYD.")
    parser.add_argument("--listen", type=parse_endpoint, default=("0.0.0.0", 8281))
    parser.add_argument("--out", type=Path, default=Path("out/capture"))
    parser.add_argument("--once", action="store_true", help="encerra apos a primeira conexao")
    parser.add_argument("--idle-timeout", type=float, default=2.0)
    parser.add_argument("--show-payload", action="store_true")
    args = parser.parse_args(argv)

    host, port = args.listen
    args.out.mkdir(parents=True, exist_ok=True)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        print(f"escutando em {host}:{port}; destino {args.out}")

        while True:
            conn, peer = server.accept()
            with conn:
                print(f"conexao de {peer[0]}:{peer[1]}")
                raw = capture(conn, args.idle_timeout)
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            path = args.out / f"{stamp}-{peer[0]}-{peer[1]}.bin"
            path.write_bytes(raw)
            print(f"{len(raw)} bytes gravados em {path}")
            for line in describe(raw):
                print(f"  {line}")
            if args.show_payload:
                print(hexdump(raw))
            if args.once:
                return 0


if __name__ == "__main__":
    sys.exit(main())
