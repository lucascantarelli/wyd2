# 00 — Índice da Especificação

Especificação técnica do WYD 7.xx (build 7662, protocolo 7640) para reconstrução do servidor em stack moderna.

**Versão:** Fase 3 · novembro de 2026
**Escopo:** pesquisa e especificação (Fase 1) + schema PostgreSQL e importador de contas (Fase 2) + gateway PoC de transporte e login de conta (Fase 3). Ainda sem mundo jogável.

---

## 1. Convenções

### 1.1. Níveis de evidência

| Marcador | Significado |
|---|---|
| ✅ | verificado na fonte primária, com `arquivo:linha` |
| 🟡 | derivado de fonte/documento, com inferência declarada |
| ⚠️ | não verificado; hipótese a validar por captura ou teste |
| 🔴 | bloqueante para a fase seguinte |

### 1.2. Referências de código

Formato `arquivo:linha`, relativo a `reference/w2pp-OpenWYD/`:

- `Basedef.cpp` — structs, constantes, fórmulas `BASE_*`
- `CPSock.cpp` / `CPSock.h` — transporte e codec
- `TMSrv/_MSG_*.cpp` — handlers de pacote
- `TMSrv/MobKilled.cpp` — EXP, drop, gold
- `TMSrv/GetFunc.cpp` — parry, receitas de combine
- `DBSrv/CFileDB.cpp` — persistência de contas
- `Basedef.h` — structs de rede e de save, constantes `_MSG_*`

### 1.3. Nomenclatura

| Termo | Significado |
|---|---|
| **TMSrv** | servidor de jogo, fala com o cliente |
| **DBSrv** | servidor de persistência, fala com o TMSrv |
| **BISrv** | billing |
| **Header** | cabeçalho de 12 bytes de todo pacote (exceto handshake e billing) |
| **Type** | opcode + bits de direção |
| **EF_*** | constante de efeito de item (1..127) |
| **sanc** | nível de refino de um item |

---

## 2. Mapa de documentos

| # | Documento | Para quem | O que responde |
|---|---|---|---|
| 01 | [Fontes e Metodologia](01-FONTES-E-METODOLOGIA.md) | arquiteto, líder técnico | O que existe, o que é confiável, o que não existe, como validar, licenciamento |
| 02 | [Protocolo de Rede](02-PROTOCOLO.md) | engenheiro de rede/backend | Como o cliente fala com o servidor, byte a byte |
| 03 | [Dados Legados](03-DADOS-LEGADOS.md) | engenheiro de dados | Como contas, personagens e itens são persistidos; como migrar |
| 04 | [Combate](04-COMBATE.md) | engenheiro de gameplay | Fórmulas de dano, crítico, esquiva e atributos por classe |
| 05 | [Progressão e Refino](05-PROGRESSAO-E-REFINO.md) | engenheiro de gameplay, economia | XP, rebirth, pontos, refino, montarias, drops |
| 06 | [Lacunas e Riscos](06-LACUNAS-E-RISCOS.md) | todos | O que falta, o que pode dar errado, o que decidir |
| 07 | [Importação de Contas](07-IMPORTACAO.md) | engenheiro de dados | Schema, UUID, ledger, conversor, reconciliação e limites |
| 08 | [Cliente Alvo](08-CLIENTE-ALVO.md) | todos | Qual cliente o projeto atende, o que foi medido nele e o que precisa ser revalidado |
| 09 | [Paridade e Changelog](09-PARIDADE.md) | produto, gameplay | Política de paridade, formato da entrada e divergências registradas |

### 2.1. Artefatos

| Caminho | Conteúdo |
|---|---|
| `spec/opcodes.yaml` | 197 opcodes, valor de fio, direção, handler, flag `core` |
| `spec/constants.yaml` | constantes de transporte, limites, combate, progressão, refino |
| `data/xp_mortal_arch.csv` | curva de XP Mortal/Arch |
| `data/xp_celestial.csv` | curva de XP Celestial |
| `data/refine_rates.json` | taxas de refino e combine |
| `data/class_weapon_coefficients.json` | coeficientes classe × arma |
| `scripts/*.py` | extratores reprodutíveis |
| `schema/001_init.sql` | schema PostgreSQL 16 com UUID e ledger |
| `schema/002_catalog.sql` | schema `catalog`: itens, efeitos, skills e views de reconciliação |
| `importer/` | decoder de contas, decoder das tabelas do cliente, catálogo, hashing, reconciliação, emissão e CLI |
| `gateway/` | gateway TCP em Rust: transporte, login e PostgreSQL |
| `tests/` | fixtures sintéticas e 82 testes Python; testes Rust em `gateway/tests/` |

---

## 3. Caminhos de leitura

### 3.1. Para construir o gateway (Fase 3)

1. [02-PROTOCOLO.md](02-PROTOCOLO.md) §1–§7 — transporte, header, codec, structs.
2. [spec/opcodes.yaml](../spec/opcodes.yaml) — valores de fio.
3. [spec/constants.yaml](../spec/constants.yaml) — INITCODE, limites, versão.
4. [06-LACUNAS-E-RISCOS.md](06-LACUNAS-E-RISCOS.md) §2.1 — o que ainda falta.

### 3.2. Para migrar dados (Fase 2)

1. [07-IMPORTACAO.md](07-IMPORTACAO.md) §3 — comandos de dry-run, emissão e carga.
2. [03-DADOS-LEGADOS.md](03-DADOS-LEGADOS.md) §0–§5 — alinhamento, `STRUCT_MOB`, conta.
3. [03-DADOS-LEGADOS.md](03-DADOS-LEGADOS.md) §7 — pipeline de conversão.
4. [06-LACUNAS-E-RISCOS.md](06-LACUNAS-E-RISCOS.md) §2.1 — versões de arquivo não mapeadas.

### 3.3. Para trabalhar contra o cliente real

1. [08-CLIENTE-ALVO.md](08-CLIENTE-ALVO.md) §2 — inventário e canal de atualização.
2. [08-CLIENTE-ALVO.md](08-CLIENTE-ALVO.md) §3 — divergências de tabelas medidas.
3. [08-CLIENTE-ALVO.md](08-CLIENTE-ALVO.md) §6 — ordem para fechar as lacunas.
4. [R02](../roadmap/issues/R02.md) — captura de tráfego e golden vectors.

### 3.4. Para implementar combate (Fase 4)

1. [04-COMBATE.md](04-COMBATE.md) §1–§7 — pipeline e fórmulas.
2. [05-PROGRESSAO-E-REFINO.md](05-PROGRESSAO-E-REFINO.md) §3–§4 — atributos e HP/MP.
3. [data/class_weapon_coefficients.json](../data/class_weapon_coefficients.json) — coeficientes.
4. [04-COMBATE.md](04-COMBATE.md) §9 — lacunas e golden cases.

### 3.5. Para entender o projeto (gestão)

1. [README](../README.md) — visão e roadmap.
2. [01-FONTES-E-METODOLOGIA.md](01-FONTES-E-METODOLOGIA.md) §2 — estado do ecossistema.
3. [06-LACUNAS-E-RISCOS.md](06-LACUNAS-E-RISCOS.md) §7 — perguntas de produto.

---

## 4. Status por área

| Área | Cobertura | Confiança | Pendência principal |
|---|---|---|---|
| Transporte e codec | 100% | alta | golden vectors |
| Catálogo de opcodes | 100% (197) | alta | structs de mensagens secundárias |
| Login/seleção | 100% | alta | captura de tráfego |
| Movimento/ataque | 90% | alta | validação de rota server-side |
| Dano físico | 100% | alta | golden cases |
| Dano mágico/skill | 85% | média-alta | mapear `InstanceType` por skill |
| Crítico | 80% | média | `g_pHitRate` |
| Progressão/XP | 100% | alta | validar ledger no cliente |
| Refino | 95% | alta | tabela efetiva do `SancRate.txt` |
| Drops | 100% | alta | — |
| Persistência | 95% | alta (7952) | contas de 4294; 7500–7600 via zero-padding |
| Gateway/login de conta | 70% | média | `CharacterLogin`, mundo e captura real |
| Cliente alvo (WYD Global) | 55% | média | `SkillData`/`ItemList` decodificados e carregados em `catalog.*`; protocolo e demais `.bin` pendentes |
| Conteúdo (mapas, quests, guerras) | 20% | baixa | fora do escopo da Fase 1 |
| Bots/LLM | 0% | — | Fase 5 |

---

## 5. Regra de ouro

> **Nenhum número sem origem. Nenhuma correção sem registro. Nenhuma inferência disfarçada de fato.**

Se um documento afirma algo sem ✅/🟡/⚠️, isso é um bug de documentação.

---

**Comece por:** [01-FONTES-E-METODOLOGIA.md](01-FONTES-E-METODOLOGIA.md) ou [02-PROTOCOLO.md](02-PROTOCOLO.md).
