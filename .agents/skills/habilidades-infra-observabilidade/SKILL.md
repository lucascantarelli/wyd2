---
name: habilidades-infra-observabilidade
description: "Use quando a tarefa envolver infraestrutura ou operação: pool/conexões, reconexão, TLS, rate limit, replay, backups, logs, métricas, tracing, SLOs e resposta a incidentes."
metadata:
  category: wyd-next-gen
---

# Habilidades — Infra, Segurança e Observabilidade (WYD)

> Base para as habilidades de infraestrutura e operação do servidor: pool de banco, reconexão, segurança (hash, TLS, rate limit, replay), persistência, backups, e observabilidade (métricas, logs, traces).

---

## Quando usar

- Mexer em pool/conexão, reconexão, timeout ou resiliência.
- Configurar TLS, rate limit ou proteção contra replay.
- Definir logs, métricas, tracing, SLO ou alerta.
- Planejar backup, restore ou resposta a incidente.

## 1. Contexto

O servidor legado era stateless por conexão, com arquivo plano, sem criptografia de fio, sem rate limit, sem autoridade server-side e sem observabilidade. A stack nova deve trazer isso antes do primeiro login jogável: pool de PostgreSQL com reconexão, hash de senha/PIN, proteção de rede, rate limit, replay protection, e métricas desde o estágio 1.

---

## 2. Habilidades de banco e conexão

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Pool de conexões PostgreSQL** | Pool transiente com `min_connections`, `max_connections`, timeout de idle e de aquisição; saúde periódica (ping/query). | connection string → pool saudável. | Fase 3+; sem TLS de banco nesta fase (NoTls). |
| **Reconexão** | Reconexão automática com backoff exponencial + jitter; detectar conexão envenenada (erro de comunicação, idle timeout). | falha de conexão → reconexão sem perder a pool. | Backoff + jitter documentado; sem retry infinito em falha de auth. |
| **Envenenamento** | Marcar conexão como ruim após erro de protocolo/query; não reutilizar; drenar e recriar. | erro de conexão → pool limpa. | Fase 3+. |
| **Transação e idempotency** | Transação serializável para operações críticas (trade, movimento, itens); `SELECT ... FOR UPDATE` + idempotency key para evitar dupes por corrida/reconexão. | operação crítica → transação segura. | Fase 4+. |

---

## 3. Habilidades de segurança

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Hash de senha/PIN** | Senha/PIN migram para argon2id (ou PBKDF2 fallback); nunca texto plano no banco ou no log; gateway só verifica hash. | login + senha → true/false. |
| **TLS na borda** | O gateway não exposto à internet sem proteção; TLS na borda ou AES-GCM em pacotes sensíveis; protocolo legado sem criptografia real. | socket → proteção. |
| **Rate limit** | Token bucket para burst tolerance; sliding window counters para justiça entre clientes; rate limit por sessão/IP; backpressure. | ação → rate limit. |
| **Replay protection** | Nonce/tick monotônico por sessão; rejeitar repetição fora da janela. | pacote → replay check. |
| **Validação de rota/movimento** | Posição e rota validadas server-side; velocidade máxima, raycast e bloqueios de mapa; não confiar no cliente. | movimento → validação. |

---

## 4. Habilidades de operação

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Backup PostgreSQL** | Backup pontual + WAL; política de retenção; restore testado; plano de recuperação documentado antes do go-live. | banco → backup + DR. |
| **Logs e auditoria** | Eventos de login, movimento, itens, combate e trade auditáveis; PII não em log; retenção definida por política. | evento → log/audição. |
| **Secretos** | Senha/hash/PIN, connection string de produção, chaves de API nunca no repo; no sistema do provedor (secret manager, Workers secrets, etc.). | secret → seguro. |
| **CI/CD** | format + lint + testes; schema versionado; migrações explícitas; rollback documentado antes do go-live. | repo → pipeline. |

---

## 5. Habilidades de observabilidade

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Métricas (gateway)** | Conexões ativas, falhas de handshake, latência de frame, taxa de login por login, erro de banco (sem detalhes do cliente). | gateway → métricas. |
| **Métricas (mundo)** | Tick latency, entidades ativas, sessões, throughput de ataque/movimento, % ações rejeitadas. | mundo → métricas. |
| **Métricas (banco)** | Tempo de query, pool utilization, locks/fails, tamanho de transação. | banco → métricas. |
| **Métricas (bots)** | Sessões de bot, ações/autômato, tempo de resposta da LLM (se houver), taxa de falha de caminho. | bot → métricas. |
| **Teste de carga** | Concurrência real de logins e tick; identificar gargalo antes de deploy; a benchmark que importa é mundo + conexões, não só codec. | carga → gargalo. |
| **OpenTelemetry** | Since estágio 1; traces e métricas de serviço; sem Jaeger distribuído até haver >1 serviço. | serviço → OTel. |

---

## 6. Limitações desta fase

- Pool + reconexão + TLS de banco são Fase 3+; hoje o gateway usa uma conexão `NoTls` protegida por mutex.
- Rate limit e replay protection são posteriores ao gateway básico (Fase 3/4).
- Backup/DR e observabilidade avançada são para quando há servidor jogável e produção.

---

## 7. Referências

- `docs/06-LACUNAS-E-RISCOS.md` §4 — riscos de segurança e correção na stack nova.
- `docs/06-LACUNAS-E-RISCOS.md` §5 — risco de arquitetura e ordem recomendada.
- `gateway/` — gateway TCP em Rust (Fase 3): transporte + login + PostgreSQL.
- `schema/001_init.sql` — DDL com UUID, ledger, triggers e views.
- `importer/` — hashing, ids, reconcile, emit.

