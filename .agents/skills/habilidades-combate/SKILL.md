---
name: habilidades-combate
description: "Use quando a tarefa envolver combate: dano físico/mágico, crítico, esquiva, parry, hit rate, coeficientes classe × arma, resistências, resolve_hit, drops de morte e combate multiplayer."
metadata:
  category: wyd-next-gen
---

# Habilidades — Combate (WYD)

> Base para as habilidades de combat no sistema de agentes/server: dano físico, dano mágico, crítico, esquiva, parry, coeficientes por classe × arma, reflexos de sprint e defesa, matriz de hit rate, combinações de item, drops, e as decisões de paridade que acompanham.

---

## Quando usar

- Implementar `resolve_hit`, dano físico/mágico, crítico, esquiva, parry ou hit rate.
- Ajustar coeficientes classe × arma, resistências ou bônus de atributo.
- Validar fórmula contra golden cases ou comportamento legado.
- Mexer em drops/morte, refino aplicado ao dano ou combate multiplayer.

## 1. Contexto

O WYD não resolve dano com uma fórmula genérica de "INT aumenta dano mágico". O dano é **orientado por tabela de skill** (`g_pSpell`), com termos por classe, e o throughput de combate é regido por atributos, coeficientes de classe × arma, e efeitos de item. A missão da Fase 4 é uma função pura `resolve_hit` com golden cases, e a Fase 5+ traz autoridade server-side total (nada de confiar em HP/EXP/MP do cliente).

---

## 2. Habilidades de dano

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **resolve_hit (puro)** | Função pura que recebe contexto de ataque (atacante, alvo, arma, skill, distância, facing, ticks, etc.) e devolve dano, crítico, esquiva, etc., sem efeito colateral. | contexto → `{dano, acertou, critico, esquiva, damage_type}`. | Fase 4; sem golden cases do mundo real ainda. |
| **Dano físico base** | Coeficientes de classe × arma + atributos base; fórmula extraída de `Basedef.cpp` e `data/class_weapon_coefficients.json`. | atacante + arma → base. | Coeficientes já em `data/`. |
| **Dano mágico por skill** | Mapeamento de `InstanceType`/`TargetType` por skill, com termos por classe. | skill + alvo → dano. | Faltam alguns mapeamentos de InstanceType; tabela parcial. |
| **Penetração / defesa** | AC reduz damage; regra PvP (`Ac *= 3`) mantida por padrão até haver dados de balanceamento. | alvo + contexto → redução. | PvP ainda com regra legada; decisão de paridade R01. |

---

## 3. Habilidades de crítico e esquiva

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Crítico** | Política de crítico com `g_pHitRate` reproduzida ou substituída por decisão explícita; bits de crítico invertidos no legado (semântica mantida, nome renovado no código novo). | ataque → {critico, chance}. | `g_pHitRate` não finalizada; decisão de paridade R01. |
| **Esquiva** | Esquiva por classe (Huntress) + atributos; fórmula de chance de esquiva. | ataque → {esquiva, chance}. | Se o legado usa `rand()%100` ou `rand()%115` no refino, isso é uma questão separada (R05). |
| **Parry** | Parry de dano; fórmula de parry em `GetFunc.cpp`. | dano entrando → {parry, chance}. | Fase 4/5. |

---

## 4. Habilidades de atributos e corpo

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **HP/MP** | `CurrentHp/Exp` não é autoridade; reconstruir HP/MP server-side; decidir se o legado dobra o MaxHp (`Basedef.cpp:3132-3145`) — capturar antes de decidir (R04). | character → hp/mp reais. |
| **Regeneração** | `RegenHP`/`RegenMP` e efeitos de item (ex.: `EF_REGENHP`, `EF_REGENMP`) aplicados no tick. | character + tick → regen. |
| **Status** | Buffs/debuffs via afetos (type, value, level, time) aplicados no mundo, com timer server-side. | afeto → estado ativo. |

---

## 5. Habilidades de item, refino e combine

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Efeito de item** | `sIndex` + até 3 pares `(EF_*, valor)`; aplicar efeitos estáticos e dinâmicos. | item → efeitos. |
| **Refino (R05)** | `EF_SANC` (43) ou faixa 116–125 → nível/gema/pity; off-by-one `sanc+1`, pity empacotado; taxa de refino de `SancRate.txt`. | item → refine/gem/pity. |
| **Combine (R05)** | `CompRate.txt` importado; taxa de combine por família; anti-macro com cooldown explícito. | itens + combinação → resultado/taxa. |

---

## 6. Habilidades de combate multiplayer e economia

| Skill | O que faz | Entrada / saída |
|---|---|---|
| **Target selection** | Seleção de alvo por range, faction, party, etc., com `MaxTarget` e bits de comportamento da skill. | skill + contexto → alvos. |
| **Ação e movimento** | Ataque (`0x367`), movimento (`0x36C`), variantes (`0x39D`, `0x39E`); movimento com validação server-side; taxa de spawn/acción. | ação → mundo. |
| **Drop e loot** | Tabela de drop por mob; taxa de drop; loot com autoridade server-side; evitar dupes por corrida. | morte → drop. |
| **Economia** | Gold, EXP, itens; ledger de transações para itens; sem confiar no cliente para POS. | ação → mudança de estado. |

---

## 7. Limitações e riscos

- **Sem golden cases reais:** Fase 4 precisa de casos de dano com resultado esperado verificado (captura ou fonte) antes de confiar no resolve_hit.
- **g_pHitRate:** matriz de hit rate não finalizada; decisão de paridade ou substituição explícita via R01.
- **Dobra de MaxHp:** possível no legado; capturar antes de decidir se o novo servidor replica ou corrige.
- **Off-by-one e pity:** refino tem pendências de paridade documentadas em R05.
- **Sem criptografia de fio:** protocolo legado não tem criptografia real; a proteção vem de TLS na borda ou AES-GCM em pacotes sensíveis.

---

## 8. Referências

- `docs/04-COMBATE.md` — dano, crítico, parry, coeficientes por classe.
- `docs/05-PROGRESSAO-E-REFINO.md` — XP, rebirth, atributos, refino, drops.
- `data/class_weapon_coefficients.json` — coeficientes de dano por classe × arma.
- `data/xp_mortal_arch.csv`, `data/xp_celestial.csv` — curvas de XP.
- `data/refine_rates.json` — taxas de refino, pity e tabelas de combine.
- `reference/w2pp-OpenWYD/Source/Code/TMSrv/_MSG_Attack.cpp` — handler de ataque (Fonte de referência, não copiado).
- `reference/w2pp-OpenWYD/Source/Code/TMSrv/GetFunc.cpp` — parry, receitas de combine.
- `reference/w2pp-OpenWYD/Basedef.cpp` — structs, constantes, fórmulas BASE_*.

