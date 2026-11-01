---
name: habilidades-arquitetura-design
description: "Use quando a tarefa envolver arquitetura ou estrutura: monólito modular vs multi-shard, limites gateway/jogo/dados, design patterns, contratos, topologia de deploy e quando adotar K8s/Kafka."
metadata:
  category: wyd-next-gen
---

# Habilidades — Arquitetura, Sistema e Design (WYD)

> Base para as habilidades de arquitetura: monólito modular, multi-shard, gateway/web/dados, padrões, estrutura, e as decisões de produto e infra que orientam o sistema.

---

## Quando usar

- Escolher topologia (monólito modular, multi-shard, eventos).
- Definir limites entre gateway, servidor de jogo e dados.
- Revisar design patterns, contratos ou organização de pastas.
- Avaliar quando introduzir K8s, Kafka ou fila.

## 1. Contexto

O servidor legado era um monólito C++ com TCP bruto, arquivos plano, e estado em memória. A stack nova começa com um binário Go (gateway + world + auth) sobre PostgreSQL, e evolui para multi-shard quando necessário. A arquitetura é guiada por paridade com o legado (até onde a documentação permite) e por decisões de produto (R01) e infra (R07).

---

## 2. Habilidades de arquitetura

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Monólito modular** | Gateway + world + auth em um binário Go; PostgreSQL; um processo. | código → binário. | Fase 1-3. |
| **Multi-shard** | Separar gateway (stateless) de world (shard por mapa); Redis para sessão/presença; NATS JetStream para eventos. | shards → escala. | Quando houver necessidade real. |
| **Gateway** | TCP bruto com INITCODE, framing, codec, login, CNF; pool de banco com reconexão; sem vazar credenciais. | socket → Account. | Fase 3. |
| **World** | CharacterLogin, snapshot, movimento com validação, combate, itens, sessão. | character → mundo. | Fase 5+. |
| **Auth** | Login, hash de senha/PIN, sessão curta e rotacionada, rate limit, replay protection. | login → sessão. | Fase 3+. |
| **Persistência** | PostgreSQL com UUID, ledger, triggers, views; nunca mais por arquivo. | dump → banco. | Fase 2+. |

---

## 3. Habilidades de design e padrões

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Clean-room** | Código novo do zero a partir de docs/spec; referência como oráculo, não como base de código. | especificação → implementação. |
| **Paridade por padrão, endurecimento como flag** | O servidor novo se comporta igual ao legado até onde a documentação permite; difere apenas onde a divergência é segura e documentada. | comportamento → decisão. |
| **Sem autoridade delegada ao cliente** | HP, EXP, MP, posições e itens são reconstruídos pelo servidor; o cliente é apresentação. | ação → decisão server-side. |
| **Nenhum número sem origem** | Fórmulas etiquetadas com arquivo:linha ou artefato em data/; inferência vira label 🟡, não fato. | afirmação → evidência. |
| **Tamanho de arquivo** | Limiar 200–250 linhas como sinal; quebrar por responsabilidade; arquivos gerados não cobertos pelo limite manual. | arquivo → limite. |

---

## 4. Limitações e riscos

- Escopo muda o projeto; decisões de produto (R01) e infra (R07) são anteriores à técnica.
- Microsserviços + Kafka + K8s + mesh + Jaeger desde o dia 1 é risco disfarçado de escopo; adiar até haver necessidade real.
- Sem golden vectors reais: o gateway é verificado contra o layout documentado, mas sem vetor capturado do cliente não se sabe se o 7662 aceita o que o servidor devolve.

---

## 5. Referências

- `docs/01-FONTES-E-METODOLOGIA.md` — ecossistema, versões, método de evidência, licenciamento.
- `docs/06-LACUNAS-E-RISCOS.md` §5 — risco de arquitetura e ordem recomendada.
- `README.md` — visão geral, stack alvo, infra.
- `gateway/` — gateway TCP em Rust (Fase 3).
- `schema/001_init.sql` — DDL com UUID, ledger, triggers e views.
- `importer/` — decoder, hashing, ids, reconcile, emit.

