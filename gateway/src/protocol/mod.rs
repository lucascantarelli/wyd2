//! Constantes e codecs do protocolo CPSock.
//!
//! Todos os layouts são little-endian e usam offsets explícitos; nenhuma
//! struct Rust é transmitida diretamente.

pub mod codec;
pub mod framing;
pub mod keytable;
pub mod login;
pub mod selchar;
pub mod text;

/// `sizeof(HEADER)`.
pub const HEADER_SIZE: usize = 12;
/// `MAX_MESSAGE_SIZE`.
pub const MAX_MESSAGE_SIZE: usize = 8192;
/// Gate de versão enviado pelo cliente antes do primeiro frame.
pub const INIT_CODE: u32 = 0x1F11_F311;
/// `APP_VERSION` em `MSG_AccountLogin.ClientVersion` (layout de 104 bytes).
pub const APP_VERSION: i32 = 7640;
/// `ClientVersion` do cliente WYD Global (layout de 112 bytes).
pub const CLIENT_VERSION_GLOBAL: i32 = 0x0C9D_B301;
/// Tick que o cliente nunca deve enviar; frames com ele são descartados.
pub const SKIP_CHECK_TICK: u32 = 235_543_242;
/// `MAX_USER`: IDs válidos em `[0, 1000)`.
pub const MAX_USER: u16 = 1000;

/// `_MSG_AccountLogin` (C→S).
pub const MSG_ACCOUNT_LOGIN: u16 = 0x020D;
/// `_MSG_CharacterLogin` (C→S).
pub const MSG_CHARACTER_LOGIN: u16 = 0x0213;
/// `_MSG_Ping` (C→S, sem efeito).
pub const MSG_PING: u16 = 0x03A0;
/// `_MSG_MessagePanel` (S→C, `char String[128]`).
pub const MSG_MESSAGE_PANEL: u16 = 0x0101;
/// `_MSG_CNFAccountLogin` (S→C, resposta de login).
pub const MSG_CNF_ACCOUNT_LOGIN: u16 = 0x010A;
/// `_MSG_CharacterLoginFail` (S→C, `MSG_STANDARD`).
pub const MSG_CHARACTER_LOGIN_FAIL: u16 = 0x0119;

/// `MSG_MessagePanel.String` tem 128 bytes.
pub const MESSAGE_PANEL_LENGTH: usize = 128;
