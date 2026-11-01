---
name: habilidades-devops
description: "Use quando a tarefa envolver ambiente, CI/CD, containers, migrations, rollback, secrets, variáveis de ambiente, deploy ou automação de gates de qualidade."
metadata:
  category: wyd-next-gen
---

# Habilidades — DevOps, CI/CD, Ambientes e Secrets (WYD)

> Base para as habilidades de DevOps: ambientes, CI/CD, format + lint + testes, versionamento de schema, rollback, e gestão de secrets.

---

## Quando usar

- Mexer em CI/CD, workflow, cache, artefatos ou matriz de testes.
- Configurar ambiente, containers, migrations ou rollback.
- Gerir secrets e variáveis de ambiente.
- Automatizar gates de fmt, lint, pytest e cargo.

## 1. Contexto

O servidor legado não tinha CI, ambientes, secrets nem rollback. A stack nova traz pipeline desde o início: format + lint + testes, schema versionado, migrações explícitas, e rollback documentado antes do go-live. Os secrets nunca ficam no repo; a connection string e as chaves de API ficam no sistema do provedor.

---

## 2. Habilidades de ambiente

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Dev** | Código rodando local, com banco de demonstração ou PG real via Docker. | código → dev. | Sempre. |
| **Staging** | Validação com dump real ou fixture grande; aproxima produção sem expor produção. | dump/fixture → staging. | Fase 2/3. |
| **Prod** | Servidor jogável com segurança, persistência, observabilidade. | binário + banco → prod. | Quando houver servidor jogável. |

---

## 3. Habilidades de pipeline

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Format + lint** | `cargo fmt/clippy`, `ruff`, `mypy`/`pyright` quando aplicável; rodam no repo, não no fundo do coração de alguém. | código → lint. |
| **Testes** | Unitário + integrazione sintética; integração real com PG opt-in via Docker; teste de carga para mundo + conexões. | código → testes. |
| **Schema** | DDL versionado; migrações explícitas, nunca DDL ad-hoc no prod. | schema → versão. |
| **Build** | Binários versionados com hash de commit quando houver release. | código → binário. |
| **Rollback** | Rollback do schema e do binário documentado antes do go-live. | deploy → rollback. |

---

## 4. Habilidades de secrets

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Secrets fora do repo** | Senha/hash/PIN, connection string de produção, chaves de API nunca no repo; no sistema do provedor (secret manager, Workers secrets, etc.). | secret → seguro. |
| **Sem vazar no log** | Gateway não registra credenciais; mensagens de erro não ecoam a senha; importador não loga texto plano. | sistema → log seguro. |
| **Out/ protegido** | `out/` com hashes e dados de conta não versionar, não compartilhar, não commitar; destruir após carga quando possível. | dump → pacote seguro. |

---

## 5. Limitações desta fase

- Integração real com PG no CI pode ser opt-in via Docker; carga de dump real pode ser pesada e sensível, deixar para staging manual ou pipeline separado.
- Release automático antes de ter um servidor jogável é prematuro.

---

## 6. Referências

- `README.md` — visão geral, stack alvo, infra.
- `docs/06-LACUNAS-E-RISCOS.md` §5 — risco de arquitetura e ordem recomendada.
- `gateway/` — gateway TCP em Rust (Fase 3).
- `schema/001_init.sql` — DDL com UUID, ledger, triggers e views.
- `importer/` — hashing, ids, reconcile, emit.

