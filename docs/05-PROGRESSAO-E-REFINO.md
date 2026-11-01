# 05 — Progressão, Rebirth, Refino e Drops

> **Escopo:** curvas de XP, tiers, pontos de atributo, rebirth, montarias, refino/combine e tabelas de drop.
>
> **Fonte:** `reference/w2pp-OpenWYD/Source/Code/Basedef.cpp`, `TMSrv/MobKilled.cpp`, `TMSrv/_MSG_UseItem.cpp`, `TMSrv/_MSG_CombineItem*.cpp`, `TMSrv/_MSG_ApplyBonus.cpp`, `docs/migration/game-rules.md`.
>
> **Legenda:** ✅ verificado na fonte · 🟡 derivado · ⚠️ não verificado

---

## 0. Resumo

| Tema | Achado principal |
|---|---|
| Cap de nível | **399** para Mortal/Arch, **199** para Celestial/Sub-Celestial (`MAX_LEVEL`/`MAX_CLEVEL`) |
| Curva Mortal/Arch | tabela hardcoded de 597 entradas; nível 399 = **4.000.000.000** de XP acumulado |
| Curva Celestial | **20.000.000 por nível**, linear, com uma descontinuidade real no nível 199 |
| Pontos por nível | Mortal `5/nível` (com modificadores), Arch `6/nível`, Celestial `6/nível` + bônus de rebirth |
| CON e INT | **+2 HP máximo por CON** e **+2 MP máximo por INT** |
| Refino | `rand()%100` no caminho principal; `rand()%115` com fold no combine; tabela indexada com off-by-one |
| Combine +9 → +10 | 2 itens +9 + Pedra do Sábio + joias + 50kk, em Ailyn |
| Montarias | **todas as montarias dão o mesmo bônus** nesta build — os valores por montaria estão comentados |
| Drop | a raridade é do **slot** do inventário do mob, não do item |

---

## 1. Tiers e limites

| Tier (`ClassMaster`) | Faixa de nível | Onde entra |
|---|---|---|
| `MORTAL` | 1–399 | personagem inicial |
| `ARCH` | 1–399 | criado a partir de Mortal |
| `CELESTIAL` | 1–199 | reset de EXP ao criar |
| `CELESTIALCS` | 1–199 + Sub-Celestial | compartilha pontos com Sub-Celestial |
| `SCELESTIAL` | 1–199 + Celestial | espelho do anterior |

`MAX_LEVEL = 399`, `MAX_CLEVEL = 199` (`Basedef.h:177-178`). Para fins de EXP e comparabilidade, o nível "de mundo" de um personagem Celestial é `nível + 400`; o código usa `myLevel += MAX_LEVEL + 1` (`MobKilled.cpp:1280`).

> **Correção ao briefing:** não existe tier "Mortal 1–100". O cap Mortal é 399. Os marcos reais de rebirth são ~300 (criação de Arch), 356+ (criação de Celestial) e os bônus por `ArchLevel` — ver §5.

---

## 2. Curva de XP

### 2.1. Mortal / Arch (`g_pNextLevel`)

Fonte: `Basedef.cpp:625-694` ✅. Tabela completa em [data/xp_mortal_arch.csv](../data/xp_mortal_arch.csv).

| Nível | XP acumulado | XP para o próximo |
|---:|---:|---:|
| 1 | 500 | 624 |
| 10 | 9.260 | 1.633 |
| 50 | 607.895 | 41.820 |
| 100 | 8.123.795 | 336.379 |
| 150 | 29.871.690 | 645.795 |
| 200 | 77.651.770 | 1.333.584 |
| 254 | 180.123.330 | 25.222.560 |
| 299 | 593.702.090 | 19.571.520 |
| 300 | 613.273.610 | 19.571.520 |
| 354 | 2.000.000.000 | 39.000.000 |
| 371 | 2.663.000.000 | 39.000.000 |
| 399 | 4.000.000.000 | 100.000.000 |
| 400 | 4.100.000.000 | 20.000.000 |

Observações:

- A curva **não é suave**: há patamares (254–298, 300–353) e saltos (354, 399). É uma tabela editada manualmente ao longo de anos, não uma fórmula.
- O array é declarado como `[MAX_LEVEL + 202]` (601 posições), mas só tem **597 inicializadores**; os índices 597–600 são zero-inicializados. Qualquer código que indexe acima de 596 lê zero. A stack nova deve tratar o fim da tabela explicitamente.
- Valores acima do nível 400 existem para arenas/eventos e chegam a 8,2 bilhões — acima de `INT32_MAX`. **Armazenar EXP em `int64`**, nunca em `int`.

### 2.2. Celestial / Sub-Celestial (`g_pNextLevel_2`)

Fonte: `Basedef.cpp:696-751` ✅. Tabela completa em [data/xp_celestial.csv](../data/xp_celestial.csv).

A curva é linear: `20.000.000` por nível.

| Nível | XP acumulado |
|---:|---:|
| 1 | 20.000.000 |
| 40 | 800.000.000 |
| 90 | 1.800.000.000 |
| 120 | 2.400.000.000 |
| 150 | 3.000.000.000 |
| 190 | 3.800.000.000 |
| 199 | 4.000.000.000 |

**Anomalia real na fonte:** o valor do índice 199 é `4.000.000.000`, mas o índice 198 é `3.960.000.000` — um salto de 40M onde deveria haver 20M. Não é erro de extração: o literal C está assim. A stack nova deve decidir entre preservar (paridade) ou corrigir (documentado como divergência).

### 2.3. Distribuição de EXP em PvE

Fonte: `MobKilled.cpp:1272-1425` (branch geral). ✅

```text
para cada membro vivo da party dentro de ±HALFGRID:
    isExp = GetExpApply(membro.extra, mob.Exp, membro.Level, mob.Level)
    myLevel = membro.Level
    se membro não é MORTAL nem ARCH: myLevel += 400

    exp = 450 * isExp / (30 + myLevel)
    se exp <= 0 ou exp > 10_000_000: pular recompensa

    exp = aplicar_divisor_do_tier(exp, membro.ClassMaster, myLevel)
    exp = 6 * exp / 10                    # corte fixo de 40%
    se exp > eMob: exp = eMob             # cap no ExpApply do matador
    se 0 < ExpBonus < 500: exp += exp * (ExpBonus + fada) / 100
    se RvR ativo e clã do membro == clã vencedor: exp += exp * 5 / 100
    se servidor newbie e nível < 100: exp += exp / 4
    se DOUBLEMODE: exp *= 2
    se Kefra vivo: exp /= 2
    exp ± 15% conforme NewbieEventServer
    clampar em g_pNextLevel[400]
```

Divisores por tier (`MobKilled.cpp:1286-1356`):

| Mortal: nível ≤ | divide por |
|---:|---:|
| 200 | 1 |
| 300 | 1,07 |
| 356 | 1,25 |
| 370 | 1,70 |
| 380 | 2,10 |
| 390 | 2,60 |
| 399 | 4 |

| Arch: nível ≤ | divide por |
|---:|---:|
| 200 | 1 |
| 300 | 0,85 |
| 356 | 0,90 |
| 360 | 4,50 |
| 370 | 5,90 |
| 380 | 11 |
| 390 | 17 |
| 400 | 35 |

| Celestial+: nível < | divide por |
|---:|---:|
| 120 | 10 |
| 150 | 20 |
| 170 | 40 |
| 180 | 80 |
| 190 | 160 |
| ≥190 | 320 |

> O fator `0,85` do Arch **aumenta** a EXP (divide por menos de 1). É intencional no legado e deve ser preservado ou corrigido explicitamente.

### 2.4. Perda de EXP ao morrer

Fonte: `game-rules.md` §0, derivado de `MobKilled.cpp`. 🟡

- `alpha` = diferença entre o limiar do próximo nível e o atual.
- Perda inicial = `alpha/20`, com divisores crescentes (22, 25, 30, 35, 40, 45, 50, 55, 70, 85, 100) a partir dos níveis 30, 40, 50, 60, 70, 80, 90, 100, 150, 200 e 250.
- Limite de 150.000; multiplicado por 3 se `10 < PKPoint ≤ 25`, por 5 nos demais casos; limite final de 30.000.
- Mortais abaixo do nível 35 são protegidos.

---

## 3. Atributos

### 3.1. Base por classe

Fonte: `BaseSIDCHM[4][6]` (`Basedef.cpp:44-49`) ✅

| Classe | Str | Int | Dex | Con | HP | MP |
|---|---:|---:|---:|---:|---:|---:|
| TransKnight | 8 | 4 | 7 | 6 | 80 | 45 |
| Foema | 5 | 8 | 5 | 5 | 60 | 65 |
| BeastMaster | 6 | 6 | 9 | 5 | 70 | 55 |
| Huntress | 8 | 9 | 13 | 6 | 75 | 60 |

### 3.2. Efeito de cada ponto

Fonte: `_MSG_ApplyBonus.cpp:34-60` ✅

| Ponto em | Efeito imediato |
|---|---|
| Str | `BaseScore.Str += pontos` |
| Int | `BaseScore.Int += pontos` **e** `MaxMp += 2 * pontos` |
| Dex | `BaseScore.Dex += pontos` |
| Con | `BaseScore.Con += pontos` **e** `MaxHp += 2 * pontos` |

Regra de conveniência: se `ScoreBonus >= 300`, um único clique aplica **100 pontos** de uma vez. Isso existe para não exigir 300 pacotes `MSG_ApplyBonus`.

> **Não há bônus de HP/MP por Str ou Dex.** Str e Dex afetam dano via coeficientes de arma (ver [04-COMBATE.md](04-COMBATE.md) §7); Con e Int afetam reservatórios.

### 3.3. Ledger de pontos (`ScoreBonus`)

O servidor não guarda "pontos ganhos por nível" como contador separado: ele **recalcula** o total permitido a partir do nível e do tier e subtrai o que já foi gasto acima da base da classe. Fonte: `BASE_GetScore` (`Basedef.cpp:890-1215`) ✅.

Fórmula geral:

```text
totaluse = (Str + Int + Dex + Con) - soma_da_base_da_classe
ScoreBonus = leveluse - totaluse
```

Se `totaluse > leveluse`, o servidor **remove** os pontos excedentes, na ordem Str → Int → Dex → Con, até fechar. É uma salvaguarda contra edição de personagem.

`leveluse` por tier:

**Mortal**

```text
leveluse = level * 5
se level >= 254: leveluse += (level - 254) * 5
se level >= 299: leveluse += (level - 299) * 10
se level >= 354: leveluse += (level - 354) * -8
```

**Arch**

```text
leveluse = level * 6
leveluse += MortalLevel * 6            # nível mortal congelado na criação
se level >= 354: leveluse += (level - 354) * 6
```

**Celestial**

```text
leveluse = level * 6
leveluse += Arch.Cristal * 100
leveluse += Celestial.Reset * 200
leveluse += 1001
leveluse += bônus_por_ArchLevel        # 1→100, 2→300, 3→600, 4→900, 5→1200
se level >= 120: leveluse += (level - 119) * 6
se level >= 150: leveluse += (level - 149) * 2
se level >= 170: leveluse += (level - 169) * 2
se level >= 180: leveluse += (level - 179) * 2
se level >= 190: leveluse += (level - 189) * 2
```

**Celestial + Sub-Celestial (`CELESTIALCS`)**

```text
leveluse = (fórmula Celestial acima)
leveluse += (SubCelestialLevel * 6) / 2
se SubCelestialLevel >= 120: leveluse += (SubCelestialLevel - 119) * 6
se SubCelestialLevel >= 150: leveluse += (SubCelestialLevel - 149) * 2
... (mesmos thresholds 170/180/190)
```

**Sub-Celestial (`SCELESTIAL`)** usa a mesma estrutura, somando a metade `CelestialLevel`.

> O `1001` base é o mesmo documentado oficialmente para criação de Celestial (ver §5). Aqui ele está **verificado na fonte**, não é estimativa de comunidade.

---

## 4. HP e MP

### 4.1. Ganho por nível

| Classe | HP/nível | MP/nível |
|---|---:|---:|
| TransKnight | 3 | 1 |
| Foema | 1 | 3 |
| BeastMaster | 1 | 2 |
| Huntress | 2 | 1 |

Fonte: `g_pIncrementHp`/`g_pIncrementMp` (`Basedef.cpp:61-62`) ✅.

### 4.2. Quirk de duplicação

Em `BASE_GetCurrentScore` (`Basedef.cpp:3132-3145`), depois de somar os efeitos de item:

```c
int MPDelta = ItemInt * 2;
int HPDelta = ItemCon * 2;

unsigned int mhp = MOB.CurrentScore.MaxHp + HPDelta;
unsigned int mmp = MOB.CurrentScore.MaxMp + MPDelta;

MOB.CurrentScore.MaxHp += mhp;
MOB.CurrentScore.MaxMp += mmp;
```

Isso equivale a `MaxHp = 2*MaxHp + 2*ItemCon`. O trecho está dentro de `if (isSummon == 0)` e não é gated por Soul, apesar de estar na região "Soul Hp/Mp add". **Ou o servidor legado dobra o HP de todo jogador, ou o valor de `CurrentScore.MaxHp` nesse ponto é zero por algum motivo que não foi rastreado.**

⚠️ Não replicar sem validação. É o item de maior risco de paridade deste documento. O caminho correto é capturar o `MSG_UpdateScore` de um personagem recém-criado e comparar MaxHp com a base da classe.

---

## 5. Rebirth (Mortal → Arch → Celestial)

### 5.1. O que a fonte garante

- **Celestial começa no nível 1 com EXP zerada.** A curva `g_pNextLevel_2` parte de 0 e o ledger soma `1001` pontos base.
- **Bônus por nível de Arch congelado** (`ArchLevel`): 100 / 300 / 600 / 900 / 1200 pontos, além de `Arch.Cristal * 100` e `Celestial.Reset * 200`.
- **Sub-Celestial e Celestial compartilham pontos**: o ledger soma `3 * nível do outro lado` e os modificadores de 120/150/170/180/190.
- **Skills são resetadas** na criação do Celestial (documentação oficial 2010, corroborada pelo fluxo de `SaveCelestial` em `_MSG_UseItem.cpp:3219-3234`). 🟡

### 5.2. O que é documentação oficial/community, não fonte

Do FAQ oficial da WYD Global e do patch notes de 2010 (pesquisa desta fase): 🟡

- Mortal precisa de nível ~300–356 para criar Arch (com Pedra da Imortalidade + Sephirot).
- Arch 356+ é o mínimo para criar Celestial.
- Celestial recebe 1001 pontos base + bônus por ArchLevel (100/300/600/900/1200) → **1100 a 2600 pontos**.
- Cythera por faixa de Arch: Silver (356–380), Gold (381–390), Mystic (400), com Def 80/90/110 e Damage Absorb 30/40.
- Ao criar Celestial: capa "Mestre dos Aventureiros", skills resetadas, EXP resetada, Sephira "Limite da Alma" automática, unlocks de nível 40 e 90 refeitos.

> **Divergência a resolver:** a fonte tem `MAX_LEVEL=399`, então "Arch 400" não existe neste build. Os valores de bônus por `ArchLevel` (1..5) são a verdade da fonte; a correspondência `ArchLevel → faixa de nível` (356–370, 371–380, etc.) vem da documentação e precisa ser confirmada no fluxo de criação.

---

## 6. Refino e combine

### 6.1. Onde cada coisa acontece

| Ação | Pacote | Handler | Roll |
|---|---|---|---|
| arrastar poeira sobre equipamento | `0x0373` `_MSG_UseItem` | `Exec_MSG_UseItem` | `rand()%100` |
| combine/anvil (Anct, joias) | `0x03A6` `_MSG_CombineItem` | `Exec_MSG_CombineItem` | `rand()%115` com fold |
| +9 → +10 (Ailyn) | `0x03B5` | `Exec_MSG_CombineItemAilyn` | tabela + joias |
| +10 → +15 (Odin) | `0x02D2`/`0x02E2` | `Exec_MSG_CombineItemOdin` | `g_pOdinRate`/`g_pCelestialRate` |

**O refino com poeira não é um "combine".** Ele vive em `_MSG_UseItem`, que classifica a ação pelo `EF_VOLATILE` da poeira de origem. Isso é uma das confusões mais comuns em reimplementações.

### 6.2. Codificação do nível de refino

O campo `cValue` do efeito `EF_SANC` (efeito 43) **não guarda o nível puro**:

```text
níveis 0..9:   cValue = nível + 10 * pity        # pity 0..20
nível 10:      cValue = 230 + gem
nível 11:      cValue = 234 + gem
nível 12:      cValue = 238 + gem
nível 13:      cValue = 242 + gem
nível 14:      cValue = 246 + gem
nível 15:      cValue = 250 + gem
```

Fonte: `BASE_SetItemSanc` (`Basedef.cpp:2282-2330`) e `BASE_GetItemSanc` (`:2136-2190`) ✅.

Consequências:

- Um item `+5` com 2 falhas de pity guarda `25`, não `5`. Ler `cValue` cru reporta nível errado.
- `BASE_GetItemSanc` faz `% 10` para níveis 0–9 e mapeia as faixas 230–253 para 10–15.
- `BASE_GetItemGem` retorna `(cValue - 230) % 4`, ou seja o tipo de joia usado no +10..+15.

### 6.3. Tabela de sucesso

`BASE_GetSuccessRate(item, OriLacto)` (`Basedef.cpp:2243-2268`) ✅:

```text
se item é ovo (2330..2389): retorna FALSE
se OriLacto não é 0/1/2: retorna FALSE
sanc = BASE_GetItemSanc(item)

se sanc == 10 e OriLacto != 2: return 15
se sanc == 10 e OriLacto == 2: return 100

sanc = sanc % 10
succ = BASE_GetItemSancSuccess(item)          # pity = cValue / 10
rate = g_pSancRate[OriLacto][sanc + 1]        # ATENÇÃO: sanc + 1
rate += succ * g_pSuccessRate[sanc + 1]
return (OriLacto == 2) ? 100 : rate
```

`OriLacto`: 0 = Poeira de Ori (PO), 1 = Poeira de Lac (PL), 2 = Âmago.

**Off-by-one deliberado ou bug:** o índice é `sanc + 1`, então um refino a partir de `+3` lê o slot 4. A tabela compilada (`Basedef.cpp:68-76`) é toda 100; o arquivo `Settings/SancRate.txt` sobrescreve os índices listados. Segundo o documento de referência, o arquivo contém: 🟡

| Linha | +0 | +1 | +2 | +3 | +4 | +5 | +6 | +7 | +8 | +9 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PO | 100 | 100 | 100 | 85 | 70 | 40 | — | — | — | — |
| PL | 100 | 100 | 100 | 100 | 100 | 100 | 80 | 70 | 70 | 10 |
| Âmago | 100 | 80 | 60 | 40 | 20 | 10 | 10 | 10 | 5 | 5 |

Devido ao `+1`, "PO 3 = 85" é a chance do **+2 → +3**, não do +3 → +4. Documentar a tabela sem esse deslocamento produz um servidor 1 nível mais generoso em todos os refinos.

> **Bug histórico do Âmago:** `CReadFiles.cpp:157` grava a linha do Âmago na mesma linha do PO (copy-paste), então no legado o Âmago sobrescrevia o Ori. A referência corrigiu isso (issue #103). A stack nova deve decidir: paridade (Âmago sobrescreve) ou correção (linhas independentes). Recomendação: **corrigir**, com flag de compatibilidade.

### 6.4. Pity

- `g_pSuccessRate[11] = {5,5,5,5,4,4,3,3,2,1,0}` (`Basedef.cpp:122`).
- Cada ponto de pity soma `g_pSuccessRate[nível+1]` à próxima tentativa.
- Uma falha acumula pity com chance 3/4 (`rand()%4 <= 2`): sempre para Lac, apenas até +5 para Ori.
- Um sucesso zera o pity.

### 6.5. Limites

- Itens "tipo 5" (selados) não passam de `sanc >= 9` (`_MSG_UseItem.cpp:227`).
- Outros itens não passam de `sanc >= 6` quando a poeira é Ori (`EF_VOLATILE == 4`, `:203`).
- `EF_NOSANC` (126) bloqueia refino.
- **Não há cooldown anti-spam**: o bloco de 1 segundo está comentado (`_MSG_UseItem.cpp:209-221`). Reativar é uma divergência de endurecimento, não paridade.

### 6.6. Combine (Anct)

Fonte: `_MSG_CombineItem.cpp:46-139` ✅

```text
combine = GetMatchCombine(itens)          # 0 = receita inválida
se combine == 0: erro "Wrong_Combination"

para cada item de entrada: limpar slot e enviar SendItem

_rand = rand() % 115
se _rand >= 100: _rand -= 15              # 100..114 → 85..99
sucesso = (_rand <= combine) ou LOCALSERVER
```

O fold `>= 100 → -15` faz os valores 85–99 serem **duas vezes mais prováveis**. Substituir por `rand()%100` muda a distribuição. O item resultante recebe `sanc = 7` via `BASE_SetItemSanc(..., 7, 0)` e o índice é `joia + g_pItemList[item0].Extra`.

### 6.7. +9 → +10 (Ailyn)

Requisitos (documentação oficial + código): 🟡

- 2 itens iguais em +9;
- 1 Pedra do Sábio;
- 1 a 4 joias idênticas;
- 50.000.000 de gold;
- NPC Ailyn, em Azran.

Bônus das joias: 1 → +4%, 2 → +8%, 3 → +15%, 4 → +32%. Em falha, os dois itens +9 **permanecem**; joias, pedra e gold são consumidos. O resultado recebe `sanc = 10` e o tipo de joia em `gem` (`_MSG_CombineItemAilyn.cpp:120`).

### 6.8. +10 → +15 (Odin)

Duas rotas:

| Rota | Requisitos | Taxa |
|---|---|---|
| Lactolerium | 2 pacotes de 10 poeiras de Lactolerium, item +11+, 4 Pedras Secretas | base 5/3/2/1% para +12/+13/+14/+15 |
| Emblemas de Proteção | 2 Emblemas, item +11+, 4 Pedras Secretas | mesmas bases, mas falha vira cristal de extração em vez de destruir |

Blessed Refine soma: +0 → 2%, +1 → 3%, +2 → 4%, +3 → 5%, +4 → 6%, +5 → 7%, +6 → 8%, +7 → 9%, +8 → 12%, +9 → 15%.

Com 4 blessed refines: 4×+0 → 13/11/10/9%; 4×+9 → 65/63/62/61%. ⚠️ Tabela corroborada por duas fontes de comunidade e pelo FAQ oficial da era 2010, **não** pelo código desta build.

`g_pOdinRate[12] = {100,35,100,40,100,...}` e `g_pCelestialRate[15] = {100,...,70,50,40,40,40,10,5}` são as tabelas compiladas que o handler usa; elas não batem necessariamente com a tabela de comunidade. **A fonte de verdade é a compilada.** Ver [data/refine_rates.json](../data/refine_rates.json).

### 6.9. Combinações de Sephirot (`GetMatchCombine`)

O mesmo handler cobre receitas fixas de itens (não só refino). Exemplos verificados (`GetFunc.cpp:650-680`):

| Receita | Resultado |
|---|---|
| 413 + 2441 + 2442 | Sagacidade (0) |
| 413 + 2443 + 2442 | Resistência (1) |
| 4127 ×3 | Revelação (2) |
| 4127 + 4127 + 697 | Recuperação (3) |
| 412 + 2441 + 2444 | **Absorção** (4) |
| 412 + 2444 + 2443 | Proteção (5) |
| 612 (+9) + 2441 + 2442 | Poder (6) |
| 612 + 613 + 614 + 615 | Armazenagem (7) |
| 614 (+9) + 2443 + 2444 | Precisão (8) |

Isso confirma que "Absorção" é **nome de receita**, não stat de combate.

---

## 7. Montarias

Fonte: `g_pMountBonus[30][5]` (`Basedef.cpp:240-271`) ✅

```c
int g_pMountBonus[30][5] = {
    // AttackAdd, MagicAdd, Evasion, Resistence, Speed
    {750, 110, 80, 32, 6}, // Porco
    {750, 110, 80, 32, 6}, // Javali
    ...
};
```

**Achado:** nesta build, **todas as 30 montarias têm exatamente o mesmo bônus** `{+750 ataque, +110 magia, +80 evasão, +32 resistência, +6 velocidade}`. Os valores diferenciados por montaria estão **comentados** ao lado de cada linha (por exemplo, Dragão vermelho `{750,110,80,32,6}` vs. Pantera negra `{150,10,20,0,6}`). O mesmo vale para `g_pMountTempBonus`.

Interpretação: é um placeholder/bug de balanceamento do servidor de referência. Para o projeto novo há duas opções, e a escolha precisa ser explícita:

1. **Paridade:** replicar o bônus único.
2. **Conteúdo:** usar os valores comentados como tabela pretendida, versionada como dados.

Recomendação: modelar montaria como `(species, tier, bonuses)` em dados, com o valor único como default de paridade e os valores comentados disponíveis para um modo "balanceado".

**Evolução de montaria:** `BASE_GetGrowthRate` lê `g_pSancRate[2][sanc]` para itens 2360–2389 (ovos/evoluções) — ou seja, a mesma tabela do Âmago controla o crescimento. O bloco de incubação está inline no sucesso de `_MSG_UseItem` (`:890`) e usa `EF_INCUBATE`/`EF_INCUDELAY`. ⚠️ O mapeamento completo de estágios não foi levantado nesta fase.

---

## 8. Drops

### 8.1. A raridade é do slot, não do item

Fonte: `Basedef.cpp:222-238` ✅

| Slots do `Carry` do mob | `g_pDropRate` | Leitura |
|---|---:|---|
| 0–7 | 900 | equipamento comum |
| 8–11 | 4 | muito comum (gold/poção) |
| 12–15 | 900 | equipamento comum |
| 16–23 | 20000 | raríssimo |
| 24–47 | 2000 | incomum |
| 48–55 | 3000 | incomum |
| 56 | **1** | sempre dropa |
| 57–63 | 35, 500, 2500, 5000, 5000, 10000, 20000 | cauda de raridade |

`g_pDropBonus[64]` é 100 em todas as posições (neutro). A lógica de roll (`MobKilled.cpp:2758-2800`):

```text
droprate  = g_pDropRate[i]
dropbonus = g_pDropBonus[i] + killer.DropBonus
se dropbonus != 100:
    dropbonus = 10000 / (dropbonus + 1)
    droprate  = dropbonus * droprate / 100

se i < 60 e slot/8 ∈ {0,1,2}:
    ajustar por nível do mob (<10, <20, ...)

# roll final contra rand()
```

> `g_pDropRate` é um **divisor/odds**, não uma porcentagem. Quanto maior, mais raro. Confundir isso inverte todo o balanceamento.

A "loot table" de um mob é o próprio `Carry[64]`. Não existe arquivo separado de drop por mob em runtime; `ItemDropList.txt` é um relatório gerado pela `DropTool.exe`, não uma entrada.

### 8.2. Gold

```text
UNKGOLD = 18
se mob.Level < 10: 2; <20: 4; <30: 6; <50: 9
UNKGOLD = rand() % (UNKGOLD + 1)

se MobCoin != 0 e UNKGOLD == 0:
    MobCoin = 4 * (rand()%(((MobCoin+1)/4)+1) + (MobCoin+1)/4 + MobCoin)
    MobCoin = min(MobCoin, 2000)
    killer.Coin = min(killer.Coin + MobCoin, 2_000_000_000)
```

### 8.3. Drop de evento

Controlado por flags globais (`evOn`, `evItem`, `evRate`, `evStartIndex`, `evEndIndex`). Quando ativo e `rand()%evRate == 0`, o item de evento é gerado com bônus e anunciado globalmente. Vira feature flag na stack nova.

---

## 9. Validação

| Item | Como validar |
|---|---|
| Curva de XP | comparar CSV com `Basedef.cpp` em CI (script já versionado) |
| Ledger de pontos | criar personagem de cada tier e comparar `ScoreBonus` com a fórmula |
| Duplicação de HP | capturar `MSG_UpdateScore` de personagem novo; comparar com a base |
| Refino | 10.000 tentativas por faixa; comparar distribuição e taxa de sucesso |
| Pity | forçar falhas e verificar que o `cValue` cresce de 10 em 10 |
| Combine | validar o fold 100..114 → 85..99 (valores 85–99 devem ter ~2× a frequência dos demais) |
| Drops | 10.000 kills de um mob de teste; comparar taxa por slot |
| Montarias | confirmar bônus único no cliente e decidir paridade vs. conteúdo |

---

**Próximo documento:** [03-DADOS-LEGADOS.md](03-DADOS-LEGADOS.md) — formatos de arquivo e structs de persistência.
