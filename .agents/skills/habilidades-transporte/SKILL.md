---
name: habilidades-transporte
description: "Use quando a tarefa envolver protocolo ou gateway: INITCODE, framing, header, codec/pKeyWord, checksum, opcodes, MSG_AccountLogin, MSG_CNFAccountLogin, seleção de personagem ou o servidor TCP em Rust."
metadata:
  category: wyd-next-gen
---

# Habilidades — Transporte, Protocolo e Gateway (WYD)

> Base para as habilidades de transporte: INITCODE, framing, codec, tabela pKeyWord, checksum, header, opcodes, login de conta, MSG_CNFAccountLogin, e o gateway em Rust (Fase 3).

---

## Quando usar

- Implementar ou depurar INITCODE, framing, header, checksum, codec ou pKeyWord.
- Adicionar ou alterar mensagem `MSG_*`, opcode ou layout de pacote.
- Investigar login, `MSG_CNFAccountLogin` ou seleção de personagem no gateway Rust.
- Capturar tráfego real e comparar bytes com o cliente (R02).

## 1. Contexto

O protocolo do WYD é TCP bruto com handshake de 4 bytes fixo (`0x1F11F311`), header de 12 bytes, framing por `Size` (12..8192), tabela de ofuscação simétrica `pKeyWord[512]` (512 bytes = dado público de protocolo), e checksum. As mensagens são `MSG_*`; o login de conta é `MSG_AccountLogin` (`0x020D`) e a resposta é `MSG_CNFAccountLogin` (`0x010A`) de 2008 bytes com `STRUCT_SELCHAR` e cargo.

---

## 2. Habilidades de transporte

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **INITCODE** | 4 bytes `0x1F11F311`; sem troca de chaves; handshake fixo. | socket → handshake. | Fase 3+. |
| **Header** | 12 bytes: type, size, checksum, etc. | pacote → header. | Fase 3+. |
| **Framing** | Por `Size` (12..8192); bytes parciais/colados; timeout e limpeza de sessão. | stream → frames. | Fase 3+. |
| **Tabela pKeyWord** | Ofuscação simétrica; checksum; tabela pública de 512 bytes (não criptografia de verdade). | payload → ofuscado. | Fase 3+. |

---

## 3. Habilidades de mensagem

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **MSG_AccountLogin** | Login de conta: login, senha, ClientVersion==7640. | pacote → login. | Fase 3+. |
| **MSG_CNFAccountLogin** | Resposta de 2008 bytes: STRUCT_SELCHAR, cargo, equip, guild, scores. | conta → CNF. | Fase 3+; CNF parcial (HashKeyTable, Keys, QuestDiaria, BlockPass, IsBlocked, Unknow_28 zerados). |
| **MSG_CharacterLogin** | Entrada no mundo; ainda não implementada no PoC (devolve falha controlada). | character → mundo. | Pendente. |
| **Opcodes** | 197 opcodes mapeados; `spec/opcodes.yaml` gerado por script; `value` e `base`, direções, handler. | opcode → contrato. | Fase 1+. |

---

## 4. Habilidades de gateway

| Skill | O que faz | Entrada / saída | Limite esta fase |
|---|---|---|---|
| **Transporte (Rust)** | INITCODE + framing + codec + login + CNF. | socket → protocolo. | Fase 3. |
| **Diretório** | DemoDirectory (memória) ou PostgresDirectory (PostgreSQL); trait Directory. | login → Account. | Fase 3. |
| **PostgreSQL** | Lê de wyd.accounts, wyd.characters, wyd.items; verifica hash; rejeita erro de banco sem vazar detalhes; sem vazar a connection string no log. | connection string → Account. | Fase 3; sem pool/TLS nesta fase. |
| **Pool (Fase 3+)** | Pool PostgreSQL com reconexão, timeout e envenenamento controlado. | connection string → pool. | Pendente. |

---

## 5. Limitações e riscos

- **Sem golden vectors reais:** o gateway é verificado contra o layout documentado, mas sem vetor capturado do cliente não se sabe se o 7662 aceita o que o servidor devolve (especialmente os campos zerados do CNF).
- **Sem mundo:** CharacterLogin devolve falha controlada; sem snapshot, spawn, persistência de sessão.
- **Sem TLS no cliente:** protocolo legado não tem criptografia; o gateway não deve ser exposto à internet sem camada de proteção.
- **Banco sem pool/TLS e com uma conexão:** suficiente para o PoC; pool, reconexão e TLS ficam para a versão de carga.
- **CNF parcial:** pode ser insuficiente para funcionalidades além da seleção; decidir quando completar.

---

## 6. Referências

- `docs/02-PROTOCOLO.md` — transporte, header, codec, opcodes, structs.
- `spec/opcodes.yaml` — 197 opcodes com valor de fio, direções, handler.
- `spec/constants.yaml` — constantes de transporte, limites, versão.
- `gateway/` — gateway TCP em Rust (Fase 3): transporte + login + PostgreSQL.
- `gateway/src/protocol/` — login, selchar, header, codec.
- `gateway/src/server.rs` — roteamento, handle, timeout.
- `gateway/src/directory.rs` — DemoDirectory, PostgresDirectory.
- `gateway/tests/` — e2e, postgres, fixtures.

