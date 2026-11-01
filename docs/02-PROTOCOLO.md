# 02 — Protocolo de Rede

> **Escopo:** especificação de fio do WYD 7.xx (cliente build 7662, `APP_VERSION` 7640) suficiente para um servidor novo falar byte-a-byte com o cliente original.
>
> **Fonte primária:** `reference/w2pp-OpenWYD/Source/Code/{CPSock.h,CPSock.cpp,Basedef.h}` e `docs/migration/protocol-spec.md` do mesmo repositório (GPLv3, derivado do "Polly's Server"/W2PP).
>
> **Legenda de evidência:** ✅ verificado na fonte · 🟡 inferido/derivado · ⚠️ não verificado

---

## 0. Correções ao briefing original

O briefing desta fase listou cinco pacotes e um handshake. Quatro das seis premissas estão erradas. A tabela abaixo é o ponto de partida correto:

| Premissa do briefing | Fato verificado | Evidência |
|---|---|---|
| `0x20D` = handshake / troca de chaves | `0x20D` = `_MSG_AccountLogin`. **Não existe troca de chaves.** | `Basedef.h:1543` |
| Handshake negocia uma chave de sessão | Handshake é um inteiro fixo de 4 bytes, `INITCODE = 0x1F11F311`, sem resposta e sem material de chave | `CPSock.h:40` |
| `0x213` = seleção de personagem | Correto no essencial: `_MSG_CharacterLogin` entra no mundo com o `Slot` escolhido | `Basedef.h:1673` |
| `0x334` = chat | `0x334` = **sussurro** (`_MSG_MessageWhisper`). Chat público é `0x333` (`_MSG_MessageChat`) | `Basedef.h:1788,1796` |
| `0x366` = movimentação | `0x366` é `_MSG_Action2`; a movimentação canônica é **`0x36C`** (`_MSG_Action`). `0x366/0x368` roteiam para o mesmo handler | `Basedef.h:2067` |
| `0x36C` = ataque | `0x36C` é **movimento**. Ataque é **`0x367`** (`_MSG_Attack`), com variantes `0x39D`/`0x39E` | `Basedef.h:2399` |

> Consequência de projeto: o gateway novo **não deve** implementar "handshake criptográfico". O que existe é (a) um gate de versão de 4 bytes e (b) uma ofuscação simétrica com tabela pública. Tratar isso como criptografia é um erro de modelo de ameaça — ver §3.4.

---

## 1. Modelo de transporte

| Propriedade | Valor | Evidência |
|---|---|---|
| Transporte | TCP, uma conexão por cliente | `CPSock.cpp` |
| Handshake | 4 bytes `11 F3 11 1F` (little-endian de `0x1F11F311`) | `CPSock.h:40`, `CPSock.cpp:366-383` |
| Cabeçalho | 12 bytes fixos, little-endian | `CPSock.h:42-50` |
| Delimitação | campo `Size` do cabeçalho; sem terminador | `CPSock.cpp:386-416` |
| Tamanho mínimo | 12 bytes | `CPSock.cpp:397-406` |
| Tamanho máximo | 8192 bytes (`MAX_MESSAGE_SIZE`) | `CPSock.h:38` |
| Buffers | 128 KiB de recepção e 128 KiB de envio | `CPSock.h:35-36` |
| Usuários por processo | 1000 (`MAX_USER`) | `Basedef.h:116` |
| Versão de protocolo | 7640 (`APP_VERSION`) | `Basedef.h:102` |

### 1.1. Sequência de conexão

```mermaid
sequenceDiagram
    participant C as WYD.exe
    participant G as Gateway
    C->>G: TCP connect
    C->>G: INITCODE (4 bytes, 0x1F11F311)
    Note over G: valida o gate; não há resposta
    C->>G: HEADER + MSG_AccountLogin (0x20D)
    G-->>C: MSG_CNFAccountLogin (0x10A) + lista de personagens
    C->>G: MSG_CharacterLogin (0x213, Slot)
    G-->>C: MSG_CNFCharacterLogin (0x114) + snapshot do mundo
    C->>G: MSG_Action (0x36C) / MSG_Attack (0x367) / chat (0x333)
```

O `INITCODE` é enviado pelo lado que **conecta**. O cliente o envia ao abrir a conexão com o servidor de jogo; nas conexões servidor→servidor (`ConnectServer`) o mesmo código é enviado por `send(tSock, &InitCode, 4, 0)` (`CPSock.cpp:250`).

**Regra para o gateway novo:** exigir e consumir exatamente 4 bytes antes de qualquer parsing de cabeçalho. Conexão que não comece com `0x1F11F311` deve ser derrubada. Isso não autentica nada — é um filtro de tráfego/versão.

### 1.2. Enquadramento (framing)

```text
loop:
  se ainda não consumiu INITCODE:
      ler 4 bytes; se != 0x1F11F311 -> fechar
  esperar >= 12 bytes no buffer
  size = u16le(buffer[0..2])
  se size < 12 ou size > 8192 -> fechar (buffer inconsistente)
  esperar >= size bytes
  frame = buffer[0..size)
  avançar buffer em size
```

Propriedades que a implementação nova deve respeitar:

1. **Múltiplos pacotes por `recv()`** são normais; o parser precisa drenar em laço.
2. **Frame parcial** fica no buffer; não se descarta até completar.
3. `Size` inclui o cabeçalho. Um `MSG_STANDARD` tem `Size = 12`.
4. O legado zera os buffers em caso de tamanho inválido; o gateway novo deve fechar a conexão (fail-closed).

---

## 2. Cabeçalho (`HEADER`, 12 bytes)

```c
typedef struct _HEADER {
    short        Size;        // 2 bytes, tamanho total incluindo o header
    char         KeyWord;     // 1 byte, índice 0..255 na tabela pKeyWord
    char         CheckSum;    // 1 byte, checksum aditivo
    short        Type;        // 2 bytes, opcode + bits de direção
    short        ID;          // 2 bytes, slot do jogador/conexão
    unsigned int ClientTick;  // 4 bytes, tick do cliente
} HEADER;
```

| Offset | Campo | Tipo | Bytes | Observação |
|---:|---|---|---:|---|
| 0 | `Size` | `int16` | 2 | lido como `unsigned short` no legado |
| 2 | `KeyWord` | `uint8` | 1 | semente da ofuscação |
| 3 | `CheckSum` | `uint8` | 1 | soma aditiva, ver §4 |
| 4 | `Type` | `int16` | 2 | valor de fio inclui flags de direção |
| 6 | `ID` | `int16` | 2 | `0..999` para jogadores |
| 8 | `ClientTick` | `uint32` | 4 | gravado pelo servidor como `CurrentTime` no envio |

Notas de implementação:

- **Sem padding**: 2+1+1+2+2+4 = 12.
- A ofuscação e o checksum cobrem **do offset 4 até `Size`**; `Size`, `KeyWord` e `CheckSum` viajam em claro.
- O legado faz leituras sobrepostas de `Type`/`ID` como `unsigned int` (`CPSock.cpp:394-395`). **Não replicar**: o layout canônico é o da tabela.
- `ID` fora de `[0, MAX_USER)` é descartado pelo dispatcher (`ProcessClientMessage.cpp:42`).
- Pacotes do cliente com `ClientTick == 235543242` (`SKIPCHECKTICK`) são descartados (`Basedef.h:232`).

### 2.1. Structs de mensagem vs. structs de persistência

Há **dois regimes de alinhamento** e confundi-los quebra o parsing:

| Família | Alinhamento | Exemplo | Tamanho |
|---|---|---|---|
| Mensagens de rede (`MSG_*`) | `#pragma pack(push,1)` | `MSG_AccountLogin` | 116 bytes |
| Persistência (`STRUCT_MOB`, `STRUCT_ITEM`) | natural MSVC x86, com padding | `STRUCT_MOB` | 816 bytes |

Aplicar `pack(1)` em `STRUCT_MOB` produz 805 bytes — 11 bytes a menos que o real. Ver [03-DADOS-LEGADOS.md](03-DADOS-LEGADOS.md).

---

## 3. Codec (ofuscação `pKeyWord`)

### 3.1. A tabela

`pKeyWord[512]` é uma tabela estática (`unsigned char`) embutida em `CPSock.cpp:29-46`. Bytes de índice **par** são sementes de posição; índices **ímpares** são bytes de transformação.

- O emissor sorteia `iKeyWord = rand() % 256` e grava esse índice em `KeyWord` no header.
- A posição inicial é `pos = pKeyWord[iKeyWord * 2]`.
- `pos` avança 1 por byte e é reduzido `mod 256`, percorrendo os 256 pares.

### 3.2. Decode (recepção)

```text
pos = pKeyWord[iKeyWord * 2]
sum_cipher = 0
sum_plain  = 0
para i de 4 até Size-1:
    rst   = pos % 256
    sum_cipher += frame[i]                  # acumula ANTES de transformar
    trans = pKeyWord[rst * 2 + 1]
    caso i & 3:
        0: plain = frame[i] - (trans << 1)
        1: plain = frame[i] + (trans >> 3)
        2: plain = frame[i] - (trans << 2)
        3: plain = frame[i] + (trans >> 5)
    frame[i] = plain & 0xFF                 # truncamento de 8 bits
    sum_plain += frame[i]
    pos += 1
checksum_calculado = (sum_cipher - sum_plain) & 0xFF
```

### 3.3. Encode (envio)

Operação inversa, com a ordem das somas trocada:

```text
pos = pKeyWord[iKeyWord * 2]
para i de 4 até Size-1:
    sum_plain += plain[i]                   # acumula ANTES
    trans = pKeyWord[(pos % 256) * 2 + 1]
    caso i & 3:
        0: cipher = plain[i] + (trans << 1)
        1: cipher = plain[i] - (trans >> 3)
        2: cipher = plain[i] + (trans << 2)
        3: cipher = plain[i] - (trans >> 5)
    frame[i] = cipher & 0xFF
    sum_cipher += frame[i]
    pos += 1
checksum = (sum_cipher - sum_plain) & 0xFF
```

**Armadilha de portabilidade:** em C, `trans << 2` é promovido a `int` e pode passar de 255; o truncamento acontece na atribuição ao buffer `char`. Em Go/Rust/Python é obrigatório mascarar explicitamente com `& 0xFF` **após** a operação. Sem isso, o checksum e o payload divergem em bytes específicos.

### 3.4. Propriedade de segurança (importante)

Isto é **ofuscação, não cifragem**:

- A tabela é pública e idêntica no cliente e no servidor.
- A "chave" é um índice de 1 byte sorteado, não um segredo.
- O checksum é **não-rejeitante** no legado: em mismatch, `ReadMessage` seta `ErrorCode=1` e **retorna o pacote mesmo assim** (`CPSock.cpp:457-466`).
- O `ClientPatch_v7662.dll` patcheia três saltos condicionais para `JMP` (`0x53AC6A`, `0x53AD52`, `0x53AE7E`) desligando a verificação no cliente.

Portanto: **nenhuma decisão de segurança pode depender do codec**. Autenticação, autoridade de estado e anti-cheat pertencem às camadas 4–7 do modelo do projeto, não ao transporte legado.

---

## 4. Checksum

- Cálculo: `CheckSum = (soma dos bytes cifrados − soma dos bytes em claro) & 0xFF`, ambos sobre `[4, Size)`.
- No envio, calcular sempre. O cliente lê o campo; um valor errado gera comportamento indefinido em builds não patcheados.
- Na recepção, o legado **tolera** mismatch. A stack nova deve **rejeitar** e contar a métrica — é uma divergência intencional (endurecimento), documentada em [06-LACUNAS-E-RISCOS.md](06-LACUNAS-E-RISCOS.md).
- **É diferencial, não integridade:** a transformação soma/subtrai uma constante por posição, então `(soma cifrada − soma plana)` depende só de `Size` e `KeyWord`. Alterar um byte do corpo preserva a igualdade; o campo confere a chave de transporte, não o conteúdo. O gateway também só consegue recusar um `CheckSum` adulterado no próprio byte — coberto pela matriz de framing.

---

## 5. Codificação do campo `Type`

`Type` não é um opcode puro: é `base | flags de direção`. Os bits (`Basedef.h:1212-1221`):

| Flag | Valor | Sentido |
|---|---:|---|
| `FLAG_GAME2CLIENT` | `0x0100` | servidor de jogo → cliente |
| `FLAG_CLIENT2GAME` | `0x0200` | cliente → servidor de jogo |
| `FLAG_DB2GAME` | `0x0400` | DBSrv → TMSrv |
| `FLAG_GAME2DB` | `0x0800` | TMSrv → DBSrv |
| `FLAG_DB2NP` | `0x1000` | DBSrv → NPServer |
| `FLAG_NP2DB` | `0x2000` | NPServer → DBSrv |
| `FLAG_NEW` | `0x4000` | família "nova" (ranking) |

Exemplo: `_MSG_AccountLogin = 13 | FLAG_CLIENT2GAME = 525 = 0x020D`.

Duas famílias podem reutilizar a mesma base; as flags desambiguam. Ao implementar, compare sempre contra a **constante completa**, nunca contra a base isolada.

---

## 6. Ciclo de vida: opcodes que o gateway precisa tratar

### 6.1. Cliente → servidor (entrada)

Tabela mínima para um servidor jogável. A extração automática encontrou 197 constantes; o catálogo completo está em [spec/opcodes.yaml](../spec/opcodes.yaml).

| Type (dec/hex) | Constante | Struct | Handler legado |
|---:|---|---|---|
| 525 / `0x020D` | `_MSG_AccountLogin` | `MSG_AccountLogin` | `Exec_MSG_AccountLogin` |
| 527 / `0x020F` | `_MSG_CreateCharacter` | `MSG_CreateCharacter` | `Exec_MSG_CreateCharacter` |
| 529 / `0x0211` | `_MSG_DeleteCharacter` | `MSG_DeleteCharacter` | `Exec_MSG_DeleteCharacter` |
| 531 / `0x0213` | `_MSG_CharacterLogin` | `MSG_CharacterLogin` | `Exec_MSG_CharacterLogin` |
| 533 / `0x0215` | `_MSG_CharacterLogout` | `MSG_STANDARD` | `Exec_MSG_CharacterLogout` |
| 819 / `0x0333` | `_MSG_MessageChat` | chat | `Exec_MSG_MessageChat` |
| 820 / `0x0334` | `_MSG_MessageWhisper` | whisper | `Exec_MSG_MessageWhisper` |
| 876 / `0x036C` | `_MSG_Action` | `MSG_Action` | `Exec_MSG_Action` |
| 870 / `0x0366` | `_MSG_Action2` | `MSG_Action` | `Exec_MSG_Action` |
| 872 / `0x0368` | `_MSG_Action3` | `MSG_Action` | `Exec_MSG_Action` |
| 874 / `0x036A` | `_MSG_Motion` | `MSG_Motion` | `Exec_MSG_Motion` |
| 871 / `0x0367` | `_MSG_Attack` | `MSG_Attack` | `Exec_MSG_Attack` |
| 925 / `0x039D` | `_MSG_AttackOne` | `MSG_AttackOne` | `Exec_MSG_Attack` |
| 926 / `0x039E` | `_MSG_AttackTwo` | `MSG_AttackTwo` | `Exec_MSG_Attack` |
| 883 / `0x0373` | `_MSG_UseItem` | `MSG_UseItem` | `Exec_MSG_UseItem` |
| 886 / `0x0376` | `_MSG_TradingItem` | `MSG_TradingItem` | `Exec_MSG_TradingItem` |
| 889 / `0x0379` | `_MSG_Buy` | `MSG_Buy` | `Exec_MSG_Buy` |
| 890 / `0x037A` | `_MSG_Sell` | `MSG_Sell` | `Exec_MSG_Sell` |
| 899 / `0x0383` | `_MSG_Trade` | `MSG_Trade` | `Exec_MSG_Trade` |
| 900 / `0x0384` | `_MSG_QuitTrade` | `MSG_STANDARD` | `Exec_MSG_QuitTrade` |
| 903 / `0x0387` | `_MSG_Withdraw` | `MSG_STANDARDPARM` | `Exec_MSG_Withdraw` |
| 904 / `0x0388` | `_MSG_Deposit` | `MSG_STANDARDPARM` | `Exec_MSG_Deposit` |
| 624 / `0x0270` | `_MSG_GetItem` | `MSG_GetItem` | `Exec_MSG_GetItem` |
| 626 / `0x0272` | `_MSG_DropItem` | `MSG_DropItem` | `Exec_MSG_DropItem` |
| 631 / `0x0277` | `_MSG_ApplyBonus` | `MSG_ApplyBonus` | `Exec_MSG_ApplyBonus` |
| 934 / `0x03A6` | `_MSG_CombineItem` | combine | `Exec_MSG_CombineItem` |
| 4062 / `0x0FDE` | `_MSG_AccountSecure` | `MSG_AccountSecure` | `Exec_MSG_AccountSecure` |
| 928 / `0x03A0` | `_MSG_Ping` | — | no-op |

### 6.2. Servidor → cliente (saída)

| Type (dec/hex) | Constante | Uso |
|---:|---|---|
| 257 / `0x0101` | `_MSG_MessagePanel` | texto no painel |
| 258 / `0x0102` | `_MSG_MessageBoxOk` | popup |
| 266 / `0x010A` | `_MSG_CNFAccountLogin` | confirma login, envia lista de personagens |
| 276 / `0x0114` | `_MSG_CNFCharacterLogin` | snapshot do personagem e entrada no mundo |
| 281 / `0x0119` | `_MSG_CharacterLoginFail` | falha ao entrar |
| 284 / `0x011C` | `_MSG_AlreadyPlaying` | conta já online |
| 868 / `0x0364` | `_MSG_CreateMob` | spawn visível |
| 357 / `0x0165` | `_MSG_RemoveMob` | despawn |
| 871 / `0x0367` | `_MSG_Attack` | resultado de ataque |
| 876 / `0x036C` | `_MSG_Action` | movimento de terceiros |
| 822 / `0x0336` | `_MSG_UpdateScore` | atributos |
| 386 / `0x0182` | `_MSG_SendItem` | atualiza slot |
| 385 / `0x0181` | `_MSG_SetHpMp` | HP/MP |
| 380 / `0x017C` | `_MSG_ShopList` | loja NPC |


---

## 7. Layouts de mensagens críticas

Todos os offsets abaixo são relativos ao início do frame (offset 0 = `Size`). Little-endian.

### 7.1. `MSG_AccountLogin` — 116 bytes

> ⚠️ **O cliente WYD Global diverge:** a captura de 2026-11-01 mostra frame de 124 B
> (corpo de **112 B**) e `ClientVersion = 0x0C9DB301`, não 7640. O layout abaixo é o do
> **7662** e vale como oráculo; o layout medido está em
> [08-CLIENTE-ALVO.md](08-CLIENTE-ALVO.md#61-endpoint-medido-e-captura-do-login-2026-11-01).
> O gateway aceita os dois corpos e exige a versão do layout: 7640 no de 104 B e
> `0x0C9DB301` no de 112 B.

| Offset | Campo | Tipo | Bytes |
|---:|---|---|---:|
| 0 | `_MSG` | `HEADER` | 12 |
| 12 | `AccountPassword` | `char[12]` | 12 |
| 24 | `AccountName` | `char[16]` | 16 |
| 40 | `Zero` | `char[52]` | 52 |
| 92 | `ClientVersion` | `int32` | 4 |
| 96 | `DBNeedSave` | `int32` | 4 |
| 100 | `AdapterName` | `int32[4]` | 16 |

- `ClientVersion` **deve** ser `7640` **no 7662**; caso contrário o handler responde erro de versão (`_MSG_AccountLogin.cpp:44-47`). O cliente WYD Global anuncia `0x0C9DB301`.
- A senha trafega em texto plano. Isso é dívida de segurança do legado; a stack nova deve aceitar o formato no fio, mas nunca persistir a senha em claro.

### 7.2. `MSG_CharacterLogin` — 20 bytes

| Offset | Campo | Tipo | Bytes |
|---:|---|---|---:|
| 12 | `Slot` | `int32` | 4 |
| 16 | `Force` | `int32` | 4 |

### 7.3. `MSG_Action` (movimento) — 52 bytes

| Offset | Campo | Tipo | Bytes |
|---:|---|---|---:|
| 12 | `PosX`, `PosY` | `int16[2]` | 4 |
| 16 | `Effect` | `int32` | 4 |
| 20 | `Speed` | `int32` | 4 |
| 24 | `Route` | `char[24]` | 24 |
| 48 | `TargetX`, `TargetY` | `int16[2]` | 4 |

`Effect`: 0 = andando, 1 = teleportando (comentário do legado). `Route` carrega até 24 passos — é a base do pathfinding server-side e o ponto onde o cliente tenta impor trajetória.

### 7.4. `MSG_Attack` — tamanho variável (68 bytes com 1 alvo; 164 com 13)

| Offset | Campo | Tipo | Bytes |
|---:|---|---|---:|
| 12 | `Unk_1` | `char[4]` | 4 |
| 16 | `CurrentHp` | `int32` | 4 |
| 20 | `Unk_2` | `char[4]` | 4 |
| 24 | `CurrentExp` | `int64` | 8 |
| 32 | `unk0` | `int16` | 2 |
| 34 | `PosX`, `PosY` | `uint16[2]` | 4 |
| 38 | `TargetX`, `TargetY` | `uint16[2]` | 4 |
| 42 | `AttackerID` | `uint16` | 2 |
| 44 | `Progress` | `uint16` | 2 |
| 46 | `Motion` | `uint8` | 1 |
| 47 | `SkillParm` | `uint8` | 1 |
| 48 | `DoubleCritical` | `uint8` | 1 |
| 49 | `FlagLocal` | `uint8` | 1 |
| 50 | `Rsv` | `int16` | 2 |
| 52 | `CurrentMp` | `int32` | 4 |
| 56 | `SkillIndex` | `int16` | 2 |
| 58 | `ReqMp` | `int16` | 2 |
| 60 | `Dam[13]` | `STRUCT_DAM[13]` | 104 |

`STRUCT_DAM` = `{ int32 TargetID; int32 Damage; }` (8 bytes). `MAX_TARGET = 13`.

`_MSG_AttackOne` usa `Dam[1]` e `_MSG_AttackTwo` usa `Dam[2]`; o tamanho do frame varia com o número de alvos e deve ser validado contra `Size`, nunca contra `sizeof` fixo.

> **Autoridade:** `CurrentHp`, `CurrentExp`, `CurrentMp` e `DoubleCritical` vêm do cliente e são **alegações**, não fatos. O servidor legado os lê para conveniência de sincronização; a stack nova deve recalculá-los e ignorar valores divergentes (ver [04-COMBATE.md](04-COMBATE.md) §7).

### 7.5. `MSG_UseItem` — 34 bytes

| Offset | Campo | Tipo | Bytes |
|---:|---|---|---:|
| 12 | `SourType` | `int32` | 4 |
| 16 | `SourPos` | `int32` | 4 |
| 20 | `DestType` | `int32` | 4 |
| 24 | `DestPos` | `int32` | 4 |
| 28 | `GridX`, `GridY` | `uint16[2]` | 4 |
| 32 | `WarpID` | `uint16` | 2 |

Este é o pacote do refino por poeira (o cliente arrasta a poeira sobre o item), **não** `0x03A6`.

### 7.6. `MSG_TradingItem` — 20 bytes

| Offset | Campo | Tipo | Bytes |
|---:|---|---|---:|
| 12 | `DestPlace` | `uint8` | 1 |
| 13 | `DestSlot` | `uint8` | 1 |
| 14 | `SrcPlace` | `uint8` | 1 |
| 15 | `SrcSlot` | `uint8` | 1 |
| 16 | `WarpID` | `int32` | 4 |

### 7.7. `MSG_ApplyBonus` — 18 bytes

| Offset | Campo | Tipo | Bytes |
|---:|---|---|---:|
| 12 | `BonusType` | `int16` | 2 |
| 14 | `Detail` | `int16` | 2 |
| 16 | `TargetID` | `uint16` | 2 |

`BonusType`: 0 = score, 1 = special, 2 = skill. `Detail`: 0 = Str, 1 = Int, 2 = Dex, 3 = Con.

### 7.8. `MSG_CNFAccountLogin` — 2008 bytes (S→C)

Resposta de login de conta bem-sucedido: `Type = 266 (0x010A)`, `ID = 30002`, corpo de 1996 bytes. Layout de `MSG_DBCNFAccountLogin` (`Basedef.h:1412-1431`), reutilizado no envio ao cliente; tamanho e offsets conferidos com alinhamento natural MSVC x86. O padding final de 7 bytes existe porque `STRUCT_SELCHAR` contém `long long Exp[4]`, o que alinha a struct inteira em 8.

| Offset abs | Offset corpo | Campo | Tipo | Bytes |
|---:|---:|---|---|---:|
| 12 | 0 | `HashKeyTable` | `char[16]` | 16 |
| 28 | 16 | `Unknow_28` | `int32` | 4 |
| 32 | 20 | `sel` | `STRUCT_SELCHAR` | 840 |
| 872 | 860 | `Cargo` | `STRUCT_ITEM[128]` | 1024 |
| 1896 | 1884 | `Coin` | `int32` | 4 |
| 1900 | 1888 | `AccountName` | `char[16]` | 16 |
| 1916 | 1904 | `Keys` | `char[12]` | 12 |
| 1928 | 1916 | `QuestDiaria` | `STRUCT_QUEST` | 56 |
| 1984 | 1972 | `BlockPass` | `char[16]` | 16 |
| 2000 | 1988 | `IsBlocked` | `bool` | 1 |
| 2001 | 1989 | padding final | — | 7 |

`STRUCT_SELCHAR` (840 bytes): `SPX[4]` em 0, `SPY[4]` em 8, `Name[4][16]` em 16, `Score[4]` em 80, `Equip[4][16]` em 272, `Guild[4]` em 784, `Coin[4]` em 792 e `Exp[4]` em 808. `STRUCT_SCORE` tem 48 bytes: `Level` em 0, `AC` em 4, `Damage` em 8, `Merchant` em 12, `AttackRun` em 13, `Direction` em 14, `ChaosRate` em 15, `MaxHp` em 16, `MaxMp` em 20, `Hp` em 24, `Mp` em 28, `Str` em 32, `Int` em 34, `Dex` em 36, `Con` em 38 e `Special[4]` em 40. `STRUCT_ITEM` tem 8 bytes: `sIndex` em 0 e três pares efeito/valor em 2, 4 e 6.

No PoC, `HashKeyTable`, `Keys`, `QuestDiaria`, `BlockPass` e `IsBlocked` vão zerados e `Unknow_28` vale 1. Com PostgreSQL, `Cargo`, `Coin`, `AccountName` e `STRUCT_SELCHAR` vêm de `wyd.accounts`, `wyd.characters` e `wyd.items`; na conta demo em memória esses campos são sintéticos. O cliente usa os campos restantes para a tela de seleção e para o baú; preenchê-los exige captura/leitura adicional do cliente.

---

## 8. Protocolo interno TMSrv ↔ DBSrv

Mesma camada de transporte (INITCODE + HEADER + ofuscação), direções `0x0800`/`0x0400`. Não toca o cliente, mas define o contrato de persistência.

| Type | Constante | Sentido |
|---:|---|---|
| 2051 / `0x0803` | `_MSG_DBAccountLogin` | G→DB: valida conta |
| 1046 / `0x0416` | `_MSG_DBCNFAccountLogin` | DB→G: lista de personagens |
| 2052 / `0x0804` | `_MSG_DBCharacterLogin` | G→DB: carrega personagem |
| 1047 / `0x0417` | `_MSG_DBCNFCharacterLogin` | DB→G: personagem carregado |
| 2055 / `0x0807` | `_MSG_DBSaveMob` | G→DB: persiste `STRUCT_MOB` |
| 2054 / `0x0806` | `_MSG_SavingQuit` | G→DB: salva e desconecta |
| 3087 / `0x0C0F` | `_MSG_DBSendItem` | entrega de item/cash |
| 3089 / `0x0C11` | `_MSG_DBSendDonate` | donate/cash |

O link TMSrv↔BISrv é diferente: pacote cru de **196 bytes**, sem HEADER e sem ofuscação. O layout interno está marcado como não verificado no próprio repositório de referência; **não reimplementar sem captura**.

---

## 9. Checklist de compatibilidade de fio

1. [ ] Consumir `INITCODE` `0x1F11F311` em toda conexão nova.
2. [ ] Framing por `Size` com limites 12..8192 e drenagem em laço.
3. [ ] Encode/decode com `pKeyWord` idêntica e truncamento de 8 bits.
4. [ ] Checksum correto no envio; política de recepção decidida e documentada.
5. [ ] Reconhecer todos os `Type` de §6.1 e produzir os de §6.2 com os mesmos layouts.
6. [ ] Aceitar `ClientVersion == 7640`.
7. [ ] Ignorar `_MSG_Ping`; descartar `ClientTick == SKIPCHECKTICK`.
8. [ ] Validar `Size` contra o tamanho esperado de cada struct (especialmente `MSG_Attack`).
9. [ ] Fechar conexão em `ID` fora de `[0, 1000)`.
10. [ ] Não confiar em `CurrentHp`/`CurrentExp`/`CurrentMp` do cliente.

---

## 10. Plano de validação (fase seguinte)

Sem captura de tráfego real, os itens abaixo continuam sendo hipóteses:

1. **Golden vectors**: gravar uma sessão de login + seleção + movimento + ataque com o cliente 7662 e comparar byte-a-byte com o codec novo. O repositório de referência já possui um harness (`transport_vectors_test.go`); o nosso deve ter equivalente.
2. **Fuzz de framing**: alimentar o parser com frames truncados, `Size` gigante, `Size` zero e múltiplos frames colados.
3. **Diff de opcodes**: gerar a tabela a partir de `Basedef.h` e comparar com [spec/opcodes.yaml](../spec/opcodes.yaml) em CI, para detectar divergência quando a referência mudar.
4. **Confirmar `_MSG_UpdateScore`** e as structs marcadas como `(std)`/`(combine)` no dump de referência.

---

## 11. Resumo executivo

- O transporte do WYD é **simples e reproduzível**: 12 bytes de header, INITCODE fixo, framing por tamanho e uma ofuscação simétrica de tabela pública.
- O ponto perigoso não é a criptografia (não há), é a **variedade de layouts**: alinhamento natural vs `pack(1)`, tamanho variável de `MSG_Attack`, e flags de direção no `Type`.
- Um gateway em Go/Rust consegue cobrir 100% da camada de transporte em ~500–800 linhas, com testes de vetores dourados.
- A autoridade do servidor não vem do protocolo; vem de **recalcular** tudo o que o cliente alega.

---

**Próximo documento:** [03-DADOS-LEGADOS.md](03-DADOS-LEGADOS.md) — formatos de arquivo e structs de persistência.
