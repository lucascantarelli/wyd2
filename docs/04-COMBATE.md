# 04 — Matemática de Combate

> **Escopo:** fórmulas de dano, acerto, esquiva, crítico e composição de atributos por classe, como implementadas no servidor legado 7.xx.
>
> **Fonte:** `reference/w2pp-OpenWYD/Source/Code/Basedef.cpp`, `TMSrv/_MSG_Attack.cpp`, `TMSrv/GetFunc.cpp`, `TMSrv/CMob.cpp`.
>
> **Legenda:** ✅ verificado na fonte · 🟡 derivado · ⚠️ não verificado

---

## 0. Resumo das descobertas

1. **Não existe "fórmula de dano" única.** O dano é um pipeline de quatro estágios: bônus de atributo → crítico parcial → mitigação por AC → crítico total. Cada estágio tem seu próprio arredondamento.
2. **A mitigação é não-linear.** `BASE_GetDamage` aplica uma escada de pisos que transforma dano negativo em 1–7 pontos, e dano baixo em `5x/4 + 7`. Ignorar a escada muda o balanceamento em níveis baixos.
3. **Acerto e esquiva são um único roll em 1000.** Não há "chance de acerto" separada: `rand()%1000+1 < parryretn` decide se o golpe acerta, e o resultado viaja como `dam = -3` (ou `-4`).
4. **O crítico é invertido em relação à intuição.** O bit `DoubleCritical & 1` (o "crítico total", ×2) vem do roll de *hit rate*; o bit `& 2` (crítico parcial, ×1.3–1.6) vem do atributo `Critical`. Ver §4.
5. **"Absorção" não é um stat de combate no código.** O que existe é `ReflectDamage`/`ReflectPvP` e a escada de AC. "Absorção" aparece como *nome de combinação de Sephirot* (`GetFunc.cpp:666`), não como redução percentual por classe. Ver §6.
6. **Dano mágico é orientado por tabela de skill**, não por uma fórmula geral de INT: `g_pSpell[skill].InstanceValue/AffectValue` + termos por classe + multiplicador de `Magic`. Ver §3.

---

## 1. Pipeline de um golpe corpo a corpo

Fonte: `_MSG_Attack.cpp:440-480` e `:1415-1473`.

```text
para cada alvo i em Dam[]:
    dam = atacante.CurrentScore.Damage

    # (1) crítico parcial
    se DoubleCritical & 2:
        dam = ((rand()%2 + 13) * dam) / 10     # alvo jogador: ×1.3 ou ×1.4
        dam = ((rand()%2 + 15) * dam) / 10     # alvo mob:    ×1.5 ou ×1.6

    # (2) mitigação
    Ac = alvo.CurrentScore.Ac
    se alvo é jogador: Ac *= 3                 # AC de jogador vale 3x em PvP
    dam = BASE_GetDamage(dam, Ac, master)      # master = maestria da arma

    # (3) crítico total
    se DoubleCritical & 1: dam *= 2

    # (4) acerto / esquiva / parry
    attackdex = atacante.Dex / 5
    se atacante.LearnedSkill & 0x1000000: attackdex += 100
    se atacante.Rsv & 0x40:               attackdex += 500
    parryretn = GetParryRate(alvo, alvo.Parry, attackdex, atacante.Rsv)
    se skill ∈ {22, 79}: parryretn = 30 * parryretn / 100
    se rand()%1000 + 1 < parryretn:
        dam = -3
        se alvo.Rsv & 0x200 e rd < 100: dam = -4

    # (5) pós-processamento
    se alvo.Clan == 6 e atacante.Level < 399: dam = 0
    se alvo é mob e dam >= 1: dam += atacante.ForceMobDamage
    se dam >= 1_000_000_000: dam = 1_000_000_000
    Dam[i].Damage = dam
```

Códigos negativos são o protocolo de "errou/bloqueou": o cliente não recebe um booleano, recebe `-3`/`-4` no campo de dano.

### 1.1. Ordem importa

Três detalhes que uma reimplementação ingênua erra:

- **AC é multiplicado por 3 antes da mitigação**, não depois. Em PvP, `Ac = 2000` comporta-se como `Ac = 6000` na fórmula.
- **O crítico parcial entra antes da mitigação**; o total, depois. Por isso um crítico total não é simplesmente "dano × 2" do valor final: ele dobra o valor já mitigado.
- **A esquiva é avaliada depois** de todo o cálculo de dano. O dano é calculado e depois descartado com `-3`; nenhum bônus de dano é reembolsado.

---

## 2. Mitigação: `BASE_GetDamage`

Fonte: `Basedef.cpp:1265-1296` ✅

```c
long long tdam = dam - ac / 2;
combat /= 2;
if (combat > 7) combat = 7;

int delta = 12 - combat;
int rnd = rand() % delta + combat + 99;
tdam = (long long)rnd * tdam / 100;

if (tdam < -50)                  tdam = 0;
else if (tdam >= -50 && tdam < 0) { tdam += 50; tdam /= 7; }
else if (tdam >= 0 && tdam <= 50) { tdam = 5 * tdam / 4; tdam += 7; }

if (tdam <= 0) tdam = 1;
return (int)tdam;
```

| Parâmetro | Significado |
|---|---|
| `dam` | dano bruto do atacante (`CurrentScore.Damage`) |
| `ac` | defesa do alvo (já ×3 em PvP) |
| `combat` | maestria da arma; teto 7 **após** dividir por 2 |
| `rnd` | fator percentual em `[combat+99, 110]` |

Propriedades:

- **AC mitiga metade do valor**: `ac/2`. Não há penetração de armadura.
- **Maestria reduz a variância e eleva o piso**: com `combat = 0`, `rnd ∈ [99,110]` (12 valores); com `combat = 7`, `rnd ∈ [106,110]` (5 valores).
- **A escada de pisos**:
  - `tdam < -50` → 0 (então o piso final leva a 1)
  - `-50 ≤ tdam < 0` → `(tdam + 50) / 7` ∈ [0, 7]
  - `0 ≤ tdam ≤ 50` → `5*tdam/4 + 7` ∈ [7, 69]
  - acima de 50 → passa intacto
- **Dano mínimo é sempre 1**, mesmo com AC absurdamente maior que o ataque.
- A divisão é **inteira com truncamento para zero** (C). Em Python, `//` arredonda para baixo e produz resultados diferentes para negativos; usar `int(a / b)` ou replicar a semântica.

### 2.1. Exemplos resolvidos

| Cenário | Cálculo | Resultado |
|---|---|---|
| `dam=1000, ac=200, combat=4` | `tdam=900`; `combat=2`; `rnd∈[101,110]`; `tdam∈[909,990]` | 909–990 |
| `dam=120, ac=300, combat=0` | `tdam=-30`; `rnd∈[99,110]`; `tdam≈-29..-33`; piso `(21..17)/7` | 2–3 |
| `dam=100, ac=300, combat=2` | `tdam=-50`; piso `0/7=0`; `≤0` → 1 | 1 |
| `dam=60, ac=100, combat=0` | `tdam=10`; `rnd` médio 104; `tdam≈10`; piso `5*10/4+7` | 19 |

O último exemplo mostra o efeito não-linear: 10 de dano bruto viram 19. Isso é intencional no legado e precisa ser preservado se a paridade for o objetivo.

---

## 3. Dano de skill e dano mágico

Há **duas** funções com o mesmo nome:

1. `BASE_GetSkillDamage(dam, ac, combat)` — **mitigação** de skill (`Basedef.cpp:1486`).
2. `BASE_GetSkillDamage(skillnum, mob, weather, weapondamage)` — **cálculo** do dano da skill (`Basedef.cpp:6998`).

O handler chama a segunda para obter o dano e, quando aplicável, a primeira para mitigar (`_MSG_Attack.cpp:557/567`).

### 3.1. Mitigação de skill

```c
int tdam = dam - (ac / 2);
if (combat > 15) combat = 15;

int delta = 21 - combat;
int rnd = rand() % delta + combat + 90;
tdam = (tdam * rnd) / 100;

if (tdam < -50)                tdam = 0;
else if (tdam > -50 && tdam < 0) { tdam += 50; tdam /= 10; }
else if (tdam >= 0 && tdam <= 45) { tdam = 5 * tdam / 4; tdam += 5; }

if (tdam <= 0) tdam = 1;
```

Diferenças em relação ao melee: teto de maestria 15 (não 7), fator `rand()%delta + combat + 90` (90–110 em vez de 99–110), divisor 10 na faixa negativa e piso `5x/4 + 5` até 45.

> **Atenção:** `tdam` aqui é `int`, não `long long`. Com dano acima de ~2,1 bilhões há overflow; na prática o clamp de 1e9 em `_MSG_Attack` protege antes. A stack nova deve usar 64 bits internamente e clampar no mesmo ponto.

### 3.2. Cálculo do dano de skill

Fonte: `Basedef.cpp:6998-7064` ✅

```text
instanceindex = g_pSpell[skillnum].InstanceType
kind          = (skillnum % 24) / 8 + 1       # 1..3 → Special[kind]
special       = CurrentScore.Special[kind]
base          = g_pSpell[skillnum].InstanceValue
affectbase    = g_pSpell[skillnum].AffectValue

se instanceindex == 0:
    # skills especiais com fórmula própria
    11 → special/10 + affectbase
    13 → 3*special/4 + affectbase
    41 → special/25 + 2
    43 → special/3 + affectbase
    44 → 2*(3*special/20 + affectbase)
    45 → special/10 + affectbase

senão se 1 <= instanceindex <= 5:
    skind = skillnum / 8

    skill 97        → 15*level + base
    TK  e skind==1  → 3*weaponDamage + 3*Str + level + special + base
    TK  e skind!=1  → special + base + weaponDamage + level + Int/4 + Int/40
    Foema           → Int/30 + Int/3 + level + base + 2*special
    BeastMaster     → Int/30 + Int/3 + level + base + 2*special
    Huntress        → 3*weaponDamage + 3*Str + level/2 + special + base

    clima == 1 (chuva):  instance 2 → dam = 90*dam/100
                         instance 5 → dam = 130*dam/100
    clima == 2 e instance 3 → dam = 120*dam/100

    se (classe != 0 ou skind != 1) e classe != 3:
        dam = (4*Magic + 100) * dam / 100
    dam = 5*dam/4

senão se instanceindex == 6:  dam = 3*special/2 + base
senão se instanceindex == 11: dam = base
senão:                        dam = Magic

se skillnum == 79: dam = CurrentScore.Damage * 180/100
```

Observações:

- **Foema e BeastMaster compartilham a mesma linha.** A diferença entre elas vem de `Magic` e dos coeficientes de arma em `CurrentScore`, não desta função.
- O multiplicador `(4*Magic + 100)/100` equivale a `1 + Magic/25`. Com `Magic = 100`, é ×5; com `Magic = 200`, ×9. Depois vem o ×1.25 fixo. É aqui que o poder mágico explode em níveis altos — e é o principal risco de balanceamento.
- **`Magic` é composto em `BASE_GetCurrentScore`** (`Basedef.cpp:4729`): parte de `(EF_MAGIC + EF_MAGICADD + 1)/4` e recebe bônus por classe/arma (ver §5.2).
- O clima altera o dano elemental em ±10–30%. Isso é estado de mundo, não do atacante: a stack nova precisa propagar clima no contexto de resolução.
- `skillnum == 79` ignora toda a fórmula e usa `CurrentScore.Damage × 1.8`. É uma exceção deliberada.

---

## 4. Crítico

### 4.1. Como os bits são produzidos

Fonte: `BASE_GetDoubleCritical` (`Basedef.cpp:6122-6181`) ✅

```text
hitvalue[0] = 100 * ((CurrentScore.AttackRun >> 4) - 5)
hitvalue[1] = Critical

value = g_pHitRate[cProgress]            # tabela de 1024 entradas, inicializada em runtime

bit 0 = (value < hitvalue[0])
bit 1 = (rand() % 255 < hitvalue[1])

DoubleCritical = bit0 | (bit1 << 1)
```

- `Critical = BASE_GetMobAbility(EF_CRITICAL) / 4` (`Basedef.cpp:3209`), com bônus para TransKnight: `criticaladd = ((special3+1)/10) + Dex/75`, mínimo 4 (`:3348-3355`).
- `g_pHitRate` é preenchida em runtime (`Basedef.cpp:5912-5945`), não é uma tabela estática.

### 4.2. Como os bits são consumidos

| Bit | Condição no ataque | Efeito | Fonte |
|---|---|---|---|
| `& 1` (bit 0) | roll de hit rate | `dam *= 2` — **crítico total** | `_MSG_Attack.cpp:480` |
| `& 2` (bit 1) | roll de `Critical` | ×1.3–1.4 (jogador) / ×1.5–1.6 (mob) — **crítico parcial** | `:447-449` |

> **Quirk crítico de paridade:** o nome "DoubleCritical" sugere que o bit 1 é o crítico principal, mas é o bit 0 que dobra o dano. Reproduzir a nomenclatura do legado é aceitável; **trocar a semântica dos bits não é**.

### 4.3. Chance efetiva

- Crítico parcial: `P ≈ Critical / 255`, com `Critical` tipicamente em dezenas → poucos por cento por golpe.
- Crítico total: depende de `g_pHitRate[cProgress]`, que é atualizada a cada golpe e não é um valor fixo por personagem. É um sistema de "progresso" (provavelmente para suavizar streaks), não um `if rand() < crit`.

**Não existe um multiplicador único de crítico.** Qualquer documentação que afirme "crítico = 2x" está descrevendo apenas o bit 0.

---

## 5. Acerto, esquiva e parry

### 5.1. `GetParryRate`

Fonte: `GetFunc.cpp:686-725` ✅

```text
add = clamp(alvo.Parry, 0, 100)

targetdex = alvo.CurrentScore.Dex
se targetdex > 1000: targetdex = 1000

parryrate1 = alvo.Dex - 1000; clamp(0, 2000)
parryrate2 = alvo.Dex - 3000; clamp(0, ∞)   # sem teto explícito

parryrate = targetdex/2 + add + parryrate1/4 + parryrate2/8 - attackerdex

se atacante.Rsv & 0x20:  parryrate += 100
se atacante.Rsv & 0x80:  parryrate += 50
se atacante.Rsv & 0x200: parryrate += 50

parryrate = clamp(parryrate, 1, 650)
```

| Componente | Efeito |
|---|---|
| `Dex/2` do alvo (cap 1000) | base da esquiva |
| `Parry` do alvo (0–100) | bônus plano de equipamento/skill |
| `Dex` acima de 1000 | +25% do excedente (até 2000) |
| `Dex` acima de 3000 | +12,5% do excedente |
| `attackerdex = atacante.Dex/5` | reduz a esquiva do alvo |
| `LearnedSkill & 0x1000000` | +100 de precisão |
| `atacante.Rsv & 0x40` | **+500** de precisão (flag de skill/buff) |
| `Rsv` bits 0x20/0x80/0x200 | +100/+50/+50 na esquiva do alvo |

O resultado é comparado com `rand() % 1000 + 1`; portanto `parryrate` está em **permilagem**, não em porcentagem. Cap 650 = 65% de esquiva máxima.

### 5.2. `BASE_GetAccuracyRate` (não é o roll de PvP)

```c
int ret = att->Dex / 2 + 50;
if (ret > 100) ret = 100;
```

Essa função existe (`Basedef.cpp:6110`) e retorna percentual, mas o combate PvP usa `attackdex = Dex/5` dentro de `GetParryRate`. Não confundir as duas: a primeira é usada em outros contextos (IA/exibição); a segunda é a que decide acerto.

> ⚠️ O mapeamento completo de onde `BASE_GetAccuracyRate` é consumida não foi levantado nesta fase.

---

## 6. Defesa, absorção e reflect

### 6.1. AC

- `Ac` entra na mitigação como `ac/2`.
- Em PvP, `Ac *= 3` antes da mitigação.
- TransKnight com "Trans" recebe `totalac = (Ac/100)*10 + Ac` (`Basedef.cpp:3357`), ou seja **+10% de AC** (com truncamento).
- Itens com `sanc == 9` nos slots de acessório `Equip[8..11]` contam como `sanc = 10` para efeitos (`Basedef.cpp:1851-1852`) — ×2 no multiplicador `(sanc+10)/10`.

### 6.2. Reflect

Fonte: `_MSG_Attack.cpp:1496-1508` ✅

```text
se alvo é jogador e dam > 0:
    dam -= alvo.ReflectDamage
    se dam < 1: dam = 1
    dam -= (dam / 100) * alvo.ReflectPvP
    se dam < 1: dam = 1
```

Reflect é aplicado **ao dano de saída**, não como um segundo golpe. `ReflectDamage` é plano; `ReflectPvP` é percentual.

### 6.3. "Absorção"

Não foi encontrada uma stat de absorção percentual por classe no código de combate. O que existe:

| Mecânica | Onde | O que faz |
|---|---|---|
| `ReflectDamage` / `ReflectPvP` | `_MSG_Attack.cpp:1496` | reduz o dano recebido em PvP |
| AC ×3 em PvP | `_MSG_Attack.cpp:455` | defesa de jogador vale o triplo |
| Cythera "Damage Absorb 30/40" | documentação oficial (2010) | bônus de traje Celestial, provavelmente via `EF_*` |
| "Absorção" (Sephirot) | `GetFunc.cpp:666` | **nome de combinação** de itens, não fórmula de dano |

> **Conclusão honesta:** a afirmação do briefing de que existe "absorção por classe" não se sustenta na fonte. Se a intenção era resistência a dano, o caminho é `Reflect*` + AC; se era o traje Cythera, é um efeito de item a mapear na fase de conteúdo.

---

## 7. Composição de atributos por classe

`CurrentScore.Damage` parte do equipamento (`EF_DAMAGE`) e recebe, **por gate de skill aprendida**, um bônus linear em Dex/Str. A tabela abaixo foi extraída automaticamente de `Basedef.cpp` (bloco `// Balanceamento`) por [scripts/extract_balance.py](../scripts/extract_balance.py); os gates repetem a mesma tabela, por isso estão deduplicados.

### 7.1. Dano físico: `Damage += Dex*kd + Str*ks`

| Arma (`nUnique`) | TransKnight | Foema | BeastMaster | Huntress |
|---|---|---|---|---|
| 43 Garra | 0.38 / 0.42 | 0.50 / 0.55 | 0.42 / 0.46 | 0.49 / 0.53 |
| 42 Arco | 0.55 / 0.60 | 0.75 / 0.80 | 0.68 / 0.72 | 0.68 / 0.72 |
| 46 Hermai | 0.36 / 0.40 | 0.40 / 0.45 | 0.44 / 0.48 | 0.53 / 0.57 |
| 48 Espada 2 mãos | 0.56 / 0.60 | 0.50 / 0.55 | 0.41 / 0.46 | 0.51 / 0.55 |
| 49 Martelo | 0.43 / 0.47 | 0.60 / 0.65 | 0.65 / 0.70 | 0.47 / 0.51 |
| 45 Caliburn | 0.22 / 0.27 | 0.55 / 0.60 | 0.22 / 0.32 | 0.27 / 0.37 |
| 41 Balmung | 0.22 / 0.27 | 0.50 / 0.55 | 0.22 / 0.32 | 0.27 / 0.37 |
| 44 Lança | mágico | mágico | mágico | mágico |
| 47 Cajado/Cetro | mágico | mágico | mágico | mágico |

Cada célula é `coeficiente Dex / coeficiente Str`. Gates:

| Classe | Gates que ativam a tabela |
|---|---|
| TransKnight | `Confiança` (bit 7), `Trans` (bit 15), `Espada Mágica` (bit 23) |
| Foema | `Blood` (bit 7), `8ª Black` (bit 15), `8ª Magia Especial` (bit 23) |
| BeastMaster | `BM Elemental` (bit 7), `BM Evocações` (bit 15), `BM Natureza` (bit 23) |
| Huntress | `Agressividade` (bit 2) |

### 7.2. Poder mágico: `magic += (Dex*kd + Int*ki)/100`

| Arma | TransKnight | Foema | BeastMaster | Huntress |
|---|---|---|---|---|
| 44 Lança | 2.0 / 2.5 | 6.3 / 4.2 | 7.0 / 6.0 | 40.0 / 20.0 |
| 47 Cajado/Cetro | 1.2 / 1.5 | 6.3 / 4.2 | 6.8 / 5.8 | 40.0 / 20.0 |
| `ArmaPos == 64` (cajado) | 2.0 / 2.5 | 6.3 / 4.2 | 5.5 / 4.5 | — |

Valores em percentual: `6.3` significa `Dex * 0.063`. O Huntress tem coeficientes 40.0/20.0 — **40% de Dex e 20% de Int**, uma ordem de magnitude acima das outras classes. Isso é suspeito e deve ser validado com captura/paridade antes de qualquer rebalanceamento; pode ser um bug histórico que compõe dano mágico de Huntress de forma desproporcional.

### 7.3. Modificadores planos

- Huntress, gate `Tempestade de Raios` (bit 7): `Damage += 200` (`Basedef.cpp:3852`).
- TransKnight, `Trans`: `Ac += 10%`.
- TransKnight, `Trans`: `Critical += max(4, (special3+1)/10 + Dex/75)`.

### 7.4. HP e MP por nível

Fonte: `Basedef.cpp:61-62` ✅

| Classe | HP por nível | MP por nível |
|---|---:|---:|
| TransKnight | 3 | 1 |
| Foema | 1 | 3 |
| BeastMaster | 1 | 2 |
| Huntress | 2 | 1 |

Esses incrementos são a base de progressão; o total efetivo depende de `BaseScore`, equipamentos e buffs. Ver [05-PROGRESSAO-E-REFINO.md](05-PROGRESSAO-E-REFINO.md).

---

## 8. Constantes de combate

| Constante | Valor | Papel |
|---|---:|---|
| `MAX_DAMAGE` / `MAX_DAMAGE_MG` | 1.000.000.000 | clamp final |
| `MAX_TARGET` | 13 | alvos por pacote de ataque |
| `MAX_SKILL` | 24 | módulo usado em `Special[]` |
| Teto de maestria (melee) | 7 | após `combat/2` |
| Teto de maestria (skill) | 15 | direto |
| Piso de dano | 1 | sempre |
| Cap de esquiva | 650 ‰ | `GetParryRate` |
| AC de jogador em PvP | ×3 | antes da mitigação |
| Dano mínimo de reflect | 1 | após cada etapa |

---

## 9. O que ainda não está fechado

| Item | Status | Como fechar |
|---|---|---|
| Coeficientes de todas as classes × armas | ✅ extraídos | script versionado; revisar Huntress 40/20 |
| `g_pHitRate` (tabela de 1024) | ⚠️ gerada em runtime | ler `Basedef.cpp:5912-5945` e reproduzir a inicialização |
| Árvore completa de `BASE_GetDoubleCritical` | ✅ núcleo | validar com golden cases |
| Dano de skills com `instanceindex` 6/11 | 🟡 fórmula lida | mapear quais skills usam cada índice |
| "Absorção" por classe | ⚠️ inexistente na fonte | confirmar com o cliente/servidor de referência |
| Efeito de `AttackRun`/`AttackSpeed` no tick | ⚠️ não mapeado | ler `CMob.cpp` e o loop de `ProcessSecMinTimer` |
| Fórmula de dano de montaria/summon | ⚠️ não mapeada | `pSummonBonus`/`pTransBonus` em `Basedef.cpp:754-780` |

### 9.1. Plano de validação

1. **Golden cases**: para um conjunto de (`dam`, `ac`, `combat`), gerar 10.000 amostras com o `rand()` do MSVC e comparar a distribuição com a implementação nova. Não é possível reproduzir a sequência exata sem o mesmo RNG, mas é possível comparar média, variância e suporte.
2. **Casos determinísticos**: fixar `rnd` no valor mínimo/máximo e comparar com a escada de pisos.
3. **PvP**: validar `Ac *= 3` e reflect com dois personagens de atributos conhecidos.
4. **Skills**: tabelar `InstanceType/InstanceValue/AffectValue` de `SkillData.csv` e comparar 20 skills representativas.

---

## 10. Implicações para a stack nova

1. **Ponto fixo, não float.** Os coeficientes `0.38`, `0.55` etc. são aplicados a inteiros e truncados. Use aritmética inteira (por exemplo, coeficientes em milésimos) para evitar divergência de 1 ponto por arredondamento de `float`.
2. **RNG determinístico e auditável.** O legado usa `rand()` do MSVC; a stack nova deve usar um PRNG semeável por sessão e registrar a semente. Sem isso, disputas de dano e refinamento não são reproduzíveis.
3. **Autoridade total.** `CurrentHp`, `CurrentExp`, `CurrentMp` e `DoubleCritical` que chegam no `MSG_Attack` são alegações do cliente. O servidor deve recalcular e ignorar. Ver [02-PROTOCOLO.md](02-PROTOCOLO.md) §7.4.
4. **Combate como função pura.** Modele `resolve_hit(attacker_state, target_state, skill, rng, weather) -> HitResult` sem I/O. Isso permite golden tests e reuso pelo simulador de bots (Fase 5).
5. **Não "corrigir" o balanceamento na migração.** Preserve as fórmulas, incluindo o quirk dos bits de crítico e os coeficientes suspeitos. Correções viram feature flags explícitas, medidas e documentadas.

---

**Próximo documento:** [05-PROGRESSAO-E-REFINO.md](05-PROGRESSAO-E-REFINO.md) — curvas de XP, rebirth, atributos, refino e drops.
