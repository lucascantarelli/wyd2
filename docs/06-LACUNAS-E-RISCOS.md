# 06 — Lacunas, Riscos e Decisões

> **Escopo:** o que ainda não sabemos, o que pode dar errado, e quais decisões precisam ser tomadas antes da Fase 2.
>
> **Legenda:** ✅ verificado · 🟡 derivado · ⚠️ não verificado · 🔴 bloqueante

---

## 1. Matriz de riscos

| # | Risco | Prob. | Impacto | Mitigação |
|---:|---|---|---|---|
| R1 | Reimplementar o protocolo de memória e errar offsets | Alta | 🔴 servidor não conecta | golden vectors + captura real antes de codar |
| R2 | Assumir alinhamento `pack(1)` no save | Alta | 🔴 dados corrompidos na migração | `static_assert` + mapa de padding (§03) |
| R3 | Reimplementar "handshake 0x20D" que não existe | Média | Alto (retrabalho) | correção documentada em §02 |
| R4 | Confundir `rand()%100` com `rand()%115` no refino | Alta | Médio (economia quebrada) | testes de distribuição |
| R5 | Ignorar o off-by-one `sanc+1` | Alta | Médio (refino 1 nível mais fácil) | tabela documentada com deslocamento |
| R6 | Replicar a duplicação de HP sem entender | Média | Alto (balanceamento) | captura de `MSG_UpdateScore` |
| R7 | Confiar em `CurrentHp/Exp` do cliente | Média | 🔴 dupes/cheats | autoridade server-side desde o dia 1 |
| R8 | Migrar senhas em claro | Alta | 🔴 LGPD/segurança | hash na conversão, descarte do plaintext |
| R9 | Escopo de microsserviços cedo demais | Alta | Alto (prazo) | monólito modular primeiro (§5) |
| R10 | Copiar código GPL/decompilado | Média | 🔴 legal | clean-room, `reference/` fora do artefato |
| R11 | Tabelas de XP/refino divergirem da fonte | Média | Médio | extração por script + CI |
| R12 | Perder itens na migração (sem UUID) | Média | 🔴 economia | UUID + reconciliação por personagem |
| R13 | Cliente 7662 não ser o alvo real | Média | Alto | confirmar build/versão antes da Fase 3 |
| R14 | Dependência de um único repositório de referência | Média | Médio | segunda fonte (`wyd748`) para cross-check |

---

## 2. Lacunas técnicas abertas

### 2.1. Bloqueantes para a Fase 2 (protocolo/dados)

| # | Lacuna | Onde | Como fechar |
|---:|---|---|---|
| L1 | Layout de `_AUTH_GAME` (billing, 196 B) | `CPSock.h:88-130` | captura TMSrv↔BISrv |
| L2 | Structs marcadas `(std)`/`(combine)` sem layout completo | `Basedef.h` | leitura handler a handler |
| L3 | `_MSG_UpdateScore` e structs de score | `Basedef.h` | captura + leitura |
| L4 | Contas de 4294 bytes | `CFileDB.cpp` | amostras + Ghidra; o importador detecta e **recusa** 4294 |
| L5 | `BASE_GetFirstKey` (subdiretório da conta) | declarada, não implementada | mais amostras ou binário |
| L6 | `STRUCT_MOBEXTRA` (552 B) campo a campo | `Basedef.h` | ✅ fechado na Fase 2 para ClassMaster/Citizen/Fame/Soul/MortalFace e progressão; `SaveCelestial`/`NT` ficam no raw |

### 2.2. Bloqueantes para a Fase 4 (combate)

| # | Lacuna | Onde | Como fechar |
|---:|---|---|---|
| L7 | `g_pHitRate[1024]` | `Basedef.cpp:5912-5945` | reproduzir a inicialização |
| L8 | Coeficientes de skill por `InstanceType` | `SkillData.csv` | tabelar 24 skills representativas |
| L9 | Efeito de `AttackRun`/`AttackSpeed` no tick | `CMob.cpp`, timers | leitura + captura |
| L10 | Dano de summon/montaria | `pSummonBonus`/`pTransBonus` | leitura + testes |
| L11 | "Absorção" por classe | não encontrada | confirmar que não existe |

### 2.3. Não bloqueantes (conteúdo/eventos)

- Estágios de evolução de montaria.
- Guerra de cidades/Noatun/Kefra (regras completas).
- Quests diárias e recompensas.
- AI de mob e rotas de patrulha.
- Rankings e temporadas.

---

## 3. Decisões de paridade vs. endurecimento

O projeto precisa de uma política explícita. **Decisão da R01 (2026-11-01): mapa por mecânica** — paridade por padrão, endurecimento como flag, exceto onde a paridade é insegura. A política e o changelog ficam em [09-PARIDADE.md](09-PARIDADE.md); a tabela abaixo é o mapa inicial.

| # | Comportamento legado | Opções | Recomendação |
|---:|---|---|---|
| D1 | Checksum não-rejeitante | tolerar vs. rejeitar | **rejeitar** (segurança), com métrica |
| D2 | Senha em texto plano | manter vs. hash | **hash** (obrigatório) |
| D3 | HP possivelmente dobrado | replicar vs. corrigir | **capturar primeiro**; decidir com dado |
| D4 | Off-by-one `sanc+1` | replicar vs. corrigir | **replicar** (paridade), documentar |
| D5 | Âmago sobrescreve linha do PO | replicar vs. corrigir | **corrigir**, com flag de compatibilidade |
| D6 | Sem cooldown de refino | manter vs. adicionar | **adicionar** (anti-macro) |
| D7 | Montarias com bônus único | replicar vs. tabela pretendida | **dados configuráveis**; default de paridade |
| D8 | Curva Celestial com salto de 40M no 199 | replicar vs. suavizar | **replicar**, documentar |
| D9 | `ClientVersion` fixo em 7640 | fixo vs. configurável | **configurável** |
| D10 | SkillDelay `/4` no cliente | usar tabelado vs. efetivo | **efetivo** (senão rejeita ações legítimas) |
| D11 | `Ac *= 3` em PvP | manter vs. revisar | **manter** até haver dados de balanceamento |
| D12 | Bits de crítico invertidos | renomear vs. manter | **manter semântica**, renomear no código novo |

> Cada divergência deve virar uma entrada no changelog de paridade, com teste que a comprove. Sem isso, ninguém sabe se o servidor está "errado igual" ou "certo diferente".

---

## 4. Riscos de segurança

### 4.1. Legado

| Risco | Evidência | Correção na stack nova |
|---|---|---|
| Senha em claro no arquivo e no pacote | `STRUCT_ACCOUNTINFO.AccountPass`, `MSG_AccountLogin` | TLS + hash; nunca logar |
| PIN em claro | `NumericToken[6]` | hash/HMAC |
| Sem criptografia real no fio | `pKeyWord` pública | TLS na borda ou AES-GCM em pacotes sensíveis |
| Cliente autoritativo em HP/EXP/MP | `MSG_Attack` | recalcular tudo |
| Sem rate limit | cooldown de refino comentado | falhas de login já limitadas (10/60 s por IP e conta, `gateway/src/rate_limit.rs`); sessão/movimento segue pendente |
| Sem UUID de item | `STRUCT_ITEM` | UUID + ledger de transações |
| Path traversal no nome de conta | nome vira caminho de arquivo | validar e usar ID interno |

### 4.2. Riscos da stack nova

| Risco | Mitigação |
|---|---|
| Confiar no `session token` do cliente | token opaco, curto, rotacionado; validar no gateway |
| Dupe por corrida em trade | transação serializável + `SELECT ... FOR UPDATE` + idempotency key |
| Dupe por reconexão | estado autoritativo no servidor, não no cliente |
| Replay de pacote | nonce/tick monotônico por sessão |
| Wall/speed hack | validação de rota no servidor + raycast + velocidade máxima |
| DDoS de aplicação | limite de conexões por IP, backpressure, timeout de frame |

---

## 5. Risco de arquitetura: microsserviços cedo demais

O briefing propõe Go/Rust + PostgreSQL + Redis + gRPC + Kafka + Kubernetes + Prometheus + Jaeger desde o início. Para um servidor de WYD, isso é **muito mais infraestrutura do que o problema exige** — e cada peça adiciona um modo de falha.

Ordem recomendada, sem abandonar o objetivo:

| Estágio | O que construir | O que adiar |
|---|---|---|
| 1. Núcleo jogável | gateway + world + auth em **um binário Go**, PostgreSQL, um único processo | Kafka, K8s, gRPC interno, service mesh |
| 2. Escala horizontal | separar gateway (stateless) de world (shard por mapa), Redis para sessão/presença | Kafka ainda |
| 3. Eventos | NATS JetStream (mais simples que Kafka) para analytics/drops | Kafka, se o volume não justificar |
| 4. Observabilidade | Prometheus + OpenTelemetry desde o estágio 1 (barato) | Jaeger distribuído até haver >1 serviço |
| 5. Plataforma | Docker + Compose; K8s só quando houver múltiplos shards e necessidade real | Helm/Terraform prematuros |

**Critério:** cada componente novo precisa de uma pergunta que ele responde melhor que a alternativa simples. "Kafka porque o briefing pediu" não é critério.

### 5.1. Go ou Rust?

| Critério | Go | Rust |
|---|---|---|
| Velocidade de entrega | alta | média |
| Concorrência massiva | excelente (goroutines) | excelente (async), mais complexo |
| Latência de tick | suficiente (µs–ms) | melhor, mas o gargalo é rede/DB |
| Ecossistema de jogos | bom | bom |
| Curva da equipe | baixa | alta |
| Segurança de memória | GC | sem GC |

Recomendação: **Go** para o gateway e serviços, com pontos críticos (codec, pathfinding) isolados e benchmarkados. Rust é justificável se a equipe já o domina; não é justificável só por "performance" num jogo de tick de 100–250 ms.

---

## 6. Gates de fase

### Fase 1 — Pesquisa e especificação (este documento)
- [x] Fontes mapeadas e classificadas
- [x] Protocolo documentado com correções
- [x] Fórmulas de combate verificadas
- [x] Progressão/refino extraídos
- [x] Formatos legados mapeados
- [x] Riscos e lacunas registrados
- [ ] Captura de tráfego real (depende de cliente)

### Fase 2 — Conversores e schema
- [x] `STRUCT_ACCOUNTFILE` de 7952 bytes decodificado
- [x] 4294 recusado explicitamente; 7500–7600 aceitos só com `--allow-padded-legacy` (zero-pad + aviso)
- [x] Schema PostgreSQL com UUID por item e ledger append-only
- [x] Reconciliação por personagem/item/ouro/EXP com bloqueio de `load.sql` em erro
- [x] Hash argon2id/PBKDF2 de senha e PIN; PII forte descartada
- [ ] Layout de 4294 (depende de amostra); 7500–7600 tratado por zero-padding, sem layout próprio
- [x] Catálogo do cliente importado para `catalog.items`/`catalog.skills` (`schema/002_catalog.sql`); o `ItemList.csv` do 7662 segue só validando `sIndex`
- [x] Schema e `load.sql` executados em PGlite (PostgreSQL WASM): constraints, trigger, views e idempotência
- [x] Repetidos em **PostgreSQL 16.15** via Docker (imagem oficial `postgres:16`): 10 violações rejeitadas, views corretas e segunda carga idempotente
- [x] Catálogo carregado no **PostgreSQL 16.15** com o `load_catalog.sql` real (incluindo `\copy`): 4.300 itens, 16.083 efeitos, 248 skills; segunda carga idêntica e full-refresh removeu o item 6499
- [ ] Repetir no PostgreSQL 16 do provedor (extensões e configuração de produção)

### Fase 3 — Gateway PoC
- [x] INITCODE + framing + codec implementados e cobertos por testes de round-trip
- [x] Login de conta + `MSG_CNFAccountLogin` (2008 B) com fixture sintética
- [x] Contas, personagens, equipamento e cargo lidos de `wyd.*` no PostgreSQL 16
- [x] Verificação argon2id/PBKDF2 dos hashes do importador, bloqueio e erro de banco sem vazar detalhes ao cliente
- [x] Teste de integração Docker: schema (001 + 002) + fixture + diretório + dois logins TCP reais + recusa de item fora do catálogo
- [x] Validação de catálogo no login: item_index ausente de `catalog.items` recusa a sessão com erro claro no log (views `missing_items`/`out_of_range_items` seguem para auditoria)
- [ ] Golden vectors de captura real
- [ ] `CharacterLogin` e snapshot do mundo
- [ ] Login e seleção de personagem com cliente real
- [ ] Fuzz de framing sem panic
- [ ] Pool/reconexão de banco e TLS (hoje: uma conexão `NoTls` por processo)

### Fase 4 — Combate
- [ ] `resolve_hit` puro com golden cases
- [ ] Distribuição de dano compatível
- [ ] Refino com pity e off-by-one documentados

### Fase 5 — Bots
- [ ] Cliente headless autentica e entra no mundo
- [ ] LLM responde chat com contexto
- [ ] Máquina de estados + A* sem travar o tick

---

## 7. Perguntas de produto (resolvidas)

Estas eram as perguntas de produto que mudavam o escopo; todas foram resolvidas na R01 em 2026-11-01:

1. ~~**Qual cliente é o alvo?**~~ ✅ **Resolvido:** o alvo é o **WYD Global** (`reference/WYD Global`), não o 7662 documentado. Metade do §02 e os layouts do §03 precisam de contraprova — ver [08-CLIENTE-ALVO.md](08-CLIENTE-ALVO.md).
2. ~~**Paridade ou rebalanceamento?**~~ ✅ **Resolvido:** mapa por mecânica, com paridade por padrão e divergência explícita ([R01](../roadmap/issues/R01.md), [docs/09](09-PARIDADE.md)).
3. ~~**Qual o escopo de conteúdo no MVP?**~~ ✅ **Resolvido:** 1 mapa, 4 classes e refino básico; guerras e castelos ficam para depois do MVP.
4. ~~**Qual o modelo de operação?**~~ ✅ **Resolvido:** pesquisa/comunidade fechada, operação voluntária com Docker/Compose; servidor público exige nova decisão.
5. ~~**Bots são jogadores ou ferramentas?**~~ ✅ **Resolvido:** ferramentas de teste/desenvolvimento, sem interação com humanos nem participação na economia.

---

## 8. Resumo executivo

- Os riscos técnicos são **conhecidos e mitigáveis**: offsets, alinhamento, RNG e autoridade.
- O risco que mais mata projetos assim não é código: é **escopo**. Microsserviços, Kafka e K8s antes de um login funcional é a forma mais cara de falhar.
- As **12 decisões de paridade** seguem o mapa por mecânica da R01; a recomendação está na §3 e o changelog em [09-PARIDADE.md](09-PARIDADE.md).
- O caminho crítico é: captura de tráfego → conversor → gateway → combate → bots. Nessa ordem.

---

**Voltar ao índice:** [00-INDICE.md](00-INDICE.md)
