#!/usr/bin/env bash
# Sobe um PostgreSQL 16 efêmero, aplica schema + fixture e roda o teste de
# integração do gateway. Requer Docker; o container é removido ao sair.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if command -v docker >/dev/null 2>&1; then
    DOCKER=docker
elif [[ -x "/c/Program Files/Docker/Docker/resources/bin/docker.exe" ]]; then
    DOCKER="/c/Program Files/Docker/Docker/resources/bin/docker.exe"
else
    echo "erro: docker nao encontrado no PATH" >&2
    exit 1
fi

NAME="${WYD_TEST_PG_NAME:-wyd-gateway-pg16-test}"
PORT="${WYD_TEST_PG_PORT:-55432}"

cleanup() {
    "$DOCKER" rm -f "$NAME" >/dev/null 2>&1 || true
}
cleanup
trap cleanup EXIT

echo "subindo postgres:16 como $NAME na porta $PORT"
"$DOCKER" run -d --rm --name "$NAME" \
    -e POSTGRES_USER=wyd \
    -e POSTGRES_PASSWORD=wyd_test \
    -e POSTGRES_DB=wyd \
    -p "127.0.0.1:${PORT}:5432" \
    postgres:16 >/dev/null

ready=0
for _ in $(seq 1 60); do
    if "$DOCKER" logs "$NAME" 2>&1 | grep -q "database system is ready to accept connections"; then
        if "$DOCKER" exec "$NAME" psql -U wyd -d wyd -c 'SELECT 1' >/dev/null 2>&1; then
            ready=1
            break
        fi
    fi
    sleep 1
done

if [[ "$ready" -ne 1 ]]; then
    echo "erro: PostgreSQL nao ficou pronto" >&2
    "$DOCKER" logs "$NAME" >&2 || true
    exit 1
fi

echo "aplicando schema"
"$DOCKER" exec -i "$NAME" psql -v ON_ERROR_STOP=1 -U wyd -d wyd \
    < "$ROOT/schema/001_init.sql" >/dev/null
# catalog.items e obrigatorio: o gateway valida o item_index no login.
"$DOCKER" exec -i "$NAME" psql -v ON_ERROR_STOP=1 -U wyd -d wyd \
    < "$ROOT/schema/002_catalog.sql" >/dev/null

echo "aplicando fixture"
"$DOCKER" exec -i "$NAME" psql -v ON_ERROR_STOP=1 -U wyd -d wyd \
    < "$ROOT/gateway/tests/fixtures/postgres.sql" >/dev/null

export WYD_TEST_DATABASE_URL="host=127.0.0.1 port=${PORT} user=wyd password=wyd_test dbname=wyd connect_timeout=5"

echo "rodando cargo test --test postgres"
cd "$ROOT/gateway"
cargo test --test postgres -- --nocapture
