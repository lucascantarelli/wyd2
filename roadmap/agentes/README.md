# Agentes do Projeto WYD Next-Gen

> Descrições de tarefa para os agentes da campanha. Cada agente tem nome, foco, quando usar e o que entrega. Os arquivos de especificação, schema, importer e gateway são a fonte de verdade; os agentes leem esses arquivos e produzem trabalho alinhado a eles.

---

## 🗺️ Como usar

1. **Escolha um agente** pela tabela abaixo ou pela issue associada.
2. **Dê a tarefa** com o arquivo de issue relevante e os arquivos de contexto (schema, importer, gateway, docs).
3. **Revisão**: os agentes produzem trabalho alinhado a `docs/`, `spec/`, `schema/`, `importer/` e `gateway/`; a revisão humana confirma antes de fechar a issue.

---

## 🧰 Agentes

| Agente | Foco | Quando usar | Issue associada |
|---|---|---|---|
| **Transporte/Protocolo** | INITCODE, framing, codec, header, opcodes, login, CNF, structs | Fase 3; captura, vetores, protocolo | R02, R03 |
| **Dados/Importador** | decode, hashing, ids, reconcile, emit, schema, carga, dry-run | Fase 2/3; dump real, carga, validação | R12, R06 |
| **Combate** | resolve_hit, dano físico/mágico, crítico, esquiva, parry, coeficientes | Fase 4; fórmula, golden cases | R04, R05 |
| **Conteúdo** | ItemList, SkillData, NPCGener, mapas, guildas, ranking, guerra | Fase 4+; importação, versionamento | R08 |
| **Bots/IA** | cliente headless, máquina de estados, A*, LLM com contexto | Fase 5; bots autônomos, IA | R09 |
| **Segurança/Infra** | hash, TLS, rate limit, replay, validação de movimento, pool, reconexão, secrets | Transversal; segurança, infra | R06, R07, R13 |
| **Observabilidade** | métricas, OTel, dashboards, teste de carga | Fase 3+; operação, benchmark | R11 |
| **Legal/Operação** | proveniência, licença, LGPD, logs, backup, DR, divulgação | Transversal; legal, operação | R10, R01 |
| **DevOps** | CI/CD, ambientes, format/lint/testes, schema, rollback, secrets | Transversal; pipeline, ambientes | R13 |
| **Arquitetura** | monólito modular, multi-shard, padrões, estrutura, decisões | Transversal; arquitetura, critérios | R07, R01 |
| **QA/Testes** | tipos de teste, golden vectors, fuzzing, revisão, validação | Transversal; teste, validação | R02, R12, R11 |

---

## 📚 Contexto de cada agente

Os agentes devem ler e respeitar:

- `docs/00-INDICE.md` — convenções de evidência e mapa de leitura.
- `docs/02-PROTOCOLO.md` — transporte, header, codec, structs, login.
- `docs/03-DADOS-LEGADOS.md` — STRUCT_ACCOUNTFILE, STRUCT_MOB, STRUCT_ITEM, STRUCT_SCORE, STRUCT_MOBEXTRA.
- `docs/04-COMBATE.md` — dano, crítico, parry, coeficientes.
- `docs/05-PROGRESSAO-E-REFINO.md` — XP, rebirth, atributos, refino, drops.
- `docs/06-LACUNAS-E-RISCOS.md` — riscos, decisões de paridade, gates.
- `docs/07-IMPORTACAO.md` — schema, UUID, ledger, conversor, reconciliação, limites.
- `spec/opcodes.yaml` — 197 opcodes; gerado por script; não editar à mão.
- `spec/constants.yaml` — constantes de transporte, limites, versão.
- `data/*.csv`, `data/*.json` — tabelas extraídas da fonte; versionadas.
- `schema/001_init.sql` — DDL com UUID, ledger, triggers e views.
- `importer/` — decoder, hashing, ids, reconcile, emit, __main__, model, errors, refine, layout, ids, decode, migrate.
- `gateway/` — gateway TCP em Rust (Fase 3): protocolo, server, directory, hashing, postgres_directory, main, lib, Cargo.toml.
- `tests/` — fixtures sintéticos e 82 testes Python; testes Rust em `gateway/tests/`.
- `reference/` — clone da fonte de referência; gitignored, não distribuído; usa como oráculo de especificação, com citação `arquivo:linha`.

---

## 🚦 Regras de agente

1. **Nenhum número sem origem.** O agente cita `arquivo:linha` ou artefato em `data/`; inferência vira label 🟡, não fato.
2. **Clean-room como regra.** O agente não copia código do `reference/`; usa como oráculo de especificação.
3. **Sem secret.** O agente não loga senha/hash/PIN; não vaza connection string; não grava `out/` no repo.
4. **Assertividade > cobertura.** O agente não aceita teste que não falha; cobertura sem assertividade é dívida.
5. **Divergência = decisão.** O agente registra divergências de paridade no changelog de paridade, com teste que a comprove.
6. **Arquivo gerado = script + resultado versionado.** O agente não edita `spec/opcodes.yaml` à mão; deixa o gerador explicar a origem.

---

## 🔗 Ligações

- [roadmap/README.md](../README.md) — visão geral de execução, índice de issues.
- [README.md](../../README.md) — visão geral do projeto, metas, fases, stack alvo.
- [.agents/skills/](../../.agents/skills/) — base de conhecimento por habilidade (SKILL.md descoberta pelo Freebuff).
- [issues/](../issues/) — issues detalhadas (R00–R13).
