---
name: habilidades-migracao-massa
description: "Use quando a tarefa envolver ETL ou migração: decode do legado, dry-run, geração de pacote, carga idempotente, reconciliação, validação de dump real e go-live."
metadata:
  category: wyd-next-gen
---

# Habilidades — Migração, Massa de Dados e Reconciliação (WYD)

> Base para as habilidades de ETL/migração: dry-run, emit, carga, reconciliação, verificação de schema e loads, e validação do dump real antes do go-live.

---

## Quando usar

- Rodar importação de contas ou catálogo (dry-run, emit, load).
- Investigar contagem divergente, issue de reconciliação ou pacote bloqueado.
- Validar dump real antes do go-live.
- Alterar formato de CSV/SQL gerado pelo importador.

## 1. Contexto

A migração é one-shot: lê um dump legado, produz um pacote auditável e carrega em um banco limpo. Não é um sincronizador contínuo. O pipeline é: discover → size detect → decode → migrate (hash de senha/PIN, PII descartada, UUIDs) → reconcile → emit (CSV + JSONL + load.sql + report.json) → load (staging temporário + ON CONFLICT).

---

## 2. Habilidades de ETL

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Discover** | Lista arquivos regulares, ordem estável, ocultos ignorados. | diretório → arquivos. | Fase 2+. |
| **Size detect** | 7952 aceito; 7500–7600 opt-in (zero-pad + aviso); 4294 recusado. | arquivo → versão. | Fase 2+. |
| **Decode** | STRUCT_ACCOUNTFILE com alinhamento natural MSVC x86; sem pack(1). | arquivo → structs. | Fase 2+. |
| **Migrate** | Senha/PIN → hash; PII descartada; UUIDs determinísticos; never plaintext em log/JSONL/relatório. | structs → MigratedAccount. | Fase 2+. |
| **Reconcile** | Contagens, nomes, classes, refino, ouro, EXP, catálogo; erros bloqueiam, avisos não. | importação → report.json. | Fase 2+. |
| **Emit** | CSV + JSONL + load.sql + report.json; checks do pacote; sem erro → load.sql; com erro → LOAD_BLOCKED.txt. | importação → pacote. | Fase 2+. |

---

## 3. Habilidades de carga e verificação

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **load.sql** | `\copy` relativo ao diretório atual; staging temporário + ON CONFLICT; idempotente. | CSV → banco. |
| **Verificar schema** | `pglast` (libpg_query) + execução em PGlite/PostgreSQL 16; constraints, trigger, views, idempotência. | schema → validado. |
| **Validar dump real** | Dry-run no dump real + revisão automatizada + humana; gate de emissão; carga no PG do provedor; comparação de views. | dump → validado. |

---

## 4. Limitações e riscos

- Dump diferente no mesmo banco não remove o que sumiu; carregar em banco limpo.
- Contas de 7500–7600 exigem opt-in e podem ter campos zerados; 4294 recusado.
- `STRUCT_MOBEXTRA` completo não modelado; `SaveCelestial`, `NT`, `KefraTicket`, `DayLog` ficam no raw.
- `sIndex` nunca é identidade de instância; dois itens iguais têm UUIDs diferentes.

---

## 5. Referências

- `docs/07-IMPORTACAO.md` — schema, UUID, ledger, conversor, reconciliação, limites.
- `importer/` — decoder, hashing, ids, reconcile, emit, __main__.
- `tests/` — fixtures sintéticos e 82 testes Python.
- `schema/001_init.sql` — DDL com UUID, ledger, triggers e views.
- `scripts/review_report.py` — revisão automatizada do relatório.

