# Gateway PoC — Fase 3

Gateway TCP em Rust que fala a camada de transporte do WYD (7662 + login do WYD Global):

- `INITCODE` de 4 bytes (`0x1F11F311`);
- header de 12 bytes e framing por `Size` (12..8192);
- tabela `pKeyWord[512]`, ofuscação simétrica e checksum;
- `MSG_AccountLogin` de 104 B (7662) e de 112 B (WYD Global), com a versão validada por layout;
- limite de falhas de login por IP e por conta (10 falhas/60 s por padrão) antes de tocar
  no diretório ou no hash;
- resposta `MSG_CNFAccountLogin` de 2008 bytes com `STRUCT_SELCHAR` e cargo;
- painel de erro (`MSG_MessagePanel`) e `MSG_CharacterLoginFail` para a
  seleção de personagem, que ainda não entra no mundo.

O layout de saída está em [docs/02-PROTOCOLO.md](../docs/02-PROTOCOLO.md) §7.8.

> ⚠️ **Escopo do PoC.** O login aceita os dois contratos: 104 B/7640 (7662) e 112 B/
> `0x0C9DB301` (WYD Global, capturado em 2026-11-01 —
> [R02](../roadmap/issues/R02.md)). O `CNF` de 2008 bytes e a seleção continuam derivados
> do 7662 e ainda **não** foram validados contra o cliente novo: aceitar o login não prova
> que o cliente aceita o `CNF`.

## Fontes de conta

### PostgreSQL 16 (padrão para contas reais)

Aplica o schema da Fase 2 e importa as contas:

```bash
psql -d wyd -f schema/001_init.sql
psql -d wyd -f schema/002_catalog.sql
cd out && psql -d wyd -f load.sql
# catálogo do cliente — obrigatório, o gateway valida item_index no login
cd catalog && psql -d wyd -f load_catalog.sql
```

O schema `catalog` vem de [docs/07](../docs/07-IMPORTACAO.md) §3.4 e §5.5.

Depois sobe o gateway com a connection string. O formato URL ou `chave=valor`
do `postgres` é aceito:

```bash
cd gateway
WYD_DATABASE_URL='postgres://wyd:senha@127.0.0.1:5432/wyd' \
  cargo run --release -- --listen 127.0.0.1:8281
```

O boot falha se o schema/tabelas não existirem: o gateway não deve subir
aparentando autenticar sem banco. A connection string **não** é registrada em
log; mensagens de erro não ecoam a senha.

O gateway lê, por login canônico (`lower(login)`):

| Origem | Uso no `MSG_CNFAccountLogin` |
|---|---|
| `accounts.login` / `password_hash` / `blocked` | validação e fechamento |
| `accounts.cargo_gold` | `Coin` do cargo |
| `characters.slot`, `name`, `spx`, `spy`, `level`, `exp`, `gold` | `STRUCT_SELCHAR` |
| `characters.current_*` | `STRUCT_SCORE` (AC, dano, HP/MP, Str/Int/Dex/Con, Special) |
| `characters.guild_legacy_id` | `Guild` |
| `items` com `container='equip'` | `Equip[16]` de cada personagem |
| `items` com `container='cargo'` | `Cargo[128]` da conta |
| `catalog.items` | validação: todo `items.item_index` precisa existir |

Todo `item_index` gravado em `wyd.items` é conferido contra `catalog.items`
(`EXISTS` nas consultas de equipamento e cargo) antes de o `CNF` ser montado.
Item ausente **recusa o login** com painel genérico; o log do operador registra
`item de equip com item_index 9999 nao existe em catalog.items; carregue o
catalogo do cliente (schema/002_catalog.sql + load_catalog.sql)`. Isso evita
enviar ao cliente um índice que ele não sabe resolver. O boot também falha se
as tabelas de `catalog` não existirem. Para achar pendências antes do login:

```sql
SELECT * FROM catalog.missing_items;
SELECT * FROM catalog.out_of_range_items;
SELECT * FROM catalog.coverage;
```

As senhas são verificadas contra `accounts.password_hash`:

- PHC `$argon2id$...` (argon2id v19, parâmetros da string);
- `pbkdf2-sha256$iterações$salt_b64$hash_b64` (o importador usa 600 000).

O gateway usa as crates `argon2` e `pbkdf2`; não implementa criptografia própria
e nunca registra senha nem hash. Contas com `blocked = true` recebem painel de
conta bloqueada somente depois da senha correta.

Valores que não cabem no tipo de fio (`smallint`, `integer`, `smallint[]` com
mais de 4 posições) são rejeitados como erro de diretório, em vez de truncados
silenciosamente.

### Conta demo em memória

Sem `WYD_DATABASE_URL`/`--database-url`, sobe uma conta sintética para exercitar
o transporte sem banco:

```bash
cd gateway
cargo run --release -- --listen 127.0.0.1:8281
```

Conta padrão: `TestAccount` / `Secret123!`, com dois personagens (`Hero` e
`Mage`). Para trocar:

```bash
cargo run --release -- --login MinhaConta --password MinhaSenha
```

Variáveis equivalentes: `WYD_LISTEN`, `WYD_LOGIN`, `WYD_PASSWORD`.

Ao conectar, o cliente deve enviar `INITCODE`, o `MSG_AccountLogin` e receber
o `MSG_CNFAccountLogin`. Ao escolher um personagem, o PoC responde com um
painel e `MSG_CharacterLoginFail` — não há snapshot de mundo nem persistência
de sessão.

## Testes

```bash
cd gateway
cargo test --all-targets
cargo clippy --all-targets -- -D warnings
cargo fmt --check
```

A suíte unitária/e2e cobre header, codec, framing com bytes parciais/colados,
login, layout do `CNF`, hashes argon2id/PBKDF2, rejeição de
senha/versão/bloqueio e um teste TCP ponta a ponta. Há também uma matriz hostil
de framing (`Size` fora da faixa, header truncado, `CheckSum` adulterado, ID
inválido e timeout) que exige fechamento sem resposta e um login válido logo
depois, provando que o listener não fica preso.

O handshake do WYD Global está congelado em
`tests/fixtures/account_login_global.hex` (128 B: `INITCODE` + `MSG_AccountLogin`
de 112 B). O teste decodifica o vetor, re-codifica byte a byte e o envia a um
gateway real, exigindo o `CNF` de 2.008 B. O vetor é sintético (`TestAccount`,
token de 22 B zerado) para não versionar credenciais nem identificador da
máquina.

O teste de integração com **PostgreSQL 16 em Docker** é opt-in:

```bash
bash gateway/scripts/test-postgres.sh
```

O script sobe `postgres:16` efêmero, aplica `schema/001_init.sql`,
`schema/002_catalog.sql` e `gateway/tests/fixtures/postgres.sql`, e roda
`cargo test --test postgres`. Ele valida a carga de conta, personagens,
equipamento, cargo, bloqueio, verificação de hash, rejeição de item fora do
catálogo e logins TCP reais contra o banco, incluindo o handshake congelado de
112 B do WYD Global. Sem
`WYD_TEST_DATABASE_URL`, esses testes são pulados e o restante de `cargo test`
continua funcionando.

## Limites explícitos

- **Sem mundo:** `MSG_CharacterLogin` só devolve falha controlada; snapshot,
  spawn e persistência de sessão não existem.
- **Sem TLS no cliente:** o protocolo legado não tem criptografia; o gateway
  não deve ser exposto à internet sem uma camada de proteção.
- **Banco sem TLS e com uma conexão:** `NoTls` e um único `Client` protegido
  por mutex. É suficiente para o PoC; pool, reconexão e TLS ficam para a
  versão de carga.
- **Captura parcial:** o login do WYD Global está congelado em vetor sintético,
  ancorado na captura real; o `CNF` e a seleção ainda não foram comparados com
  o cliente rodando.
- **`CNF` parcial:** `HashKeyTable`, `Keys`, `QuestDiaria`, `BlockPass` e
  `IsBlocked` vão zerados; `Unknow_28` vale 1. O cliente pode exigir esses
  campos para funcionalidades além da seleção.
- **Uma thread por conexão:** suficiente para o PoC; Tokio e métricas ficam
  para a versão de carga.
- **Rate limit em memória e por processo:** a janela de falhas de login zera
  ao reiniciar e é compartilhada por clientes atrás do mesmo IP (NAT).
  Sessão/movimento e backpressure continuam pendentes (R06).
- **`must_reset_password` não é aplicado:** não há fluxo de troca de senha
  ainda; bloquear o login deixaria as contas migradas sem acesso.

## Clean-room

A implementação foi escrita a partir de `docs/` e `spec/`. A tabela
`pKeyWord` é dado público de protocolo; nenhum código do repositório de
referência foi copiado.
