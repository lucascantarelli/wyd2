---
name: habilidades-balanceamento-economia
description: "Use quando a tarefa envolver progressão ou economia: XP, rebirth, pontos de atributo, refino, pity, gemas, drops, ouro, taxa de combine, inflação ou paridade vs rebalanceamento."
metadata:
  category: wyd-next-gen
---

# Habilidades — Balanceamento, Economia e Progressão (WYD)

> Base para as habilidades de balanceamento: XP, rebirth, atributos, refino, drops, taxa de combine, e as decisões de paridade que acompanham o equilíbrio do jogo.

---

## Quando usar

- Alterar XP, rebirth, pontos de atributo, nível ou progressão.
- Mexer em refino, pity, gemas, taxa de combine, drops ou ouro.
- Avaliar economia, inflação ou paridade vs rebalanceamento.
- Definir números iniciais e limites de servidor.

## 1. Contexto

O WYD tem progressão por nível, XP por classe/espécie, rebirth, atributos, refino com pity, e economia por gold/items. O balanceamento é derivado da fonte (extração por script) e da paridade com o legado; qualquer rebalanceamento vem de decisão explícita (R01) e está documentado como divergência.

---

## 2. Habilidades de progressão

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **XP por classe/espécie** | Curva de XP Mortal/Arch (597 níveis) e Celestial/Sub-Celestial (401 níveis); curva Celestial com salto de 40M no 199. | level → XP. | Fase 4+. |
| **Rebirth** | Rebirth + renascença; política de rebirth e pontos. | character → rebirth. | Fase 4+. |
| **Atributos** | Level, Ac, Damage, MaxHp/Mp, Hp/Mp, Str/Int/Dex/Con, Special[4]; score bonus, special bonus, skill bonus. | character → atributos. | Fase 4+. |

---

## 3. Habilidades de economia

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Gold e EXP** | `characters.gold` + `characters.exp`, e `accounts.cargo_gold` para o cargo compartilhado. | character/account → valores. | Autoridade server-side; nunca confiar no cliente. |
| **Refino (R05)** | `EF_SANC` (43) ou faixa 116–125 → nível/gema/pity; off-by-one `sanc+1`; pity empacotado; taxa de refino de `SancRate.txt`. | item → refine/gem/pity. | Fase 4+. |
| **Combine (R05)** | `CompRate.txt` importado; taxa de combine por família; anti-macro com cooldown explícito. | itens + combinação → resultado/taxa. | Fase 4+. |
| **Drop e loot** | Tabela de drop por mob; taxa de drop; loot com autoridade server-side; evitar dupes por corrida. | morte → drop. | Fase 4+. |
| **Ledger de itens (R06)** | `item_ledger` append-only; UPDATE/DELETE/TRUNCATE bloqueados; histórico sobrevive ao item. | item → ledger. | Fase 2+. |

---

## 4. Habilidades de balanceamento

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Paridade vs rebalanceamento** | Decisão explícita por mecânica: o que replica o legado e o que moderniza; divergências documentadas no changelog de paridade. | mecânica → decisão. |
| **Dobra de MaxHp** | Se o legado dobra o MaxHp (`Basedef.cpp:3132-3145`), capturar antes de decidir se o novo servidor replica ou corrige. | MaxHp → decisão. |
| **PvP `Ac *= 3`** | Manter por padrão até haver dados de balanceamento; decisão de paridade R01. | PvP → regra. |
| **Cooldown de refino** | Comentado no legado; vira política explícita no novo servidor; rate limit de ação. | ação → cooldown. |

---

## 5. Limitações e riscos

- Curva Celestial com salto de 40M no 199; replicar ou suavizar é decisão de paridade.
- Off-by-one e pity têm pendências de paridade documentadas em R05.
- Sem golden cases de dano: Fase 4 precisa de casos com resultado esperado verificado.
- Sem criptografia de fio: a proteção vem de TLS na borda ou AES-GCM em pacotes sensíveis.

---

## 6. Referências

- `docs/05-PROGRESSAO-E-REFINO.md` — XP, rebirth, atributos, refino, drops.
- `data/xp_mortal_arch.csv`, `data/xp_celestial.csv` — curvas de XP.
- `data/refine_rates.json` — taxas de refino, pity e tabelas de combine.
- `reference/w2pp-OpenWYD/Source/Code/TMSrv/_MSG_Attack.cpp` — handler de ataque (referência, não copiado).
- `reference/w2pp-OpenWYD/Basedef.cpp` — structs, constantes, fórmulas BASE_*.

