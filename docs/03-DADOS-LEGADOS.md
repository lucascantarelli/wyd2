# 03 — Dados Legados e Persistência

> **Escopo:** como o servidor legado guarda contas, personagens, itens e conteúdo; layouts byte-a-byte; estratégia de conversão para PostgreSQL.
>
> **Fonte:** `reference/w2pp-OpenWYD/Source/Code/Basedef.h`, `DBSrv/CFileDB.cpp`, `DBSrv/CRanking.cpp`, `TMSrv/CReadFiles.cpp`, e `docs/migration/data-formats.md`.
>
> **Legenda:** ✅ verificado · 🟡 derivado · ⚠️ não verificado

---

## 0. O modelo de persistência

**Não há banco de dados.** Toda a persistência é feita em arquivos:

- **Conta + personagens:** um arquivo binário por conta. O DBSrv grava o bloco `STRUCT_ACCOUNTFILE` inteiro com `_write()`, sem serialização (`CFileDB.cpp:2469`). É um dump cru de struct C, dependente de compilador e arquitetura.
- **Conteúdo:** CSV/TXT/BIN carregados na inicialização (`ItemList`, `SkillData`, `NPCGener`, mapas, drops).
- **Estado de mundo:** `Guilds.txt`, `Ranking.txt`, `ChampionCity_*`, `Guild_*`, `Chall_*`.

### 0.1. Duas armadilhas que quebram conversores

| Armadilha | Efeito |
|---|---|
| Assumir um único alinhamento | `STRUCT_MOB` tem **816 bytes** com alinhamento natural MSVC x86; com `pack(1)` daria 805. Erro de 11 bytes por personagem desalinha o arquivo inteiro. |
| Assumir um único tamanho de arquivo | Existem contas de **4294**, **7500–7600** e **7952** bytes, de gerações diferentes. É preciso detectar a versão pelo tamanho. |

**Regra:** structs de persistência usam alinhamento natural; structs de rede (`MSG_*`) usam `#pragma pack(push,1)`. Os dois regimes devem ficar isolados em pacotes diferentes no código novo.

### 0.2. Correções ao briefing

| Premissa | Fato |
|---|---|
| `ItemEffect.txt` é um arquivo de dados | `ItemEffect.h` é um **header C++** com as constantes `EF_*` (1..127). Não existe `ItemEffect.txt` neste código. |
| `itemList.bin` é um binário simples | São **6500 registros de 140 bytes, ofuscados com XOR 0x5A**, sem cabeçalho (910.004 bytes = 6500×140 + 4). O `.csv` é a fonte de verdade; o `.bin` está desatualizado em 23 itens. |
| `MobName.txt` é uma lista de nomes de mobs | É uma tabela `chave<TAB>valor` carregada em `g_pEnglish` (`BASE_InitializeMobname`, `Basedef.cpp:5368`), usada para nomes/traduções. |

---

## 1. `STRUCT_MOB` — personagem (816 bytes)

Fonte: `Basedef.h:556-599` ✅

Players e mobs compartilham a mesma struct. Persistida em `Char[4]`.

| Offset | Tam | Campo | Notas |
|---:|---:|---|---|
| 0 | 16 | `MobName[16]` | nome, Latin-1, `_` no lugar de espaço |
| 16 | 1 | `Clan` | clã/raça |
| 17 | 1 | `Merchant` | id de mercador |
| 18 | 2 | `Guild` | `ushort` |
| 20 | 1 | `Class` | 0=TK, 1=FM, 2=BM, 3=HT |
| 21 | (1) | **padding** | alinha `Rsv` em 22 |
| 22 | 2 | `Rsv` | flags de estado |
| 24 | 1 | `Quest` | progresso legado |
| 25 | (3) | **padding** | alinha `Coin` em 28 |
| 28 | 4 | `Coin` | gold carregado |
| 32 | 8 | `Exp` | `long long` |
| 40 | 2 | `SPX` | save point X |
| 42 | 2 | `SPY` | save point Y |
| 44 | 48 | `BaseScore` | `STRUCT_SCORE` |
| 92 | 48 | `CurrentScore` | `STRUCT_SCORE` |
| 140 | 128 | `Equip[16]` | 16 × `STRUCT_ITEM` (8) |
| 268 | 512 | `Carry[64]` | 64 × `STRUCT_ITEM` (8) |
| 780 | 4 | `LearnedSkill` | bitmask (`long` = 4 no Win32) |
| 784 | 4 | `Magic` | poder mágico |
| 788 | 2 | `ScoreBonus` | pontos livres |
| 790 | 2 | `SpecialBonus` | pontos especiais |
| 792 | 2 | `SkillBonus` | pontos de skill |
| 794 | 1 | `Critical` | |
| 795 | 1 | `SaveMana` | |
| 796 | 4 | `SkillBar[4]` | |
| 800 | 1 | `GuildLevel` | |
| 801 | (1) | **padding** | alinha `RegenHP` |
| 802 | 2 | `RegenHP` | |
| 804 | 2 | `RegenMP` | |
| 806 | 4 | `Resist[4]` | fogo/gelo/raio/magia |
| 810 | (6) | **padding final** | struct arredonda para múltiplo de 8 |

**Contrato de verificação** (rodar no build C++ de referência antes de converter):

```cpp
static_assert(sizeof(STRUCT_ITEM)        ==   8);
static_assert(sizeof(STRUCT_SCORE)       ==  48);
static_assert(sizeof(STRUCT_MOB)         == 816);
static_assert(offsetof(STRUCT_MOB, Coin)      ==  28);
static_assert(offsetof(STRUCT_MOB, Exp)       ==  32);
static_assert(offsetof(STRUCT_MOB, BaseScore) ==  44);
static_assert(offsetof(STRUCT_MOB, Equip)     == 140);
static_assert(offsetof(STRUCT_MOB, Carry)     == 268);
static_assert(sizeof(STRUCT_ACCOUNTFILE)      == 7952); // depende de time_t=8
```

> Se `time_t` for 4 bytes (`_USE_32BIT_TIME_T`), `STRUCT_MOBEXTRA` e `STRUCT_ACCOUNTFILE` encolhem. O `static_assert` é a única forma definitiva de fechar o número no build de referência.

---

## 2. `STRUCT_ITEM` — item (8 bytes)

Fonte: `Basedef.h:500-512` ✅

```c
struct STRUCT_ITEM {
    short sIndex;                 // 0 = slot vazio
    struct {
        short stEffect[3];        // 3 pares (cEffect, cValue)
    };
};
```

| Offset | Campo | Bytes |
|---:|---|---:|
| 0 | `sIndex` | 2 |
| 2 | `stEffect[0]` | 2 (`cEffect`, `cValue`) |
| 4 | `stEffect[1]` | 2 |
| 6 | `stEffect[2]` | 2 |

- `sIndex == 0` significa slot vazio. Negativo é inválido.
- `cEffect` é uma constante `EF_*` (1..127); `cValue` é o valor.
- `EF_SANC` (43) carrega o refino **empacotado** com pity/gem — ver [05-PROGRESSAO-E-REFINO.md](05-PROGRESSAO-E-REFINO.md) §6.2.
- Não há UUID, nem timestamp, nem origem. **Esta é a raiz do problema de dupes.**

---

## 3. `STRUCT_SCORE` — atributos (48 bytes)

Fonte: `Basedef.h:524-553` ✅

| Offset | Campo | Tipo |
|---:|---|---|
| 0 | `Level` | `int` |
| 4 | `Ac` | `int` |
| 8 | `Damage` | `int` |
| 12 | `Merchant` | `uchar` |
| 13 | `AttackRun` | `uchar` |
| 14 | `Direction` | `uchar` |
| 15 | `ChaosRate` | `uchar` |
| 16 | `MaxHp` | `int` |
| 20 | `MaxMp` | `int` |
| 24 | `Hp` | `int` |
| 28 | `Mp` | `int` |
| 32 | `Str` | `short` |
| 34 | `Int` | `short` |
| 36 | `Dex` | `short` |
| 38 | `Con` | `short` |
| 40 | `Special[4]` | `short[4]` |

`AttackRun` é dividido em dois nibbles: `AttackRun & 15` = velocidade de corrida; `AttackRun >> 4` = componente de ataque usado no crítico.

---

## 4. Conta: `STRUCT_ACCOUNTINFO` (216 bytes)

Fonte: `Basedef.h:1017-1032` ✅

| Offset | Campo | Tipo | Bytes | Risco |
|---:|---|---|---:|---|
| 0 | `AccountName` | `char[16]` | 16 | |
| 16 | `AccountPass` | `char[12]` | 12 | **texto plano** |
| 28 | `RealName` | `char[24]` | 24 | PII |
| 52 | `SSN1` | `int` | 4 | PII |
| 56 | `SSN2` | `int` | 4 | PII |
| 60 | `Email` | `char[48]` | 48 | PII |
| 108 | `Telephone` | `char[16]` | 16 | PII |
| 124 | `Address` | `char[78]` | 78 | PII |
| 202 | `NumericToken` | `char[6]` | 6 | **PIN em texto plano** |
| 208 | `Year` | `int` | 4 | |
| 212 | `YearDay` | `int` | 4 | |

### 4.1. Dívida de segurança

Senha e PIN são gravados **em claro**. Na migração:

1. Nunca copiar a senha em claro para o PostgreSQL.
2. Migrar com hash forte (argon2id) — a senha original só pode ser hasheada no momento da conversão, e o texto plano deve ser descartado.
3. PIN idem (HMAC/argon2).
4. PII (SSN, endereço, telefone) provavelmente não deve migrar; avaliar retenção mínima e base legal (LGPD).

> Este é o item de conformidade mais sério do projeto. Um dump de contas legado é um vazamento pronto.

---

## 5. `STRUCT_ACCOUNTFILE` — o arquivo de conta (7952 bytes)

Fonte: `Basedef.h:1085-1108` ✅

| Campo | Tipo | Bytes |
|---|---|---:|
| `Info` | `STRUCT_ACCOUNTINFO` | 216 |
| `Char[4]` | `STRUCT_MOB[4]` | 3264 (4 × 816) |
| `Cargo[128]` | `STRUCT_ITEM[128]` | 1024 |
| `Coin` | `int` | 4 |
| `ShortSkill[4][16]` | `uchar` | 64 |
| `affect[4][32]` | `STRUCT_AFFECT[128]` | 1024 |
| `mobExtra[4]` | `STRUCT_MOBEXTRA[4]` | 2208 (4 × 552) |
| `Donate` | `int` | 4 |
| `TempKey[52]` | `char` | 52 |
| `ReceivedItem` | `bool` | 1 (+ padding) |
| `QuestDiaria` | `STRUCT_QUEST` | 56 |
| `BlockPass[16]` | `char` | 16 |
| `IsBlocked` | `bool` | 1 (+ padding) |

Offsets garantidos: `Char` = 216, `Cargo` = 3480, `Coin` = 4504, `affect` = 4572, `mobExtra` = 5600.

### 5.1. Detecção de versão

| Tamanho | Geração | Ação |
|---:|---|---|
| 4294 | muito antiga (sem `affect`/`mobExtra`) | **detectar e recusar** até haver layout verificado |
| 7500–7600 | intermediária | aceitar com `--allow-padded-legacy` (zero-pad até 7952, com aviso) |
| 7952 | atual | layout acima, implementado em `importer/` |

O DBSrv aceita `(7500 <= fsize <= 7600) || fsize == sizeof(STRUCT_ACCOUNTFILE)` (`CRanking.cpp:175`). O conversor detecta os três intervalos: 7952 decodifica direto; 7500–7600 só com `--allow-padded-legacy`, aplicando zero-padding até 7952 e emitindo `legacy_account_zero_padded`; 4294 é recusado com `unsupported_account_version` para **falhar alto** em vez de adivinhar.

### 5.2. Caminho e case-sensitivity

1. `check = strupr(AccountName)`.
2. Rejeita nomes reservados do DOS (`COM0..9`, `LPT0..9`).
3. Subdiretório = primeira letra maiúscula (`account/A/antonio`).
4. Grava o arquivo inteiro a cada save.

Em Windows o filesystem é case-insensitive; em Linux/containers **não**. A migração deve normalizar o nome canônico (por exemplo, lowercase) e indexar por ele, senão `ANTONIO` e `antonio` viram contas distintas — ou colidem.

> ⚠️ `BASE_GetFirstKey` está apenas declarada no header; a implementação não está no código disponível. O comportamento "primeira letra" é inferido de uma amostra real. Confirmar com mais arquivos ou desmontando o binário.

---

## 6. Arquivos de conteúdo

### 6.1. `ItemList.csv` → catálogo de itens

Fonte: `Basedef.cpp:5717` (`BASE_ReadItemListFile`) e `Basedef.h:1162-1185` ✅

Formato: CSV com `index,Name,mesh.texture,reqs,nUnique,price,nPos,Extra,Grade` e depois pares `EF_<nome>,valor`.

```text
1,TransKnight,0.0,0.0.0.0.0,0,0,1,0,0,EF_CLASS,1,EF_RANGE,1,EF_REGENHP,2,...
```

| Coluna (0-based) | Campo |
|---:|---|
| 0 | `index` |
| 1 | `Name` (Latin-1, `_` no lugar de espaço) |
| 2 | `IndexMesh.IndexTexture` |
| 3 | `ReqLvl.ReqStr.ReqInt.ReqDex.ReqCon` |
| 4 | `nUnique` |
| 5 | `Price` |
| 6 | `nPos` — bitmask dos 16 slots de `Equip`; `64|128` = duas mãos; `0` = não equipável |
| 7 | `Extra` |
| 8 | `Grade` (1 Normal, 2 Místico, 3 Arcano, 4 Lendário) |
| 9+ | pares `EF_*,valor` |

**`ItemList.bin`:** 6500 registros × 140 bytes, XOR 0x5A, sem cabeçalho. Layout real: `Name[64] + 8 shorts + 12 pares (short,short) + int Price + 4 shorts` = 140. O `.bin` está desatualizado em 23 itens; **usar o `.csv`**.

### 6.2. `SkillData.csv` → `STRUCT_SPELL`

Fonte: `Basedef.h:1110-1133` ✅

```text
0,24,3,15,3,5,4,5,0,0,0,0,0,10.0.0.10.0.0.0.0,10.0.0.10.0.0.0.0,4,0,1,13,0,3,0,1,Giro_da_Furia
```

Campos: `SkillPoint, TargetType, ManaSpent, Delay, Range, InstanceType, InstanceValue, TickType, TickValue, AffectType, AffectValue, AffectTime, Act[8], ..., Aggressive, MaxTarget, bParty, AffectResist, Passive`.

**`Delay` efetivo no cliente é `Delay / 4`** por causa do `ClientPatch_v7662` (`Hook.cpp:230-231`). O servidor novo deve usar o mesmo valor para não rejeitar ações legítimas. Ver [04-COMBATE.md](04-COMBATE.md) §3.

### 6.3. `NPCGener.txt` — spawns

Blocos `# [n]` com campos:

```text
MinuteGenerate: -1
MaxNumMob:      100
MinGroup/MaxGroup: 4/7
Leader:  Ciclope_Forte
Follower: Ciclope_Forte
RouteType: 2
Formation: 0
StartX/StartY/StartRange/StartWait
DestX/DestY/DestRange/DestWait
```

### 6.4. `MobName.txt` — tabela de nomes/traduções

Formato `chave<TAB>valor` por linha, carregado por `BASE_InitializeMobname` (`Basedef.cpp:5368`) em `g_pEnglish`. Valor truncado em 128 bytes. É uma tabela de strings, **não** a definição de mobs (essas ficam nos arquivos `npc/` no formato `STRUCT_MOB` de 816 bytes).

### 6.5. `ItemEffect.h` — vocabulário de efeitos

Header C++ com `EF_*` de 1 a 127 (`ItemEffect.h:100` para `EF_SANC = 43`, `:94` para `EF_VOLATILE = 38`, `:126` para `EF_NOSANC`). É a "linguagem" dos itens: um item é um `sIndex` + até 3 pares `(EF_*, valor)`.

> Não existe `ItemEffect.txt`. Se o briefing se referia a uma tabela de efeitos, ela é este header.

### 6.6. Outros arquivos

| Arquivo | Formato | Conteúdo |
|---|---|---|
| `InitItem.csv` | CSV | itens iniciais por classe |
| `extraitem.bin` / `.csv` | bin/CSV | itens de cash/evento |
| `ItemDropList.txt` | TXT | relatório gerado pela `DropTool`, não lido em runtime |
| `LevelItem.txt` | TXT | itens por nível |
| `Guard.txt` | TXT | NPCs guarda |
| `Regions.txt` | TXT `x1,y1,x2,y2 = Nome` | regiões nomeadas |
| `Settings/SancRate.txt` | TXT `Família Chave Valor` | taxas de refino |
| `Settings/CompRate.txt` | TXT `Família Chave Valor` | taxas de combine |
| `Guilds.txt` / `Ranking.txt` | TXT | guildas e ranking |
| `ChampionCity_*` / `Guild_*` / `Chall_*` | TXT | estado de guerra/castelo |

### 6.7. Tabelas do cliente alvo (WYD Global)

> As seções 6.1–6.4 descrevem os arquivos do **servidor 7662**. O cliente alvo do projeto
> ([08-CLIENTE-ALVO.md](08-CLIENTE-ALVO.md)) distribui **só** `.bin`, com layout próprio. Esta
> seção registra o layout medido nesses arquivos, decodificado em [importer/client_tables.py](../importer/client_tables.py).

**Transform comum ✅** — payload inteiro em XOR `0x5A`, seguido de um `int32` **cru** (sem XOR),
que é o `nRand` que o escritor do 7662 já anexava (`Basedef.cpp:2739-2755`). Re-encodar o modelo
reproduz o arquivo byte a byte.

| Arquivo | Tamanho | Registros | Registro | Trailer cru |
|---|---:|---:|---:|---:|
| `SkillData.bin` | 25.796 B | 248 | 104 B | 41 |
| `ItemList.bin` | 2.494.004 B | 14.500 | 172 B | 18.467 |

#### 6.7.1. `SkillData.bin` — 248 × 104 B

| Offset | Bytes | Campo | Evidência |
|---:|---:|---|---|
| 0 | 4 | `SkillPoint` (custo) | 🟡 ordem do 7662; faixa 0–350, 45 valores |
| 4 | 4 | `TargetType` | 🟡 faixa 0–6 |
| 8 | 4 | `ManaSpent` | 🟡 faixa 0–800 |
| 12 | 4 | `Delay` | 🟡 faixa 0–1200 |
| 16 | 4 | `Range` | 🟡 faixa 0–13 |
| 20 | 4 | `InstanceType` | 🟡 faixa 0–12 |
| 24 | 4 | `InstanceValue` | 🟡 faixa 0–500 |
| 28 | 4 | `TickType` | 🟡 faixa 0–46 |
| 32 | 4 | `TickValue` | 🟡 faixa 0–160 |
| 36 | 4 | `AffectType` | 🟡 faixa 0–48 |
| 40 | 4 | `AffectValue` | 🟡 faixa 0–255 |
| 44 | 4 | `AffectTime` | 🟡 faixa 0–30 |
| 48 | 8 | `InstanceAttribute[8]` (bytes) | ✅ padrão `v,0,0,v,0,0,0,0`, igual ao grupo pontilhado do CSV do 7662 |
| 56 | 8 | `TickAttribute[8]` (bytes) | ✅ idem |
| 64 | 32 | 8 `int` pós-efeito | 🟡 mesmos valores da cauda do CSV (`4,0,1,13,0,3,0,1`); o 4º nunca passa de 13 (`MAX_TARGET`) |
| 96 | 4 | `SkillIndex` | ✅ 152 valores distintos em 1..248, nenhum repetido; `0` em slot vazio |
| 100 | 4 | flag desconhecida | ⚠️ só assume 0 ou 1 |

➡️ **Diferença para o 7662:** o `STRUCT_SPELL` do 7662 tem 84 B (12 `int` + `Act[8]` + 2 `int` + 5 `int`).
O cliente novo usa 104 B — os atributos viraram dois blocos de 8 bytes, a cauda tem 8 `int` em vez de 7
e existe um `SkillIndex` explícito no fim. Não é o mesmo struct com padding.

#### 6.7.2. `ItemList.bin` — 14.500 × 172 B

| Offset | Bytes | Campo | Evidência |
|---:|---:|---|---|
| 0 | 64 | `Name` — Latin-1, terminado em `\0`, preenchimento `0xFE` | ✅ 4.300 nomes; nenhum sem terminador; maior nome = 39 bytes |
| 64 | 2 | `IndexMesh` | 🟡 faixa 0–3.148 |
| 66 | 2 | `IndexTexture` | 🟡 |
| 68 | 2 | `IndexVisualEffect` | ✅ sempre 0, como o loader do 7662 força (`Basedef.cpp:5770`) |
| 70 | 2 | `ReqLvl` | 🟡 faixa 0–360 |
| 72 | 2 | `ReqStr` | 🟡 |
| 74 | 2 | `ReqInt` | 🟡 |
| 76 | 2 | `ReqDex` | 🟡 |
| 78 | 2 | `ReqCon` | 🟡 |
| 80 | 48 | 12 pares `(sEffect, sValue)`; vazio = `(255, 0)` | ✅ item 1 = `(18,1),(27,1),(47,2),(48,2),(42,10)` + 7 sentinelas; `sEffect` medido em 2..113 e `sValue` em 0..2.000 (não é 0..255) |
| 128 | 4 | `Price` | 🟡 mesma posição do 7662; item 1 = 0 (= CSV), `Steel_Helmet` = 70.000, `Heaven_Of_Staff` = 650.000 |
| 132 | 2 | `nUnique` | 🟡 faixa 0–148 |
| 134 | 2 | `Extra` | 🟡 sempre 0 neste dump |
| 136 | 2 | `nPos` (bitmask de 16 slots) | ✅ potências até 2¹⁵: `Steel_Helmet` = 2, `Heaven_Of_Staff` = 64, `Pure_Divine_Circle` = 8192 |
| 138 | 2 | `Grade` | 🟡 0–2 neste dump (o 7662 documenta 1–4) |
| 140 | 32 | extensão não identificada | ⚠️ ver abaixo |

**Extensão de 32 bytes (+140..+171).** Só parte foi entendida:

| Offset | Bytes | Observação |
|---:|---:|---|
| 140 | 26 | faixa 0–10.000 em `+140`; `+156`/`+158` variam juntos em itens de material; semântica **desconhecida** |
| 168 | 2 | `u16` = id canônico: igual ao índice em 3.868 dos 4.300 registros nomeados; nos outros 432 aponta para o primeiro registro de mesmo nome (variantes `(Ancient)`) ✅ |
| 170 | 2 | sempre 0 |

➡️ **Diferença para o 7662:** o `STRUCT_ITEMLIST` do 7662 tem 140 B. O cliente novo tem 172 B:
o prefixo até `Price` é idêntico em posição; a cauda ganhou 32 bytes e a ordem de `nUnique`/`Extra`/`nPos`/`Grade`
não é mais a do header antigo (lá `nPos` vem antes de `Extra`).

#### 6.7.3. O que ainda não se sabe

1. Semântica dos campos `+64..+92` do skill (os 8 `int` pós-efeito) — só a faixa é conhecida.
2. Significado do flag `+100` do skill.
3. Semântica dos 26 bytes `+140..+165` do item (flags de loja? drop? comércio?).
4. Por que o dump tem 4.300 nomes em 14.500 slots — provável catálogo com reserva por faixa.
5. Se o cliente **lê** `SkillData.bin`/`ItemList.bin` do disco ou recebe esse catálogo do servidor.

> Teste: [tests/test_client_tables.py](../tests/test_client_tables.py) faz round-trip exato nos dois arquivos reais
> (quando `reference/` está presente) e valida tamanhos, contagens, nomes e campos verificados.
>
> Carga no banco: [importer/catalog.py](../importer/catalog.py) emite `items.csv`, `item_effects.csv`,
> `skills.csv` e `load_catalog.sql` idempotente para o schema `catalog`
> ([schema/002_catalog.sql](../schema/002_catalog.sql)). Uso em [07-IMPORTACAO.md](07-IMPORTACAO.md) §3.4.

---

## 7. Estratégia de conversão

### 7.1. Princípios

1. **Conversor one-shot, não leitura em produção.** Ler structs C alinhadas em tempo de execução é frágil e inseguro. Converter uma vez para PostgreSQL, com relatório de divergências.
2. **Versionar por tamanho de arquivo.** Nunca assumir 7952.
3. **Nunca confiar no binário para integridade.** Calcular checksum por conta e por personagem antes/depois.
4. **Preservar IDs legados como `legacy_id`.** `sIndex` de item não é identidade única de instância; o novo modelo precisa de UUID.
5. **Dry-run por padrão.** O conversor produz um relatório (contas lidas, personagens, itens, inconsistências) sem escrever, e só escreve com flag explícita.

### 7.2. Pipeline proposto

```text
1. Inventário        -> listar arquivos de conta, agrupar por tamanho
2. Decode            -> STRUCT_ACCOUNTFILE (layout por versão)
3. Validação         -> campos fora de faixa, sIndex inválido, EXP > int64?, nome vazio
4. Normalização      -> encoding Latin-1 -> UTF-8, nome canônico, trimming
5. Enriquecimento    -> resolver sIndex contra ItemList.csv
6. Emissão           -> JSONL intermediário (auditável) -> COPY para PostgreSQL
7. Verificação       -> recontar itens/gold/EXP por personagem e comparar com o dump
8. Relatório         -> divergências, contas puladas, itens órfãos
```

O passo JSONL intermediário é importante: ele permite revisar sem tocar no banco e serve de artefato de auditoria.

> Implementação: [07-IMPORTACAO.md](07-IMPORTACAO.md). O conversor recusa os layouts não mapeados, hasheia senha/PIN, gera UUIDv5 por item e emite `load.sql` idempotente.

### 7.3. Modelo-alvo mínimo

| Legado | Novo |
|---|---|
| `Info.AccountName/Pass` | `accounts(login, password_hash, ...)` |
| `Char[4]` | `characters(id, account_id, name, class, level, exp, ...)` |
| `Equip[16]` / `Carry[64]` | `items(id UUID, owner_id, container, slot, item_index, refine, ...)` |
| `Cargo[128]` | `items` com `container='cargo'` |
| `Coin` | `characters.gold` / `accounts.cargo_gold` |
| `affect[4][32]` | `character_affects(character_id, type, value, expires_at)` |
| `mobExtra[4]` | `character_progress(...)` |
| `Guilds.txt` | `guilds`, `guild_members` |
| `Ranking.txt` | materialized view / tabela de ranking |

**Regra de ouro:** todo item instanciado recebe um **UUID** no ato da conversão. É o que permite auditoria ponta a ponta e previne dupes (Fase 4 do projeto).

### 7.4. Migração de senhas

1. Ler `AccountPass` em claro.
2. Gerar `argon2id(pass)` e descartar o texto plano **em memória** após o hash.
3. Nunca gravar o texto plano em log, JSONL ou relatório.
4. Forçar reset de senha no primeiro login se a política exigir.

---

## 8. Riscos e lacunas

| Risco | Severidade | Mitigação |
|---|---|---|
| Layout de `STRUCT_MOB` divergente no build de referência | Alta | `static_assert` + comparação com amostra real |
| Contas de 4294 bytes com layout desconhecido | Alta | tratar como geração separada; não adivinhar |
| Senhas/PIN em claro | Crítica | hash na conversão; nunca persistir texto plano |
| `.bin` desatualizado vs `.csv` | Média | usar `.csv` como fonte de verdade |
| `nPos` com sinal (`short`) | Média | interpretar como bitmask, não como índice |
| Encoding Latin-1/cp1252 | Média | converter para UTF-8 com tabela explícita; testar acentos |
| Nomes de arquivo case-sensitive | Média | normalizar e indexar por nome canônico |
| Sem UUID em itens legados | Alta | gerar UUID na conversão; nunca reutilizar `sIndex` como identidade |

### 8.1. O que ainda não foi verificado

- Layout das contas de 4294 bytes; o de 7500–7600 é tratado como prefixo do atual, não como layout próprio.
- Implementação real de `BASE_GetFirstKey`.
- Formato exato de `InitItem.csv`, `extraitem.bin` e `LevelItem.txt`.
- Se `IndexVisualEffect` é realmente sempre zero.

**Verificado na Fase 2:** `STRUCT_MOBEXTRA` (552 bytes), incluindo o padding aninhado — `Arch` em **51** e `Celestial` em **86**, não 52/88 — e `STRUCT_QUEST` (56 bytes). `STRUCT_MOB.Resist[4]` é `char` assinado. O importador preserva `raw_mobextra` para os campos ainda não modelados (`SaveCelestial`, `NT`, `KefraTicket`).

---

## 9. Resumo executivo

- O legado é **file-based e dependente de ABI**. O maior risco não é o volume, é o layout.
- `STRUCT_MOB` = 816 bytes com padding; `STRUCT_ITEM` = 8 bytes sem identidade; a conta = 7952 bytes com senha em claro.
- O caminho correto é um **conversor versionado por tamanho**, com etapa JSONL auditável, UUID por item e hash de senha.
- O modelo-alvo já nasce pronto para ACID, auditoria e anti-dupe — que é exatamente o que o legado não oferece.

---

**Próximo documento:** [01-FONTES-E-METODOLOGIA.md](01-FONTES-E-METODOLOGIA.md) — o que existe no ecossistema, o que é confiável e como validar.
