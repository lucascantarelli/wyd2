# 01 — Fontes, Ecossistema e Metodologia

> **Escopo:** o que existe publicamente sobre WYD, o que é confiável, o que não existe, e como este projeto valida cada afirmação.
>
> **Legenda:** ✅ verificado · 🟡 derivado · ⚠️ não verificado

---

## 1. Método de evidência

Toda afirmação técnica deste projeto carrega um dos três níveis:

| Nível | Significado | Exemplo |
|---|---|---|
| ✅ | Lido diretamente no código-fonte ou em documento primário | `INITCODE = 0x1F11F311` em `CPSock.h:40` |
| 🟡 | Derivado de código/documento, com uma inferência explícita | "o subdiretório da conta é a primeira letra" (inferido de uma amostra) |
| ⚠️ | Não verificado; hipótese a validar | layout interno do pacote de billing de 196 bytes |

Regras:

1. **Nenhum número sem origem.** Fórmulas e tabelas citam `arquivo:linha` ou um artefato em `data/`.
2. **Inferência é declarada como inferência.** Não se mistura com fato.
3. **Divergência é decisão, não acidente.** Quando a stack nova corrige um bug do legado, isso vira uma nota de divergência intencional.
4. **Reprodutibilidade.** Tabelas numéricas são extraídas por script ([scripts/extract_reference_data.py](../scripts/extract_reference_data.py), [scripts/extract_balance.py](../scripts/extract_balance.py)), não transcritas à mão.

### 1.1. Por que não confiar em "fórmulas de fórum"

A pesquisa encontrou **zero** fórmulas de combate publicadas em fóruns/wikis que batessem com o código. O que existe são descrições qualitativas ("STR aumenta dano físico", "Huntress esquiva") e números de servidores específicos. Qualquer documento que apresente uma fórmula de dano do WYD sem citar código ou captura está, na melhor das hipóteses, descrevendo um servidor privado com configuração própria.

---

## 2. Estado do ecossistema

### 2.1. Projetos públicos (verificados)

| Projeto | URL | Linguagem | Alvo | O que é |
|---|---|---|---|---|
| **w2pp-OpenWYD** | https://github.com/Jean1dev/w2pp-OpenWYD | Go + C++ legado | build 7662 / protocolo 7640 | O mais completo: fontes C++ do "Polly's Server" + reescrita Go com serviços `tmServer`, `dbServer`, `binServer`, `webServer` e uma pasta `docs/migration/` com especificação de protocolo, regras e formatos citando `arquivo:linha`. **Fonte primária deste projeto.** |
| **wyd748** | https://github.com/felipeletsgo/wyd748 | Go + C++ | 7.48 | Servidor autoritativo em Go + fontes do cliente C++ (TMProject 748). Documentação extensa (200+ arquivos) e pesquisa com Ghidra do servidor nativo 7.59. |
| **snalmir** | https://github.com/venantivs/snalmir | C | 7.54, Linux | Servidor `epoll` não-bloqueante; login, char, chat, movimento, ataque, atributos, teleport, quests, NPCs. Sem DBSrv, sem multi-canal, DB em arquivo. |
| **W2PP** | https://github.com/seitbnao/W2PP | C/C++ | build mais recente | Decompilação do release "Polly's Server" (Klafke/TheHouse), GPLv3. Inclui TMSrv, DBSrv, BISrv, ferramentas e `ClientPatch_v7662`. |
| **WYDServer_7556** | https://github.com/reon/WYDServer_7556 | C++ | 7556 | Patch de source 7556; profundidade de implementação não verificada. |
| **open-wyd-scripts** | https://github.com/open-wyd/open-wyd-scripts | Lua 5.3 | — | API de scripting server-side (não é servidor). Útil como referência de superfície de modding. |
| **WYD2Bot** | https://github.com/kevinkouketsu/WYD2Bot | C++ | cliente 756+ | Bot headless com login e lista de personagens; menciona um "hash system" adicional em clients 756+. |

### 2.2. O que **não** existe

| Alegação comum | Realidade |
|---|---|
| "PyWYD" | **Não existe.** Busca no GitHub e na web retorna zero resultados. Não citar. |
| `openwyd.com.br` | Domínio morto (DNS não resolve). A org `open-wyd` no GitHub sobrevive, mas o servidor não. |
| "Código do OpenWYD" como servidor | A org tem launcher, fórum e scripts; não há servidor completo ali. |
| Árvore `TLogin` / `TGame` / `TNet` / `TItem` | Não existe nesse formato. A árvore real é `TMSrv` / `DBSrv` / `BISrv` + `Basedef.cpp` / `CPSock.cpp`. |
| Fórmulas de combate publicadas | Não encontradas em fonte independente. As únicas verificáveis estão no código. |

### 2.3. Versões e nomenclatura

| Nome | O que é |
|---|---|
| **7.48 / 7.54 / 7.55 / 7.56 / 7.62 / 7.63** | gerações de cliente/servidor; protocolos e conteúdos diferentes |
| **7662** | build do executável e do `ClientPatch_v7662.dll` |
| **7640** | **versão de protocolo** que o cliente envia em `MSG_AccountLogin.ClientVersion` (`APP_VERSION`) |
| **7.xx keys** | tabela `pKeyWord[512]` usada na ofuscação |

> A confusão 7662 vs. 7640 é comum: 7662 é o nome do build; 7640 é o número que trafega no pacote de login e que o servidor compara.

### 2.4. Comunidades

| Hub | URL | Observação |
|---|---|---|
| RaGEZONE — WYD2 | https://forum.ragezone.com/community/wyd2.302/ | maior acervo em inglês; seção cobre 6.13 a 7.63; downloads exigem login |
| XPZone — WYD | https://forum.xpzone.net/forums/wyd.117/ | maior acervo em português; releases de source 7.62/7662 |
| GitHub | busca `with your destiny` | ~6 repositórios; a maior parte do conhecimento está em fóruns, não em Git |

**Não verificados:** WebCheats, elitepvpers e ownedcore não retornaram material específico de WYD. Discord: nenhum convite público verificável.

---

## 3. A árvore de código canônica

```text
Source/Code/
├── Basedef.cpp / .h        # structs, constantes, tabelas, fórmulas BASE_*
├── CPSock.cpp / .h         # transporte: HEADER, INITCODE, codec, framing
├── ItemEffect.h            # vocabulário EF_* (1..127)
├── TMSrv/                  # servidor de jogo (fala com o cliente)
│   ├── Server.cpp          # loop, timers, estado global
│   ├── CUser.cpp / CMob.cpp / CItem.cpp
│   ├── ProcessClientMessage.cpp
│   ├── ProcessDBMessage.cpp
│   ├── SendFunc.cpp / GetFunc.cpp
│   ├── MobKilled.cpp       # EXP, drop, gold
│   └── _MSG_*.cpp          # ~60 handlers, um por pacote
├── DBSrv/                  # persistência de contas/personagens
│   ├── CFileDB.cpp
│   ├── CRanking.cpp
│   └── CReadFiles.cpp
└── BISrv/                  # billing (link de 196 bytes)
```

### 3.1. Onde cada lógica vive

| Tema | Arquivo | Linhas-chave |
|---|---|---|
| Cabeçalho e codec | `CPSock.cpp` | 29-46 (tabela), 353-467 (leitura), 535-584 (escrita) |
| Dano físico | `Basedef.cpp` | `BASE_GetDamage` 1265-1296 |
| Mitigação de skill | `Basedef.cpp` | `BASE_GetSkillDamage` 1486-1515 |
| Dano de skill/mágico | `Basedef.cpp` | `BASE_GetSkillDamage` 6998-7064 |
| Score e coeficientes | `Basedef.cpp` | 3014-4729 |
| Parry/esquiva | `TMSrv/GetFunc.cpp` | 686-725 |
| Crítico | `Basedef.cpp` | `BASE_GetDoubleCritical` 6122-6181 |
| Pipeline de ataque | `TMSrv/_MSG_Attack.cpp` | 440-480, 1415-1473, 1496-1508 |
| EXP/drop | `TMSrv/MobKilled.cpp` | 1272-1425 (EXP), 2693-2900 (drop) |
| Refino por poeira | `TMSrv/_MSG_UseItem.cpp` | 802-976 (principal), 224/385/514/716 (variantes) |
| Combine | `TMSrv/_MSG_CombineItem.cpp` | 46-139 |
| XP table | `Basedef.cpp` | 625-751 |
| Taxas de refino | `Basedef.cpp` | 68-122 |
| Structs de save | `Basedef.h` | 500-1108 |
| Structs de rede | `Basedef.h` | 1545-2485 |

---

## 4. Restrição legal e estratégia de uso

Isto não é um detalhe burocrático; define como o projeto pode ser construído.

- O WYD é propriedade da **HanbitSoft**. Os fontes disponíveis são **decompilações/leaks** de servidores privados.
- O repositório de referência é **GPLv3** (W2PP), mas a GPL não pode licenciar o que o autor original não licencia. O próprio README do W2PP diz que não reivindica direitos e que todos pertencem à HanbitSoft.
- Copiar código do repositório de referência para o projeto novo cria uma cadeia de licenciamento duvidosa.

**Estratégia recomendada: clean-room comportamental.**

1. A referência é usada como **oráculo de especificação** (ler e documentar comportamento, com citação), não como código a ser colado.
2. A implementação nova é escrita do zero, a partir das especificações em `docs/` e `spec/`.
3. Testes de paridade comparam **comportamento observável** (bytes na rede, resultados de fórmulas, distribuições), não código.
4. O diretório `reference/` é **gitignored** e não faz parte do artefato distribuído.

> Se o objetivo for operar um servidor público, a decisão sobre licenciamento e uso de assets (clientes, mapas, sprites) precisa de aconselhamento jurídico. Este documento não substitui isso.

---

## 5. Como validar (além da leitura de código)

| Técnica | O que fecha | Custo |
|---|---|---|
| **Golden vectors de transporte** | codec, checksum, framing | baixo |
| **Captura de tráfego** com o cliente 7662 | opcodes e structs reais | médio (precisa do cliente) |
| **Differential testing** contra o servidor de referência | fórmulas e fluxos | médio-alto |
| **Distribuição estatística** de RNG | dano, refino, drop | baixo (10k amostras) |
| **Ghidra/IDA** no cliente ou no servidor nativo | pontos não documentados | alto |
| **Fuzzing de framing** | robustez e segurança | baixo |

### 5.1. Limite do RNG

O legado usa `rand()` do MSVC. Reproduzir a **sequência exata** exigiria o mesmo gerador e a mesma seed; isso é possível, mas frágil. A estratégia adotada é:

1. Reproduzir a **distribuição** (suporte, probabilidades, fold `rand()%115`).
2. Fixar o RNG em testes determinísticos (golden cases com valor sorteado conhecido).
3. Registrar a seed em produção para auditoria.

Sem isso, não há como disputar um refino ou um crítico.

---

## 6. Backlog de pesquisa (priorizado)

| # | Item | Por quê | Como |
|---:|---|---|---|
| 1 | Captura real de login + ataque + refino | fecha opcodes e structs marcados ⚠️ | cliente 7662 + proxy |
| 2 | `g_pHitRate` (tabela de 1024) | crítico total depende dela | ler `Basedef.cpp:5912-5945` e reproduzir |
| 3 | Layout de `_AUTH_GAME` (billing, 196 B) | reimplementar billing | captura TMSrv↔BISrv |
| 4 | Contas de 4294 bytes | migração | amostras + Ghidra no DBSrv |
| 5 | Delays de skill (`/4`) | anti-cheat e cooldown | comparar `SkillData.csv` com captura |
| 6 | Montarias (valores comentados) | conteúdo | decisão de produto |
| 7 | Dano de summon/montaria | combate completo | `pSummonBonus`/`pTransBonus` + testes |
| 8 | AI de mob (`NPCGener`, `CMob`) | mundo vivo | leitura + simulação |

---

## 7. Resumo executivo

- Existe **um** projeto público que documenta o WYD em nível de byte com citação de fonte: `w2pp-OpenWYD`. Todo o resto é parcial ou derivado dele.
- "PyWYD" não existe; a árvore `TLogin/TGame` é imaginação; o handshake `0x20D` é lenda.
- A metodologia é **evidência com nível de confiança**, extração automatizada de tabelas e validação por comportamento.
- A restrição legal exige **clean-room**: especificação sim, código colado não.
- O que falta é captura de tráfego real. Sem ela, os itens marcados ⚠️ continuam hipóteses — e estão listados explicitamente para não virarem folclore.

---

**Próximo documento:** [06-LACUNAS-E-RISCOS.md](06-LACUNAS-E-RISCOS.md) — o que pode dar errado e como mitigar.
