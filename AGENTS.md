# AGENTS.md — WYD Next-Gen

Instruções para agentes de código (Freebuff, Codebuff, Claude Code). Leia este
arquivo antes de alterar o projeto; ele é carregado no início de cada chat.

## O que é o projeto

Reconstrução do servidor de **With Your Destiny** (cliente-alvo: WYD Global) em
stack moderna: especificação verificada em `docs/`, schema PostgreSQL em
`schema/`, importador clean-room em `importer/` e gateway TCP em Rust em
`gateway/`. Nada de copiar o código legado: `reference/` é oráculo de
comportamento, não fonte para copiar (GPLv3, fora do artefato distribuído).

Estado atual: Fases 1–2 concluídas; Fase 3 (login + `MSG_CNFAccountLogin`)
funcionando. Sem mundo jogável, sem `CharacterLogin`. O roadmap vivo está em
[`roadmap/`](roadmap/) e o índice da especificação em
[`docs/00-INDICE.md`](docs/00-INDICE.md).

## Antes de codar

1. Leia o documento de [`docs/`](docs/) que cobre a área e a issue em
   [`roadmap/issues/`](roadmap/issues/) — cada uma tem objetivo, entregáveis,
   riscos e checklist.
2. Leia a skill relevante em [`.agents/skills/`](.agents/skills/). Cada skill é
   um `SKILL.md` com frontmatter e aparece como `/skill:<nome>` no Freebuff.
3. Se o comportamento vem do servidor legado, cite `arquivo:linha` ou marque a
   inferência (🟡). Nenhum número sem origem.

## Mapa do repositório

| Caminho | Conteúdo |
|---|---|
| `docs/` | especificação narrativa (fonte de verdade do comportamento) |
| `spec/` | contratos legíveis por máquina (`opcodes.yaml`, `constants.yaml`) |
| `data/` | dados extraídos e versionados (XP, refino, coeficientes) |
| `schema/` | DDL versionado (`001_init.sql`, `002_catalog.sql`) |
| `importer/` | decodifica o legado e emite pacote idempotente |
| `gateway/` | servidor TCP em Rust (transporte, login, diretório) |
| `tests/` | testes Python e fixtures sintéticas |
| `roadmap/` | visão de execução, issues R00–R13, agentes |
| `.agents/skills/` | skills do projeto (formato Freebuff/Codebuff) |
| `skills/` | apenas entrada humana para as skills |
| `reference/` | fonte GPLv3, **gitignored**, nunca copiar código |
| `out/` | pacotes gerados (contêm hashes de senha) — nunca versionar |

## Comandos

Use Bash (Git Bash no Windows), sempre a partir da raiz:

```bash
# Python (importador, schema, reconciliacao)
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check .
.venv/Scripts/python.exe scripts/verify_spec.py

# Gateways (Rust)
cd gateway && cargo fmt -- --check && cargo clippy --all-targets -- -D warnings
cd gateway && cargo test --all-targets

# Integracao opcional com PostgreSQL 16 (Docker; pula sem WYD_TEST_DATABASE_URL)
bash gateway/scripts/test-postgres.sh

# Importacao de contas / catalogo
.venv/Scripts/python.exe -m importer --source "reference/..." --emit out
.venv/Scripts/python.exe -m importer.catalog --client "reference/WYD Global" --emit out/catalog
```

O Docker Desktop pode não estar no `PATH`; o script de teste já procura o
caminho padrão. Em `docker exec` com paths absolutos, use
`MSYS_NO_PATHCONV=1`.

## Regras de engenharia

- **Idempotência:** UUIDs são determinísticos (`importer/ids.py`); `load.sql` e
  `load_catalog.sql` podem rodar duas vezes sem duplicar. Não troque o namespace
  sem migração explícita.
- **Ledger append-only:** `item_ledger` rejeita `UPDATE`/`DELETE` no banco.
- **Catálogo validado:** `catalog.items` é obrigatório para o gateway; todo
  `item_index` em `wyd.items` precisa existir e caber em `int16`.
- **Segredos:** nunca versionar `out/`, `.env`, hashes ou credenciais. O
  gateway não registra senha nem hash.
- **Tamanho:** 200–250 linhas é sinal de atenção; acima de 300, quebre por
  responsabilidade, não por número.
- **Comentários e mensagens de código:** português sem acento (ASCII) em
  mensagens de erro; documentação em pt-BR com acentuação.
- **Formatação:** Python com `ruff` (line-length 100, regras em `ruff.toml`);
  Rust com `cargo fmt`.

## Definição de pronto

- Rodar o menor check que cobre a mudança (teste focado, `cargo test`, lint) e
  relatar o que não foi possível rodar.
- Atualizar a documentação afetada (`docs/`, `README.md`, `roadmap/`) e marcar
  o checklist da issue quando ela fechar.
- Não commitar, publicar ou subir site sem pedido explícito.

## Skills

As skills do projeto são as 14 áreas em `.agents/skills/<nome>/SKILL.md`
(transporte, contas/personagens, combate, modelagem de dados, migração, QA,
DevOps, etc.). Carregue a que corresponde à tarefa antes de implementar; se
alterar uma skill, mantenha o `name` igual ao diretório e a `description`
curta e específica, começando por "Use quando".

Cada issue em `roadmap/issues/` tem a linha **Skills** e a seção
**Skills para executar**, com o motivo de carregar cada uma. O vínculo fica na
issue; as skills não listam issues — elas só descrevem quando usar.
