---
name: habilidades-melhores-praticas
description: "Use quando a tarefa envolver qualidade de código: refatoração, SOLID, design patterns, tamanho de arquivo, organização de pastas/testes, revisão de diff e definição de pronto."
metadata:
  category: wyd-next-gen
---

# Habilidades — Melhores Práticas (WYD)

> Base para as habilidades de melhor prática: código limpo, SOLID, design patterns, organização, testes, desenvolvimento, e as decisões de qualidade que orientam o projeto.

---

## Quando usar

- Refatorar código, reduzir arquivo grande ou aplicar SOLID.
- Revisar padrão de nomes, erros, comentários ou formatação.
- Definir organização de pastas/testes ou definição de pronto.
- Revisar PR/diff antes de fechar uma issue.

## 1. Contexto

O projeto adota práticas de código limpo, SOLID, design patterns e organização que se encaixam no tipo de sistema que está sendo construído: servidor de jogo com protocolo legado, persistência PostgreSQL, e bots autônomos. As práticas são guias, não dogmas; o limite de arquivo e a organização de pastas são aplicados de forma consistente, com exceções documentadas.

---

## 2. Habilidades de código limpo

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Nomeação** | Nomes que revelam intenção; sem abreviações obscuras; sem mágica de índice. | código → intenção. |
| **Função pequena** | Função com uma coisa; sem efeito colateral disfarçado; sem parâmetro mágico. | função → propósito. |
| **Sem duplication** | Código que replica lógica é refatorado ou justificado; sem "só por enquanto". | duplicação → refatoração. |
| **Comentário como última alternativa** | Código que precisa de comentário para ser entendido é refatorado; comentário explica por quê, não o quê. | código → clareza. |
| **Sem warning ignorado** | Quando um warning precisa ser suspenso, a razão é registrada no código e no ticket. | warning → justificativa. |

---

## 3. Habilidades de SOLID e padrões

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **S — Responsabilidade única** | Cada módulo/função tem uma razão para mudar; sem módulo que faz transporte + banco + combate + logging indiscriminadamente. | módulo → razão. |
| **O — Aberto/fechado** | Extensão sem modificação do CORE quando possível; ex.: novo container de item, nova skill, novo efeito. | extensão → sem modificação. |
| **L — Substitution** | Subtipos substituíveis; ex.: Directory trait (DemoDirectory ou PostgresDirectory). | trait → implementação. |
| **I — Interface segregada** | Interface pequena e focada; ex.: trait Directory com `find`; sem interface que prometa tudo. | interface → necessidade. |
| **D — Dependência invertida** | Depender de abstração, não de concreto; ex.: protocolo depende de trait, não de PostgreSQL direto. | código → abstração. |
| **Design patterns** | Usar quando resolve um problema real; ex.: strategy para hashing (argon2/PBKDF2), repository para diretório, observer para ledger, command para ações. | problema → padrão. |

---

## 4. Habilidades de organização e testes

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Organização de pastas** | docs/ (especificação), spec/ (contrato), data/ (tabelas), schema/ (DDL), importer/ (ETL), gateway/ (serviço), tests/ (teste), roadmap/ (execução), skills/ (habilidades). | projeto → pasta. |
| **Tamanho de arquivo** | Limiar 200–250 linhas como sinal; quebrar por responsabilidade; arquivos gerados não cobertos pelo limite manual. | arquivo → limite. |
| **Testes** | Unitário (regras puras), integração (componente + banco/fixture), E2E (cliente ↔ servidor), golden/vetor (bytes conhecidos), fuzzing (framing malformado). | código → teste. |
| **Assertividade** | Testar sem poder falhar não é teste; caso o código fique coberto mas o teste nunca rejeite uma alteração quebrada, é dívida de assertividade. | teste → assertividade. |

---

## 5. Habilidades de desenvolvimento

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Formato + lint** | `cargo fmt/clippy`, `ruff`, `mypy`/`pyright` quando aplicável; rodam no repo, não no fundo do coração de alguém. | código → lint. |
| **Git** | Commits com mensagem focada no "porquê"; sem "Update" ou "Fix" sem contexto; sem staging amplo desnecessário. | mudança → commit. |
| **Clean-room** | Código novo do zero a partir de docs/spec; referência como oráculo, não como base de código; nada do reference/ no artefato distribuído. | implementação → clean-room. |
| **Sem secret** | Senha/hash/PIN, connection string de produção, chaves de API nunca no repo; no sistema do provedor; sem vazar no log. | sistema → seguro. |

---

## 6. Limitações e riscos

- Práticas são guias, não dogmas; exceções são documentadas no código ou no ticket.
- Tamanho de arquivo é sinal, não lei; o foco é responsabilidade, não contagem de linhas.
- Assertividade de teste é mais importante que cobertura; um teste que não falha nunca é suficiente.

---

## 7. Referências

- `docs/00-INDICE.md` — convenções de evidência e mapa de leitura.
- `docs/06-LACUNAS-E-RISCOS.md` — riscos, decisões de paridade, gates de fase.
- `README.md` — visão geral, stack alvo, infra, organização de pastas.
- `gateway/` — gateway TCP em Rust (Fase 3).
- `schema/001_init.sql` — DDL com UUID, ledger, triggers e views.
- `importer/` — decoder, hashing, ids, reconcile, emit.
- `tests/` — fixtures sintéticos e 82 testes Python.

