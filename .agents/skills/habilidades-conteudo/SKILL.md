---
name: habilidades-conteudo
description: "Use quando a tarefa envolver conteúdo de jogo: catálogo de itens/skills, NPCGener, mapas, loot, guildas, ranking, guerra/castelo, quests e arquivos carregados em runtime."
metadata:
  category: wyd-next-gen
---

# Habilidades — Conteúdo do Jogo (WYD)

> Base para as habilidades de conteúdo: catálogo de itens, skills, NPCs, mapas, guildas, ranking, guerra/castelo, e os arquivos de conteúdo que o servidor legado carrega em runtime.

---

## Quando usar

- Importar ou consultar ItemList, SkillData, NPCGener, mapas ou loot.
- Mexer em guildas, ranking, guerra/castelo ou quests.
- Investigar item ou skill ausente/divergente do cliente.
- Planejar o escopo de conteúdo do MVP.

## 1. Contexto

O servidor legado não tem banco para conteúdo jogável. Tudo é arquivos: CSV/TXT/BIN carregados na inicialização (ItemList, SkillData, NPCGener, mapas, drops), e estado persistente em arquivos de texto (guildas, ranking, cidade/castelo). A fase de conteúdo importa esses arquivos para o novo servidor, com o CSV como fonte de verdade onde existe divergência (ex.: `ItemList.bin` desatualizado em ~23 itens).

---

## 2. Habilidades de catálogo

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **ItemList** | Ler `ItemList.csv` (fonte de verdade): index, Name, mesh/texture, reqs, nUnique, price, nPos, Extra, Grade, efeitos EF_*. | CSV → catálogo. | `ItemList.bin` é XOR 0x5A e desatualizado; usar CSV. |
| **SkillData** | Ler `SkillData.csv` → `STRUCT_SPELL`: SkillPoint, TargetType, ManaSpent, Delay, Range, InstanceType, InstanceValue, TickType, TickValue, AffectType, AffectValue, AffectTime, Act[8], ... | CSV → catálogo de skills. | Mapeamento completo de InstanceType por skill ainda parcial. |
| **NPCGener** | Ler `NPCGener.txt` com blocos chaveados: spawns, patrulha, grupo, etc. | TXT → catálogo de spawns. | Fase 4/5. |
| **Mapas** | `HeightMap.dat` (4096×4096, 1 byte/célula) e `AttributeMap.dat` (1024×1024, 1 byte/célula, razão 4:1). | dat → grid de altura + atributos. | Semântica parcial de AttributeMap; preservar valores brutos. |
| **Outros conteúdos** | `InitItem.csv`, `extraitem.*`, `LevelItem.txt`, `Guard.txt`, `Regions.txt`, `Rates.txt`, `SancRate.txt`, `CompRate.txt`. | arquivos → catálogo. | Fase 4+. |

---

## 3. Habilidades de estado persistente

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Guildas** | `Guilds.txt` + `GuildInfo` (fama, sub-líderes, clã, nível). | TXT → guildas. | Fase 4+. |
| **Ranking** | `Ranking.txt` gerado varrendo `account/`; materializado/view no novo servidor. | TXT → ranking. | Fase 4+. |
| **Cidade/castelo/guerra** | `ChampionCity_*`, `Guild_*`, `Chall_*` por região. | TXT → estado de guerra. | Fase 4+. |
| **Quests diárias** | `QuestDiaria.txt` + `STRUCT_QUEST`. | TXT/quest → recompensas. | Fase 4+. |

---

## 4. Limitações e riscos

- Conteúdo é ~20% coberto na Fase 1; sem mapa jogável, mapas e NPCs não valem especificação avançada.
- Semântica parcial de `AttributeMap`: preservar valores brutos e extrair por inspeção antes de reusar/regerar.
- `ItemList.bin` desatualizado em ~23 itens: usar CSV como fonte de verdade; o bin é de compatibilidade.
- Sem UUID em itens legados: gerar UUID na conversão; nunca reutilizar `sIndex` como identidade.

---

## 5. Referências

- `docs/03-DADOS-LEGADOS.md` §6 — arquivos de conteúdo.
- `reference/w2pp-OpenWYD/Source/Code/Basedef.h` — structs de conteúdo.
- `reference/w2pp-OpenWYD/Release/Common/ItemList.csv` — catálogo de itens (fonte de verdade).
- `reference/w2pp-OpenWYD/Release/TMsrv/run/NPCGener.txt` — spawns.
- `reference/w2pp-OpenWYD/Release/DBSrv/run/ItemList.bin` — binário desatualizado (XOR 0x5A).

