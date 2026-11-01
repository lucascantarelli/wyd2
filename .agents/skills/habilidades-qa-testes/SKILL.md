---
name: habilidades-qa-testes
description: "Use quando a tarefa envolver testes ou validação: unitário, integração, e2e, golden vectors, fuzzing, fixtures, análise de relatório e verificação de schema."
metadata:
  category: wyd-next-gen
---

# Habilidades — QA, Testes e Validação (WYD)

> Base para as habilidades de QA: tipos de teste, golden vectors, fuzzing, revisão de relatório, verificação de schema, e validação do dump real.

---

## Quando usar

- Escrever ou ajustar teste unitário, integração, e2e ou fixture.
- Adicionar golden vector, fuzzing ou verificação de schema.
- Investigar falha de teste, regressão ou flakiness.
- Revisar relatório de verificação e critérios de aceite.

## 1. Contexto

O projeto tem testes do importador (82 testes Python), testes Rust no gateway (unitário, e2e, postgres), e verificação de schema (PGlite + PostgreSQL 16 via Docker). A QA continua com golden vectors e fuzzing quando o protocolo alcança cliente real.

---

## 2. Habilidades de teste

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Unitário** | Regras puras: decode, hash, refino, XP, dano. Sem banco, sem rede. | regra → teste. | Sempre. |
| **Integração** | Codificador + decode, round-trip, banco com fixture, credenciais. | componente → teste. | Fase 2/3. |
| **E2E** | Do cliente ao servidor e volta, com framing real. | cliente ↔ servidor → teste. | Fase 3+. |
| **Golden / vetor** | Compara bytes gerados com vetor conhecido (captura ou especificação). | vetor → teste. | Pendente (Fase 3+). |
| **Fuzzing** | Framing malformado/colado; o gateway não panic; timeout e limpeza de sessão. | stream → teste. | Pendente. |

---

## 3. Habilidades de validação

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Revisão de relatório** | Revisão automatizada + humana do report.json; aritmética, limiares, contas sem personagem, códigos de issue, checks do pacote. | report.json → revisão. |
| **Verificar schema** | `pglast` (libpg_query) + execução em PGlite/PostgreSQL 16; constraints, trigger, views, idempotência. | schema → validado. |
| **Validar dump real** | Dry-run no dump real + revisão + carga no PG do provedor + comparação de views; gates de go-live. | dump → validado. |
| **Testar servidor** | Gateway + banco + login + CNF + personagens + equip/cargo; sem vazar credenciais. | gateway + PG → teste. |

---

## 4. Limitações e riscos

- Sem golden vectors reais: o gateway é verificado contra o layout documentado, mas sem vetor capturado do cliente não se sabe se o 7662 aceita o que o servidor devolve.
- Sem fuzzing de framing: o gateway não é testado contra framing malformado/colado nesta fase.
- Sem captura real: os testes provam o layout documentado e o round-trip, mas ainda não comparam com um vetor capturado do cliente.

---

## 5. Referências

- `tests/` — fixtures sintéticos e 82 testes Python.
- `gateway/tests/` — e2e, postgres, fixtures.
- `scripts/review_report.py` — revisão automatizada do relatório.
- `schema/001_init.sql` — DDL com UUID, ledger, triggers e views.
- `importer/` — decoder, hashing, ids, reconcile, emit.

