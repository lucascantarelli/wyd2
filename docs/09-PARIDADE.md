# 09 — Política e Changelog de Paridade

**Versão:** 1.0 · 1º de novembro de 2026
**Decisão de origem:** [R01](../roadmap/issues/R01.md) — mapa de decisão por mecânica
**Mapa inicial:** [06-LACUNAS-E-RISCOS.md](06-LACUNAS-E-RISCOS.md) §3 (D1–D12)

---

## 1. Política

O projeto segue **paridade por padrão, endurecimento como flag**, exceto onde a
paridade é insegura. Cada mecânica tem uma decisão explícita — paridade,
endurecimento ou rebalanceamento — e nenhuma decisão vale por omissão.

O mapa inicial é a tabela D1–D12 de [06-LACUNAS-E-RISCOS.md](06-LACUNAS-E-RISCOS.md) §3.
Este documento é o **changelog**: toda divergência que chega ao jogo vira uma
entrada aqui, com motivo, evidência e teste. O mapa diz o que se pretende; o
changelog diz o que foi efetivamente implementado.

> Regra prática: se um jogador consegue perceber a diferença, existe uma entrada.
> Se ninguém consegue perceber, é refatoração e não precisa de entrada.

---

## 2. Quando registrar

Registre uma entrada quando a mudança:

- altera fórmula, valor, timing ou ordem de um comportamento observável;
- corrige um bug do legado que o jogador percebe;
- adiciona uma feature que não existia no legado;
- troca uma decisão de segurança por compatibilidade (ou o contrário).

Não registre refatoração, renomeação ou reorganização interna sem mudança
observável.

---

## 3. Formato da entrada

| Campo | Conteúdo |
|---|---|
| `ID` | `P-001`, `P-002`, … sequencial |
| `Data` | data da entrada (AAAA-MM-DD) |
| `Mecânica` | dano, XP, refino, PvP, cooldown, drops… |
| `Legado` | o que o servidor antigo fazia, com `arquivo:linha` ou doc |
| `Novo` | o que o servidor novo faz |
| `Motivo` | por que divergir (segurança, bug, balanceamento) |
| `Evidência` | teste, golden case ou captura que comprova |
| `Issue` | issue que implementou (R04, R05, R06…) |
| `Flag` | nome da flag de compatibilidade, se houver |

### Template

```markdown
| P-000 | 2026-11-01 | mecânica | comportamento legado | comportamento novo | motivo | teste/doc | R00 | `paridade_x` |
```

---

## 4. Changelog

Nenhuma divergência implementada até **2026-11-01**. As decisões D1–D12 seguem
como mapa em [06-LACUNAS-E-RISCOS.md](06-LACUNAS-E-RISCOS.md) §3 e serão
registradas aqui na medida em que forem implementadas e testadas.

| ID | Data | Mecânica | Legado | Novo | Motivo | Evidência | Issue | Flag |
|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | — |

---

## 5. Relação com as issues

- **R01** decide a política (feito: mapa por mecânica).
- **R04** implementa dano e deve registrar divergências de fórmula.
- **R05** implementa refino/combine e deve registrar off-by-one, pity e taxas.
- **R06** registra endurecimentos de segurança que mudem compatibilidade.
- **R12** valida o dump real; qualquer ajuste de paridade descoberto ali vira
  entrada antes do go-live.

---

## 6. Ligações

- [R01 — decisões de produto](../roadmap/issues/R01.md)
- [06 — lacunas e riscos](06-LACUNAS-E-RISCOS.md) §3
- [05 — progressão e refino](05-PROGRESSAO-E-REFINO.md)
- [04 — combate](04-COMBATE.md)

**Voltar ao índice:** [00-INDICE.md](00-INDICE.md)
