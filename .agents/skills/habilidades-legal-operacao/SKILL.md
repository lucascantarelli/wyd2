---
name: habilidades-legal-operacao
description: "Use quando a tarefa envolver licenciamento, proveniência, LGPD, privacidade, termos, servidor público, auditoria, retenção de logs, backup/DR ou política de divulgação."
metadata:
  category: wyd-next-gen
---

# Habilidades — Legal e Operação (WYD)

> Base para as habilidades de legal, compliance, logs e operação do servidor: proveniência, licenciamento, servidor público, LGPD, logs, auditoria, backup, DR, e política de divulgação.

---

## Quando usar

- Discutir licença, proveniência ou uso de `reference/`.
- Tratar LGPD, PII, retenção ou consentimento.
- Definir política de servidor público, bots ou divulgação.
- Planejar auditoria, backup/DR ou operação.

## 1. Contexto

O servidor legado é de propriedade da HanbitSoft. Os fontes públicos do ecossistema são decompilações/leaks de servidores privados. O repositório de referência é GPLv3, mas a GPL não pode relicenciar o original. O projeto adota clean-room comportamental: a referência é oráculo de especificação, a implementação é escrita do zero a partir de `docs/` e `spec/`, e `reference/` não faz parte do artefato distribuído.

---

## 2. Habilidades de legal

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Proveniência** | Documentar origem de cada fonte usada; citações `arquivo:linha`; clean-room como regra. | fonte → procedência. | Fase 1+; sempre. |
| **Licenciamento** | Nada do repositório de referência entra no artefato distribuído; nada substitui aconselhamento jurídico para operação pública. | projeto → licença. | Sempre. |
| **Servidor público** | Se houver operação pública, aconselhamento jurídico antes de qualquer release; LGPD, retenção, divulgação. | operação → compliance. | Fase 7+. |

---

## 3. Habilidades de operação

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Logs e auditoria** | Eventos de login, movimento, itens, combate e trade auditáveis; PII não em log; retenção definida por política. | evento → log/audição. |
| **Backup + DR** | PostgreSQL com backup pontual + WAL; política de retenção; restore testado; plano de recuperação documentado antes do go-live. | banco → backup + DR. |
| **Divulgação** | UMP, status do servidor, incidentes, política de bots (se houver). | servidor → divulgação. |
| **Segredos** | Senha/hash/PIN, connection string de produção, chaves de API nunca no repo; no sistema do provedor (secret manager, Workers secrets, etc.). | secret → seguro. |

---

## 4. Limitações e riscos

- Nada neste repo substitui aconselhamento jurídico para operação pública.
- PII forte (SSN, endereço, telefone, nome real) não migra para o PostgreSQL.
- `out/` contém hashes e dados de conta; não versionar, não compartilhar, não commitar; destruir após carga quando possível.

---

## 5. Referências

- `docs/01-FONTES-E-METODOLOGIA.md` — ecossistema, versões, método de evidência, licenciamento.
- `docs/06-LACUNAS-E-RISCOS.md` §4 — riscos de segurança e correção.
- `docs/07-IMPORTACAO.md` §8 — segurança do importador.
- `schema/001_init.sql` — DDL com UUID, ledger, triggers e views.
- `importer/` — hashing, ids, reconcile, emit.

