---
name: habilidades-contas-personagens
description: "Use quando a tarefa envolver conta, login ou personagem: autenticação, hash de senha/PIN, bloqueio, seleção, cargo, equipamento, stats, posição, persistência e CharacterLogin."
metadata:
  category: wyd-next-gen
---

# Habilidades — Contas e Personagens (WYD)

> Base para as habilidades do sistema de agentes: login, autenticação, seleção de personagem, carga de inventário/equipamento, posição, stats e persistência.

---

## Quando usar

- Mexer em login, hash de senha/PIN, bloqueio ou seleção de personagem.
- Importar conta legada, cargo, equipamento ou stats.
- Implementar `CharacterLogin`, snapshot de sessão ou persistência de personagem.
- Depurar item ou efeito que não aparece no `STRUCT_SELCHAR`.

## 1. Contexto

O servidor legado não tem banco. Contas e personagens vivem em arquivos plano: um arquivo por conta, com `STRUCT_ACCOUNTFILE` (7952 bytes com alinhamento natural MSVC x86), senha em texto plano e sem identidade única de item. A migração para PostgreSQL traz UUID por item, ledger de transações e reconciliação — e muda o modo como as habilidades leem e escrevem dados: nunca mais por caminho de arquivo.

As habilidades abaixo não são uma cópia do legado; são as ações que o sistema de agentes (servidor + bots + operação) precisa executar sobre a nova base.

---

## 2. Habilidades de conta

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Autenticar conta** | Conferir login canônico (`lower(login)`) + hash de senha (argon2id ou PBKDF2) contra `wyd.accounts`. | login + senha → `Account` ou erro de categoria. | Sem fluxo de troca de senha; `must_reset_password` não aplicado ainda. |
| **Conta bloqueada** | Se `blocked = true`, só mostra panel depois da senha correta. | entrada: conta bloqueada; saída: erro controlado. | Painel de erro legado, sem fluxo de desbloqueio. |
| **Selecionar personagem** | Ler `wyd.characters` + `wyd.items` para montar `MSG_CNFAccountLogin` (2008 bytes) com slots, stats, equip/cargo, guild e scores. | login autenticado → snapshot de seleção. | Sem mundo; CharacterLogin termina em falha controlada. |
| **Conta demo** | Conta sintética em memória para exercitar o transporte sem banco (`TestAccount` / `Secret123!`). | sem banco → conta demo. | Não é cadastro; só para o PoC. |

---

## 3. Habilidades de personagem

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Carregar personagem** | Ler slot, nome, classe, level, exp, gold, scores (base + atual), equip[16], carry[64], afetos, ShortSkill, mobExtra (parcial). | character_id → estrutura de seleção + inventário. | `raw_mobextra` cresce nessa fase; `SaveCelestial`, `NT`, `KefraTicket` ainda são raw. |
| **Inventário por container** | Equip (slots 0..15), Carry (slots 0..63) e Cargo (slots 0..127) com UUID, sIndex, efeitos, refino/gema. | container + slot → item ou vazio. | Item vazio = `sIndex == 0`, sem UUID de instância no legado; no PostgreSQL o item tem UUID. |
| **Refino empacotado** | Decodificar `EF_SANC` (43) ou faixa 116–125 → nível/gema/pity; preservar efeitos crus para re-derivação. | item → `{refine, gem, pity, effects}`. | Pity sombra > 20 gera aviso; fora de 0..15 gera aviso/rejeição. |
| **Atributos e HP/MP** | Ler `STRUCT_SCORE` (48 bytes) → Level, Ac, Damage, MaxHp/Mp, Hp/Mp, Str/Int/Dex/Con, Special[4]. | character → scores. | `Resist[4]` é `char` assinado; interpretar como sinal, não como unsigned. |
| **Afetos (buffs/debuffs)** | Ler `affect[4][32]` (STRUCT_AFFECT: 8 bytes cada → type, value, level, time). | character → afetos com 만료/tempo. | Time é tick cru; sem interpretação de efeito Server-side nesta fase. |
| **Gold e EXP** | `characters.gold` + `characters.exp`, e `accounts.cargo_gold` para o cargo compartilhado. | character/account → valores. | `gold/EXP` são autoridade server-side; nunca confiar no cliente. |

---

## 4. Habilidades de persistência e ledger

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Importar dump legado** | Dry-run + emissão: decode 7952, detectar 7500–7600 (opt-in), recusar 4294, hashear senha/PIN, gerar UUIDv5 por item, emitir load.sql. | dump → report.json + load.sql. | One-shot, não sincronizador contínuo. |
| **Reconciliação** | Contagem de contas/personagens/itens/ouro/EXP reconciliados com o dump; checks do pacote; avisos e erros. | importação → report.json. | Erros bloqueiam load.sql; avisos não. |
| **Ledger de itens** | `item_ledger` append-only por trigger: cada item importado gera evento `import` com correlation_id = run_id. | carga → ledger. | UPDATE/DELETE/TRUNCATE bloqueados; histórico sobrevive ao item. |
| **Idempotência** | Mesma execução + mesmo manifesto → mesmo run_id, UUIDs e ledger; segunda carga atualiza, não duplica. | repetição → sem duplicação. | Dump diferente no mesmo banco não remove o que sumiu; carregar em banco limpo. |

---

## 5. Habilidades de servidor (brevidade)

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Transporte (Fase 3)** | INITCODE 0x1F11F311, header 12 bytes, framing por Size (12..8192), tabela pKeyWord[512], checksum, MSG_AccountLogin → MSG_CNFAccountLogin. | socket → protocolo. |
| **Pool de banco (Fase 3+)** | Pool PostgreSQL com reconexão, timeout e envenenamento controlado; sem vazar credenciais no log. | connection string → pool saudável. |
| **Autoridade (Fase 4+)** | Recalcular dano, HP/MP, posições, itens; rejeitar ações fora da autoridade; rate limit + replay protection. | ação → decisão server-side. |
| **Bot (Fase 5+)** | Cliente headless autentica, entra no mundo, mantém sessão, executa ações com máquina de estados e A* sem travar o tick. | bot → mundo. |

---

## 6. Limitações e riscos desta fase

- **Sem mundo:** CharacterLogin devolve falha controlada; não há snapshot, spawn nem persistência de sessão.
- **Sem TLS no cliente:** protocolo legado não tem criptografia; o gateway não deve ser exposto à internet sem camada de proteção.
- **Banco sem pool/TLS e com uma conexão:** suficiente para o PoC; pool, reconexão e TLS ficam para a versão de carga.
- **CNF parcial:** `HashKeyTable`, `Keys`, `QuestDiaria`, `BlockPass`, `IsBlocked` e `Unknow_28` (1) zerados; pode ser insuficiente para funcionalidades além da seleção.
- **Dados legados sensíveis:** `out/` contém hashes e dados de conta; não versionar, não compartilhar, não commitar.
- **Sem golden vectors reais:** o gateway é verificado contra o layout documentado, mas sem vetor capturado do cliente não se sabe se o 7662 aceita o que o servidor devolve (especialmente os campos zerados do CNF).

---

## 7. Referências

- `docs/02-PROTOCOLO.md` — transporte, header, codec, structs, login.
- `docs/07-IMPORTACAO.md` — schema, UUID, ledger, conversor, reconciliação, limites.
- `docs/03-DADOS-LEGADOS.md` — STRUCT_ACCOUNTFILE, STRUCT_MOB, STRUCT_ITEM, STRUCT_SCORE, STRUCT_MOBEXTRA.
- `schema/001_init.sql` — DDL com UUID, ledger, triggers e views.
- `importer/` — decoder, hashing, ids, reconcile, emit, __main__.
- `gateway/` — gateway TCP em Rust (Fase 3): transporte + login + PostgreSQL.
- `tests/` — fixtures sintéticos e 82 testes Python; testes Rust em `gateway/tests/`.

