# Roadmap do Projeto WYD Next-Gen

Documento de execução: issues, agentes e checklist. A visão geral, metas e fases estão em
`README.md` na raiz.

## Como usar este roadmap

1. **Comece pelo README da raiz** para a visão geral, metas, stack alvo e índice de issues.
2. **Escolha uma issue** em `roadmap/issues/` — cada uma tem objetivo, entregáveis, arquivos,
   dependências, checklist, a linha **Skills** e a seção **Skills para executar** com o que
   carregar antes de implementar.
3. **Trabalhe com os agentes** em `roadmap/agentes/` quando a tarefa tem um agente associado.
4. **Atualize o README da raiz** quando uma issue fecha ou um gate de fase avança.
5. **Use as skills** em `.agents/skills/<nome>/SKILL.md` como base de conhecimento: cada
   `SKILL.md` documenta o que a habilidade faz, entradas/saídas, limites e quando usá-la. O
   Freebuff a descobre como `/skill:<nome>`.

## Estrutura

```text
roadmap/
  README.md            visão geral de execução
  issues/              uma issue por ficheiro (R00–R13)
  agentes/             descrições de tarefa para agentes da campanha
.agents/
  skills/<nome>/SKILL.md   skills do projeto (formato Freebuff/Codebuff)
skills/
  README.md            entrada humana para as skills
```

## Índice de issues

| Issue | Título | Tipo | Braço | README da raiz |
|---|---|---|---|---|
| [R00](issues/R00.md) | Padrões de qualidade, tamanho de arquivo e organização | prática | todos | [README.md#r00](../README.md#r00) |
| [R01](issues/R01.md) | Decisões de produto que mudam o escopo | produto | R01 | [README.md#r01](../README.md#r01) |
| [R02](issues/R02.md) | Captura de tráfego real (gateway × cliente) | bloqueante | Fase 3 | [README.md#r02](../README.md#r02) |
| [R03](issues/R03.md) | CharacterLogin + snapshot do mundo | bloqueante | Fase 3/5 | [README.md#r03](../README.md#r03) |
| [R04](issues/R04.md) | Resolução de dano (resolve_hit) + golden cases | bloqueante | Fase 4 | [README.md#r04](../README.md#r04) |
| [R05](issues/R05.md) | Refino e Combine (pity, off-by-one, taxas) | alto | Fase 4 | [README.md#r05](../README.md#r05) |
| [R06](issues/R06.md) | Dívida de segurança e anti-cheat (LGPD, hash, TLS, rate limit, replay, portabilidade) | alto | todos | [README.md#r06](../README.md#r06) |
| [R07](issues/R07.md) | Arquitetura operacional: monólito modular → multi-shard → eventos → K8s | alto | todos | [README.md#r07](../README.md#r07) |
| [R08](issues/R08.md) | Conteúdo de jogo: mapas, quest, loot, guildas, guerra / castelo | médio | Fase 4+ | [README.md#r08](../README.md#r08) |
| [R09](issues/R09.md) | Bots: cliente headless + LLM + máquina de estados | médio | Fase 5 | [README.md#r09](../README.md#r09) |
| [R10](issues/R10.md) | Legal + operação de produção (licenciamento, servidor público, logs, backups, DR) | alto | todos | [README.md#r10](../README.md#r10) |
| [R11](issues/R11.md) | Observabilidade, métricas e testes de carga | prática | Fase 3+ | [README.md#r11](../README.md#r11) |
| [R12](issues/R12.md) | Plano de validação do dump real antes do go-live | alto | Fase 2/3 | [README.md#r12](../README.md#r12) |
| [R13](issues/R13.md) | DevOps, CI/CD, ambientes e secrets | prática | todos | [README.md#r13](../README.md#r13) |

## Fases e percentuais

| Fase | Entrega | Estado | README da raiz |
|---|---|---|---|
| 0. Engenharia reversa | Espaço de problema mapeado | base | [README.md](../README.md) |
| 1. Especificação | Documentação verificada + contratos máquina | ✅ concluída | [README.md](../README.md) |
| 2. Dados | Schema PostgreSQL, conversor, UUID, ledger, reconciliação | ✅ concluída | [README.md](../README.md) |
| 3. Gateway PoC | Transporte + login + PostgreSQL | 🟡 transporte + login | [README.md](../README.md) |
| 4. Combate | resolve_hit + golden cases + dano mágico por skill | pendente | [README.md](../README.md) |
| 5. Mundo + sessão | CharacterLogin + spawn + snapshot + sessão | pendente | [README.md](../README.md) |
| 6. Bots | Cliente headless + LLM + máquina de estados + A* | pendente | [README.md](../README.md) |
| 7+ | Conteúdo, legal, operação de produção | 0–20% | [README.md](../README.md) |

> Percentuais aproximados para comunicação, nunca como métrica de mérito. O projeto mede
> andamento por **issues fechadas** e **gates de fase**.

## Skills do projeto

As skills canônicas ficam em `.agents/skills/<nome>/SKILL.md`, no formato que o
Freebuff/Codebuff descobre automaticamente (frontmatter com `name`, `description` e
`metadata.category`). O diretório `skills/` na raiz é apenas entrada humana.

| Skill | Arquivo | Foco |
|---|---|---|
| Habilidades de conta e personagem | [.agents/skills/habilidades-contas-personagens/SKILL.md](../.agents/skills/habilidades-contas-personagens/SKILL.md) | login, autenticação, seleção, inventário, stats, persistência |
| Habilidades de combate | [.agents/skills/habilidades-combate/SKILL.md](../.agents/skills/habilidades-combate/SKILL.md) | dano físico, mágico, crítico, esquiva, parry, coeficientes, drops |
| Habilidades de infra/observabilidade | [.agents/skills/habilidades-infra-observabilidade/SKILL.md](../.agents/skills/habilidades-infra-observabilidade/SKILL.md) | pool, reconexão, segurança, backups, métricas, OTel |
| Habilidades de conteúdo | [.agents/skills/habilidades-conteudo/SKILL.md](../.agents/skills/habilidades-conteudo/SKILL.md) | itens, skills, NPCs, mapas, guildas, ranking, guerra |
| Habilidades de bots/IA | [.agents/skills/habilidades-bots-ia/SKILL.md](../.agents/skills/habilidades-bots-ia/SKILL.md) | cliente headless, máquina de estados, A*, LLM com contexto |
| Habilidades de legal/operação | [.agents/skills/habilidades-legal-operacao/SKILL.md](../.agents/skills/habilidades-legal-operacao/SKILL.md) | proveniência, licença, LGPD, logs, backup, DR |
| Habilidades de DevOps | [.agents/skills/habilidades-devops/SKILL.md](../.agents/skills/habilidades-devops/SKILL.md) | ambientes, CI/CD, format/lint/testes, schema, rollback, secrets |
| Habilidades de modelagem de dados | [.agents/skills/habilidades-modelagem-dados/SKILL.md](../.agents/skills/habilidades-modelagem-dados/SKILL.md) | schema, UUID, ledger, conversor, reconciliação, views |
| Habilidades de transporte | [.agents/skills/habilidades-transporte/SKILL.md](../.agents/skills/habilidades-transporte/SKILL.md) | INITCODE, framing, codec, pKeyWord, opcodes, gateway |
| Habilidades de migração/massa | [.agents/skills/habilidades-migracao-massa/SKILL.md](../.agents/skills/habilidades-migracao-massa/SKILL.md) | dry-run, emit, carga, reconciliação, verificação de schema |
| Habilidades de QA/testes | [.agents/skills/habilidades-qa-testes/SKILL.md](../.agents/skills/habilidades-qa-testes/SKILL.md) | tipos de teste, golden vectors, fuzzing, revisão, validação |
| Habilidades de balanceamento/economia | [.agents/skills/habilidades-balanceamento-economia/SKILL.md](../.agents/skills/habilidades-balanceamento-economia/SKILL.md) | XP, rebirth, atributos, refino, drops, taxa de combine |
| Habilidades de arquitetura/design | [.agents/skills/habilidades-arquitetura-design/SKILL.md](../.agents/skills/habilidades-arquitetura-design/SKILL.md) | monólito modular, multi-shard, padrões, estrutura, decisões |
| Habilidades de melhores práticas | [.agents/skills/habilidades-melhores-praticas/SKILL.md](../.agents/skills/habilidades-melhores-praticas/SKILL.md) | código limpo, SOLID, padrões, organização, testes, desenvolvimento |

## Critério de fechamento

- Uma issue se fecha quando os **entregáveis** da issue estão entregues e o **checklist**
  está completo.
- Um gate de fase avança quando as issues do gate estão fechadas e a validação do gate foi
  feita.
- Percentuais são aproximados para comunicação; o andamento real é **issues fechadas** e
  **gates de fase**.
