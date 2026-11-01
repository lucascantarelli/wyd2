---
name: habilidades-bots-ia
description: "Use quando a tarefa envolver bots ou cliente headless: login automático, máquina de estados, pathfinding A*, coleta de métricas, integração com LLM, prompts e limites de autonomia."
metadata:
  category: wyd-next-gen
---

# Habilidades — Bots e IA (WYD)

> Base para as habilidades de bots no sistema de agentes/server: cliente headless, autenticação, entrada no mundo, máquina de estados, pathfinding A*, e LLM com contexto.

---

## Quando usar

- Construir cliente headless ou automação de login.
- Mexer em máquina de estados, pathfinding A* ou coleta.
- Integrar LLM, prompt, contexto ou limite de autonomia.
- Definir política bot × humano e uso em testes.

## 1. Contexto

Bots no WYD são clientes autônomos que falam o mesmo protocolo do cliente legado: autenticam no gateway, entram no mundo, mantém sessão, e executam ações (explorar, combate, comércio) com máquina de estados e A* sem travar o tick. A IA (LLM) responde chat com contexto do mundo, personagem e sessão, e não reduz o tick do servidor.

---

## 2. Habilidades de bot

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Cliente headless** | Autentica no gateway, entra no mundo, mantém sessão, fala o protocolo 7662 sem UI. | credentials → sessão. | Fase 5+. |
| **Máquina de estados** | Ações autônomas: explorar, combate, comércio; sem travar o tick, com backpressure e prioridades. | estado → ações. | Fase 5+. |
| **Pathfinding A*** | Caminho no grid 4096×4096 com validação server-side (não confiar no cliente). | origem + destino → caminho. | Fase 5+. |
| **Combate autônomo** | Alvo, ataque, dano, esquiva, crítico, loot; com autoridade server-side. | bot + mundo → combate. | Fase 5+. |

---

## 3. Habilidades de IA/LLM

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Chat com contexto** | Responde chat com contexto do mundo, personagem, sessão; sem reduzir o tick do servidor. | mensagem + contexto → resposta. | Fase 5+. |
| **Contexto de sessão** | Contexto do personagem, inventário, posição, estado do mundo; sem PII, sem secrets. | sessão → contexto. | Fase 5+. |
| **Limites de uso** | Rate limit de ação do bot; custo de API; não abusar do servidor. | bot → limite. | Fase 5+. |

---

## 4. Limitações e riscos

- Bots interagem com humanos? Isso muda economia, detecção, moderação e talvez regulamento — registrar na R01 antes de implementar comportamento bot × humano.
- Não confiar no cliente para HP/EXP/MP/posição; o bot deve passar pela validação server-side.
- A* no grid 4096×4096 sem travamento do tick: backpressure e prioridades essenciais.

---

## 5. Referências

- `docs/02-PROTOCOLO.md` — protocolo, structs, login.
- `docs/04-COMBATE.md` — dano, crítico, esquiva, coeficientes.
- `reference/w2pp-OpenWYD/Source/Code/TMSrv/_MSG_Attack.cpp` — handler de ataque (referência, não copiado).
- `reference/w2pp-OpenWYD/Basedef.h` — structs de rede e save.

