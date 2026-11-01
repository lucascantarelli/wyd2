# 08 — Cliente Alvo: WYD Global

> **Decisão registrada:** o cliente alvo do projeto é o **WYD Global** fornecido em
> `reference/WYD Global`. Este documento registra o que foi medido nesse cliente, o que
> muda em relação à especificação derivada do build 7662, e o que ainda precisa ser
> confirmado por captura.
>
> **Legenda:** ✅ verificado no arquivo · 🟡 derivado/medido com inferência · ⚠️ não verificado

---

## 1. Por que este documento existe

Toda a especificação de protocolo ([02-PROTOCOLO.md](02-PROTOCOLO.md)) e de dados legados
([03-DADOS-LEGADOS.md](03-DADOS-LEGADOS.md)) foi derivada do código do servidor 7662
(`reference/w2pp-OpenWYD`). O cliente que o projeto quer atender, porém, **não é o cliente
7662**: é uma build posterior, distribuída como *WYD Global*, com formatação de dados e
UI diferentes.

Isso não invalida a pesquisa: o transporte (INITCODE, header de 12 bytes, `pKeyWord`,
checksum) e boa parte das fórmulas continuam sendo os mesmos conceitos. O que muda é o
**contrato exato**: layouts de struct, tamanho das tabelas, catálogo de opcodes e o
handshake de versão precisam ser reverificados contra este cliente — não presumidos.

---

## 2. Inventário medido ✅

| Item | Valor |
|---|---|
| Caminho | `reference/WYD Global` (gitignored) |
| Arquivos | 10.054 |
| Tamanho em disco | 964 MB |
| Executável principal | `WYD.exe` — 6.494.000 bytes |
| Executável de configuração | `WydConfig.exe` + `WydConfig.swf` (Adobe AIR) |
| Updater | `Updater.exe` (7.168 bytes) |
| Proteção | `JProtectDll.dll` (45.056 bytes) |
| Localização | `Lang/EN` e `Lang/PT` (strings de quest, UI e descrição de classe em português) |

Arquivos de topo relevantes: `ItemList.bin`, `SkillData.bin`, `ItemSet.bin`, `MountData.bin`,
`MountDataV.bin`, `CollectionData.bin`, `ArenaVisualData.bin`, `Missionitems.bin`,
`ItemPrice.bin`, `InitItem.bin`, `HeightMap.dat`, `NQuickSLot_01.bin`, `Mixlist.bin`,
`EventCoupon.bin`.

Diretórios: `Env/` (mapas `Field####.dat` + `.trn`), `NUI/` (UI nova), `UI/`, `mesh/`,
`Effect/`, `sound/`, `music/`, `shader/`, `Lang/`, `Adobe AIR/`, `META-INF/`.

### 2.1. Canal de atualização ✅

`config.json` na raiz do cliente:

```json
{
  "path": ".",
  "infoJson": "https://d16tndoz98nwcc.cloudfront.net/info.json",
  "gameId": "Global"
}
```

Ou seja: o cliente consulta um canal de atualização (`gameId: "Global"`) hospedado em
CloudFront. Qualquer trabalho de "rodar contra um servidor de teste" precisa levar isso em
conta: antes de falar com o servidor de jogo, o cliente pode exigir um `info.json` válido —
🟡 a confirmar na captura ([R02](../roadmap/issues/R02.md)).

### 2.2. Origem da build ✅

`WYD.exe` contém o caminho de símbolos:

```text
H:\WYD_PC\WYD_ClientNew\Client\run\SD.pdb
```

🟡 Derivado: a árvore de origem é `WYD_ClientNew` — uma linha de cliente **nova**, não a
árvore 7662 coberta pela especificação atual.

⚠️ Não foi encontrado marcador textual de versão de protocolo (`7640`, `7662`) em texto
claro no `WYD.exe`. Não se conclui ausência de versão: conclui-se que ela não está em
string simples (pode estar em recurso comprimido, em `Config.bin` ou protegida por
`JProtectDll.dll`).

---

## 3. Divergências de dados medidas ✅

As tabelas vêm **só** em `.bin` (não há `.csv` no cliente), e o `.bin` continua sendo
XOR `0x5A` — o mesmo transform do 7662. Tamanhos:

| Arquivo | Tamanho | Leitura |
|---|---:|---|
| `ItemList.bin` | 2.494.004 B | ✅ **Decodificado:** 14.500 registros de 172 B + trailer `int32` cru. Layout em [03-DADOS-LEGADOS.md](03-DADOS-LEGADOS.md) §6.7.2. |
| `SkillData.bin` | 25.796 B | ✅ **Decodificado:** 248 registros de 104 B + trailer `int32` cru (o `nRand` do 7662). Layout em [03-DADOS-LEGADOS.md](03-DADOS-LEGADOS.md) §6.7.1. |
| `MountData.bin` | 70.004 B | Sem equivalente documentado no 7662 (`MountDataV.bin` também é novo). |
| `ItemSet.bin` | 928.004 B | Sem layout documentado nesta especificação. |
| `Missionitems.bin` | 26.880.000 B | Sem layout documentado. |
| `CollectionData.bin` | 23.520 B | Sem layout documentado. |
| `InitItem.bin` | 1.000 B | Divisível em 100 registros de 10 B (`26 ff 28 ff 28 fe ff ff ff ff`); a semântica dos campos não foi identificada. |

Consequências práticas:

1. `SkillData.bin` e `ItemList.bin` já têm decodificador com round-trip exato
   ([importer/client_tables.py](../importer/client_tables.py), testado em
   [tests/test_client_tables.py](../tests/test_client_tables.py)). O pipeline de migração
   (`migrate`/`emit`) ainda **não** consome essas tabelas — elas não entram no `load.sql`.
2. `data/` (XP, refino, coeficientes) continua válido como **comportamento** extraído do
   servidor 7662, mas precisa de contraprova no cliente novo antes de virar paridade.
3. Os demais `.bin` (`MountData`, `ItemSet`, `Missionitems`, `CollectionData`) continuam sem
   layout; qualquer decodificador novo tem de seguir o mesmo método: medir, round-trip, só
   então nomear campo.

### 3.1. Mapas e UI ✅

- `Env/` contém pares `Field0101.dat/.trn`, `Field0102`, `Field0104`, `Field0124`,
  `Field0129`, `Field0131`, `Field0202`, `Field0204` etc., além de `AttributeMap.dat`,
  `Character.dat` e `Character.trn`. A numeração de mapa (`FieldNNNN`) é o identificador
  que o servidor precisa devolver no spawn.
- `UI/` tem 328 telas no formato `.wyt` clássico; `NUI/` acrescenta **20** contêineres `.wyt`
  com magic `WT10` (`ServerList.wyt`, `main.wyt`, `ItemRefine.wyt`, `Combine3.wyt`,
  `Combine4.wyt`, `arena.wyt`, `Collection.wyt`, `ItemOS.wyt`, `GameConfig.wyt`…).
  🟡 São esses nomes que dão a tela correspondente a cada opcode de refino, combine,
  arena e coleção — a confirmar com captura.

---

## 4. O que isso muda no projeto

| Área | Antes (assumido do 7662) | Agora (cliente WYD Global) |
|---|---|---|
| Versão anunciada no login | `APP_VERSION 7640` fixo | ✅ `0x0C9DB301` e corpo de **112 B** (não 104); medido na §6.1 |
| `MSG_CNFAccountLogin` (2.008 B) | layout do 7662 | ⚠️ validar tamanho e campos |
| Catálogo de opcodes (197) | derivado do servidor 7662 | 🟡 provável superconjunto; validar por captura |
| `STRUCT_SPELL` (84 B) | tabela de skills | ✅ 104 B no cliente novo; layout re-derivado (§6.7.1) |
| `ItemList` (140 B/registro) | `.csv` autoritativo | ✅ 172 B no cliente novo; layout re-derivado (§6.7.2) |
| Tabelas `data/` | extraídas do servidor 7662 | 🟡 manter como referência de comportamento, contraprovar |
| Telas (refino, combine) | descritas por handler | ✅ existem como `NUI/*.wyt` — dá para mapear tela ↔ opcode |
| Launcher/updater | não modelado | ✅ `config.json` + CloudFront; modelar antes de testar com cliente real |

---

## 5. O que continua valendo sem alteração ✅

- Transporte: `INITCODE` `0x1F11F311`, frame com `Size` (WORD), transform por `pKeyWord`,
  checksum e header de 12 bytes — são características do protocolo, não de uma build.
- Semântica de conta/personagem: login de conta, seleção de personagem, cargo, equipamento.
- Fórmulas de combate/progressão extraídas do servidor: continuam sendo a **melhor
  hipótese** de comportamento, a confirmar por golden cases.

> **Regra:** tudo que este documento marca como ⚠️ ou 🟡 entra na issue
> [R02](../roadmap/issues/R02.md) como pergunta a fechar por captura, não como suposição a
> implementar.

---

## 6. Como fechar as lacunas

1. **Identificar a build/protocolo.** Ler `Config.bin`, recursos do `WYD.exe` e o
   `info.json` do updater; registrar o que for encontrado. Não inventar número.
   ✅ **Feito:** `Config.bin` (32 B) e `info.json` não carregam a versão de protocolo; o
   executável não tem recurso de versão nem os imediatos `7640`/`7662`. O updater anuncia
   a build **741** (`info.json → games.Global.version`), que é versão de patch, não de
   protocolo. A versão real veio da captura: `0x0C9DB301` (§6.1).
2. ~~**Capturar o handshake.**~~ ✅ **Feito em 2026-11-01** (§6.1): `INITCODE` confirmado,
   `MSG_AccountLogin` de **112 B** com `ClientVersion = 0x0C9DB301`, checksum conferindo em
   três capturas e dois processos. A ferramenta é
   [`scripts/capture_login.py`](../scripts/capture_login.py); falta o `CNF` de resposta.
3. **Golden vectors** de login, `CNF` e seleção — comparar bytes, não "parece igual".
   ✅ O login do WYD Global virou vetor congelado em
   [gateway/tests/fixtures/account_login_global.hex](../gateway/tests/fixtures/account_login_global.hex)
   (sintético: `TestAccount`, token de 22 B zerado); `CNF` e seleção continuam pendentes.
4. ~~**Decodificar as tabelas** `ItemList.bin` e `SkillData.bin`~~ ✅ **feito** (round-trip exato;
   layout em [03-DADOS-LEGADOS.md](03-DADOS-LEGADOS.md) §6.7). Falta a semântica dos campos
   marcados ⚠️/🟡 ali.
5. Decidir se o importador passa a ler o catálogo do cliente novo (hoje ele só lê o `.csv` do
   7662) e como o `schema/001_init.sql` recebe itens e skills.

### 6.1. Endpoint medido e captura do login (2026-11-01) ✅

Com o cliente aberto, `netstat -ano` mostrou uma única conexão do processo:

| Campo | Valor |
|---|---|
| Processo | `WYD.exe` (PID 8936) |
| Local | `192.168.100.7:51889` |
| Remoto | `92.38.151.230:8281` (`ESTABLISHED`) |

- A porta do canal é **8281**; 7640 é a *versão* de protocolo, não a porta. O gateway já
  escuta em `0.0.0.0:8281` (`gateway/src/main.rs`), então a porta não é lacuna.
- No momento da medição o cliente mantinha **uma** conexão TCP (🟡 provável canal único de
  login/seleção/mundo); não havia um segundo canal de lista de servidores.

**Captura.** Com o cliente fechado, o destino foi desviado para
[`scripts/capture_login.py`](../scripts/capture_login.py) com um alias temporário de IP na
loopback (removido depois), e o login foi refeito com credenciais descartáveis:

| Amostra | Processo | `KeyWord` | `CheckSum` | Corpo |
|---|---|---|---|---|
| 1 | PID 8868 | `0xA6` | ✅ | 112 B |
| 2 | PID 8868 | `0xF2` | ✅ | 112 B |
| 3 | PID 14788 | `0xEB` | ✅ | 112 B |

`INITCODE = 0x1F11F311`, `Size = 124`, `Type = 0x020D` (`MSG_AccountLogin`), `id = 0`.

Layout medido do corpo (o do 7662 tem 104 B):

| Offset | Tam. | Campo | Valor medido |
|---|---|---|---|
| `0x00` | 12 | `Pass` | texto, NUL-padded |
| `0x0C` | 16 | `Name` | texto, NUL-padded |
| `0x1C` | 52 | `Zero` (reservado) | zeros |
| `0x50` | 4 | `ClientVersion` | **`0x0C9DB301`** (211.661.569), constante |
| `0x54` | 4 | `DBNeedSave` | `1` |
| `0x58` | 22 | token do processo | igual entre logins do mesmo processo, muda ao reiniciar |
| `0x6E` | 2 | reservado | zeros |

O que a captura prova:

- ✅ O `INITCODE` e o header de 12 bytes estão certos; o checksum do codec confere nas três
  amostras.
- ✅ O cliente **não anuncia 7640**: `ClientVersion` é `0x0C9DB301`. O mesmo build foi aceito
  em sessão pelo servidor real, então esse é o valor que o servidor espera.
- 🟡 O bloco de 22 B em `0x58` é fingerprint/token por processo (hash + `u16`), não versão:
  ficou idêntico nas amostras 1 e 2 e mudou na 3, após reiniciar o cliente.
- ✅ O corpo cresceu 8 B. Implementar o `MSG_AccountLogin` do 7662 ao pé da letra recusa
  este cliente por tamanho.

**Golden vector.** O handshake medido virou um vetor congelado de 128 B em
[`gateway/tests/fixtures/account_login_global.hex`](../gateway/tests/fixtures/account_login_global.hex):
mesmo `INITCODE`, `Type`, `id`, `ClientTick` e `KeyWord` (`0xEB`) da amostra 3, corpo sintético
(`TestAccount`/`Secret123!`), token de 22 B em `0x58` zerado e `CheckSum` recalculado. O teste
[`gateway/tests/e2e.rs`](../gateway/tests/e2e.rs) decodifica o vetor, confere os offsets,
re-codifica byte a byte e o envia a um gateway real, exigindo `MSG_CNFAccountLogin` de 2.008 B.

Falta na R02: o `CNF` de resposta, a seleção de personagem e o fuzz de framing.

> ⚠️ `out/capture/` contém a senha em texto plano. Os arquivos ficam fora do git; não
> versionar e apagar depois de gerar o golden vector com credenciais sintéticas.

---

## 7. Licenciamento e postura

O cliente é proprietário e **não** é redistribuído por este projeto: `reference/` está no
`.gitignore` desde o primeiro commit. Ele é usado como **oráculo de comportamento**
(observar o que o jogo faz), nunca como fonte de código a copiar — a mesma regra
clean-room de [01-FONTES-E-METODOLOGIA.md](01-FONTES-E-METODOLOGIA.md).

Rodar um servidor próprio para um cliente de terceiros é uma decisão de operação e de
licença, registrada em [R10](../roadmap/issues/R10.md). Nada neste documento autoriza
operação pública.

---

**Voltar ao índice:** [00-INDICE.md](00-INDICE.md) · **Decisão de produto:** [R01](../roadmap/issues/R01.md)
