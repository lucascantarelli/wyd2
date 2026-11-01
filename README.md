# WYD Next-Gen

Reconstituição do servidor de **With Your Destiny** em stack moderna: especificação
verificada em `docs/`, schema PostgreSQL em `schema/`, importador clean-room em `importer/`
e gateway TCP em Rust em `gateway/`. Nada de copiar o código legado: `reference/` é
oráculo de comportamento, não fonte para copiar (GPLv3, fora do artefato distribuído).

O cliente alvo é o **WYD Global** (`reference/WYD Global`), não o 7662 documentado.
A captura de 2026-11-01 mediu `ClientVersion = 0x0C9DB301` e corpo de 112 B no
`MSG_AccountLogin`. As decisões de produto (paridade, MVP, operação, bots) estão
registradas na issue [`roadmap/issues/R01.md`](roadmap/issues/R01.md).

## Visão rápida

| Camada | Onde |
|---|---|
| Especificação | `docs/` (00–09) |
| Contratos de máquina | `spec/opcodes.yaml`, `spec/constants.yaml` |
| Dados extraídos | `data/xp_mortal_arch.csv`, `data/xp_celestial.csv`, `data/refine_rates.json`, `data/class_weapon_coefficients.json` |
| Schema PostgreSQL | `schema/001_init.sql`, `schema/002_catalog.sql` |
| Importador (conta, catálogo, reconciliação, emit) | `importer/` |
| Gateway TCP em Rust | `gateway/` |
| Testes Python | `tests/` (82 testes) e `gateway/tests/` |
| Roadmap e issues | `roadmap/`, `roadmap/issues/R00.md`–`R13.md` |
| Skills do agente | `.agents/skills/<nome>/SKILL.md` (14 áreas) |

## Pilares

- **Paridade por padrão, endurecimento como flag.** O novo servidor replica o legado até
  onde a documentação permite; cada divergência é entrada documentada em
  [`docs/09-PARIDADE.md`](docs/09-PARIDADE.md).
- **Sem autoridade delegada ao cliente.** HP, EXP, MP, posições e itens são recalcualdos
  pelo servidor; o cliente é apresentação.
- **Nenhum número sem origem.** Fórmulas etiquetadas com `arquivo:linha` ou registradas
  em `data/`. Inferência vira 🟡, não fato.
- **Clean-room comportamental.** A referência é oráculo; código novo começa de `docs/`
  e `spec/`, nunca de `reference/`.
- **Segurança e LGPD desde o começo.** Senha/PIN migram para hash; PII forte não
  persiste; `out/` é protegido e nunca versionado.

## Fases

| Fase | Entrega | Estado |
|---|---|---|
| 0 — Engenharia reversa | Espaço de problema mapeado, fontes classificadas, riscos registrados | ✅ base |
| 1 — Especificação | `docs/02`–`07` + contratos `opcodes.yaml`, `constants.yaml` | ✅ concluída |
| 2 — Dados | Schema + conversor `STRUCT_ACCOUNTFILE`, UUID, ledger, reconciliação, catálogo do cliente | ✅ concluída |
| 3 — Gateway PoC | INITCODE, framing, codec, login de conta, carga do PostgreSQL, validação de catálogo no login | 🟡 transporte + login |
| 4 — Combate | `resolve_hit` puro, golden cases, dano mágico por skill, crítico, refino com pity | pendente |
| 5 — Mundo + sessão | `CharacterLogin`, spawn, snapshot, persistência de sessão, movimento com validação server-side | pendente |
| 6 — Bots | Cliente headless + LLM com contexto + máquina de estados + A* | pendente |

## Como rodar

### Python / importador

```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check . --config ruff.toml
.venv/Scripts/python.exe scripts/verify_spec.py
```

### Gateway (Rust)

```bash
cd gateway
cargo fmt -- --check
cargo clippy --all-targets -- -D warnings
cargo test --all-targets
```

### Integracao com PostgreSQL 16

```bash
bash gateway/scripts/test-postgres.sh
```

Sem `WYD_TEST_DATABASE_URL`, o script pula os testes de integração com PG.

## Produto

- **Decisão de origem:** [R01 — decisões de produto](roadmap/issues/R01.md).
- **Mapa de decisão por mecânica:** [docs/09-PARIDADE.md](docs/09-PARIDADE.md) e
  [docs/06-LACUNAS-E-RISCOS.md](docs/06-LACUNAS-E-RISCOS.md) §3 (D1–D12).
- **O que foi implementado até agora:** transporte e codec do fio, guarda-login de conta
  (7662 + WYD Global), `MSG_CNFAccountLogin` de 2008 B, validação de catálogo no login,
  schema PostgreSQL 16 + exportação idempotente do pacote de importação, e 82 testes
  Python + lint + verificação da especificação. Nada de combate, mundo e sessão ou bots.

## Skills do agente

As skills canônicas ficam em `.agents/skills/<nome>/SKILL.md` e são descobertas pelo
Freebuff/Codebuff como `/skill:<nome>`. Cada uma tem frontmatter com `name`,
`description` e `metadata.category`, e está versionada com o repositório. O diretório
`skills/` é apenas ponto de entrada humano.

| Skill | Foco |
|---|---|
| `habilidades-contas-personagens` | login, autenticação, seleção, inventário, stats, persistência |
| `habilidades-combate` | dano físico/mágico, crítico, esquiva, parry, coeficientes, drops |
| `habilidades-conteudo` | itens, skills, NPCs, mapas, guildas, ranking, guerra |
| `habilidades-transporte` | INITCODE, framing, codec, pKeyWord, opcodes, gateway |
| `habilidades-migracao-massa` | decode legado, dry-run, emit, carga, reconciliação |
| `habilidades-qa-testes` | unitário, integração, e2e, golden vectors, fuzzing |
| `habilidades-modelagem-dados` | schema PostgreSQL, UUID, ledger, views, integridade |
| `habilidades-infra-observabilidade` | pool, reconexão, segurança, backups, métricas, OTel |
| `habilidades-bots-ia` | cliente headless, máquina de estados, A*, LLM com contexto |
| `habilidades-legal-operacao` | proveniência, licença, LGPD, logs, backup, DR |
| `habilidades-devops` | ambientes, CI/CD, format/lint/testes, schema, rollback, secrets |
| `habilidades-arquitetura-design` | monólito modular, multi-shard, limites de deploy |
| `habilidades-balanceamento-economia` | XP, rebirth, atributos, refino, pity, taxa de combine |
| `habilidades-melhores-praticas` | código limpo,SOLID, organização, testes |

## Leitura recomendada (para quem entra agora)

- [`docs/00-INDICE.md`](docs/00-INDICE.md) — mapa de leitura, convenções, status
- [`docs/02-PROTOCOLO.md`](docs/02-PROTOCOLO.md) — transporte, header, codec e login
- [`docs/07-IMPORTACAO.md`](docs/07-IMPORTACAO.md) — schema, UUID, ledger, reconciliação
- [`docs/06-LACUNAS-E-RISCOS.md`](docs/06-LACUNAS-E-RISCOS.md) — riscos, decisões de paridade
- [`roadmap/README.md`](roadmap/README.md) — execução, índice de issues, skills
- [`gateway/README.md`](gateway/README.md) — subir o gateway, fontes de conta, testes
