---
name: habilidades-modelagem-dados
description: "Use quando a tarefa envolver schema ou persistência: tabelas PostgreSQL, UUID determinístico, ledger append-only, conversão de structs legadas, views de reconciliação e integridade de dados."
metadata:
  category: wyd-next-gen
---

# Habilidades — Modelagem de Dados e Persistência (WYD)

> Base para as habilidades de dados: schema PostgreSQL, UUID por item, ledger de transações, conversor STRUCT_ACCOUNTFILE, reconciliação, views de conferência, e persistência de estado do jogo.

---

## Quando usar

- Criar ou alterar tabela, coluna, constraint, índice ou view no schema.
- Projetar UUID determinístico, ledger append-only ou reconciliação.
- Mapear struct legada para o schema ou depurar carga.
- Garantir integridade de contas, personagens e itens.

## 1. Contexto

O servidor legado não tem banco; toda persistência é arquivo plano: um arquivo por conta com `STRUCT_ACCOUNTFILE` (7952 bytes com alinhamento natural MSVC x86), senha em texto plano, e sem identidade única de item. A migração para PostgreSQL traz UUID por item, ledger append-only, triggers de proteção, views de conferência, e persistência ACID — e muda o modo como os dados são lidos e escritos: nunca mais por caminho de arquivo.

---

## 2. Habilidades de schema

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **accounts** | Login canônico, hash de senha/PIN, email, bloqueio, donate, ouro do cargo. | conta → row. | `must_reset_password` não aplicado ainda. |
| **characters** | Per personagem por slot: classe, tier, progressão, scores, campos crus, gold, exp. | character → row. | `raw_mobextra` cresce; campos ainda não modelados ficam no raw. |
| **items** | Instância com UUID, dono, container/slot, sIndex, refino, gema, 3 efeitos. | item → row. | UUID por posição, não por sIndex. |
| **character_affects** | Até 32 afetos por character. | afeto → row. | Time é tick cru. |
| **item_ledger** | Histórico append-only por trigger; UPDATE/DELETE/TRUNCATE bloqueados. | item → ledger. | Sem FK para items por propósito; histórico sobrevive ao item. |
| **import_runs / import_issues** | Trilha da importação; deduplicação por chave natural. | importação → trilha. | Fase 2+. |
| **views** | `character_item_counts` e `account_item_totals` de conferência. | conta/character → contagem. | Fase 2+. |

---

## 3. Habilidades de conversão

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Detectar versão do arquivo** | 7952 aceito; 7500–7600 opt-in (zero-pad + aviso); 4294 recusado. | arquivo → versão. | Layout de 4294 desconhecido; 7500–7600 sem layout próprio. |
| **Decode STRUCT_ACCOUNTFILE** | Alinhamento natural MSVC x86; campos por offset; sem pack(1). | arquivo → structs. | Fase 2+. |
| **Hash de senha/PIN** | Argon2id ou PBKDF2; nunca texto plano no banco ou no log; PIN vazio → NULL. | senha/PIN → hash. | Fase 2+. |
| **UUIDs determinísticos** | Namespace fixo; UUIDv5 por item; reimportar o mesmo dump produz os mesmos UUIDs. | item → UUID. | Mudar namespace quebra idempotência. |
| **Emitir load.sql** | CSV + JSONL + load.sql + report.json; checks do pacote; sem erro → load.sql; com erro → LOAD_BLOCKED.txt. | importação → pacote. | Fase 2+. |

---

## 4. Habilidades de reconciliação

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Contagem** | Contas, personagens, equip/carry/cargo, ouro e EXP reconciliados com a soma do dump. | dump → report.json. |
| **Avisos e erros** | Erros bloqueiam load.sql; avisos não; códigos de issue deduplicados. | importação → issue. |
| **Idempotência** | Mesma execução + mesmo manifesto → mesmo run_id, UUIDs e ledger; segunda carga atualiza, não duplica. | repetição → sem duplicação. |

---

## 5. Limitações e riscos

- Layout de 4294 desconhecido; 7500–7600 sem layout próprio; contas de 7500–7600 exigem opt-in e podem ter campos zerados.
- `STRUCT_MOBEXTRA` completo não modelado: `SaveCelestial`, `NT`, `KefraTicket`, `DayLog` ficam no `raw_mobextra`.
- `sIndex` nunca é identidade de instância; dois itens iguais têm UUIDs diferentes.
- Dump diferente no mesmo banco não remove o que sumiu; carregar em banco limpo.

---

## 6. Referências

- `docs/07-IMPORTACAO.md` — schema, UUID, ledger, conversor, reconciliação, limites.
- `docs/03-DADOS-LEGADOS.md` — STRUCT_ACCOUNTFILE, STRUCT_MOB, STRUCT_ITEM, STRUCT_SCORE, STRUCT_MOBEXTRA.
- `schema/001_init.sql` — DDL com UUID, ledger, triggers e views.
- `importer/` — decoder, hashing, ids, reconcile, emit, __main__.
- `tests/` — fixtures sintéticos e 82 testes Python.

