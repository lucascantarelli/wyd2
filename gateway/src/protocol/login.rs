//! `MSG_AccountLogin` (C→S, Type `0x020D`).
//!
//! Dois layouts são aceitos:
//!
//! - **7662**: corpo de 104 bytes, `ClientVersion == 7640`;
//! - **WYD Global**: corpo de 112 bytes, `ClientVersion == 0x0C9DB301`,
//!   medido em 2026-11-01 (`docs/08-CLIENTE-ALVO.md` §6.1). Os 22 bytes
//!   depois de `DBNeedSave` são um token por processo e não são interpretados.
//!
//! O layout é escolhido pelo tamanho do corpo; a versão esperada vem dele.
//! A senha viaja em texto plano no fio — o gateway só a compara e nunca a
//! registra.

use std::fmt;

use super::text::c_string;
use super::{APP_VERSION, CLIENT_VERSION_GLOBAL};

/// Corpo do `MSG_AccountLogin` do 7662.
pub const LEGACY_BODY_SIZE: usize = 104;
/// Corpo do `MSG_AccountLogin` do cliente WYD Global.
pub const GLOBAL_BODY_SIZE: usize = 112;
/// Alias mantido para fixtures e testes do layout do 7662.
pub const ACCOUNT_LOGIN_BODY_SIZE: usize = LEGACY_BODY_SIZE;

/// Layout reconhecido pelo tamanho do corpo.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LoginLayout {
    /// 7662: 104 bytes, `ClientVersion == 7640`.
    Legacy,
    /// WYD Global: 112 bytes, `ClientVersion == 0x0C9DB301`.
    Global,
}

impl LoginLayout {
    /// Versão que este layout deve anunciar.
    pub const fn expected_version(self) -> i32 {
        match self {
            Self::Legacy => APP_VERSION,
            Self::Global => CLIENT_VERSION_GLOBAL,
        }
    }

    /// Versão esperada em texto, para a mensagem de erro.
    pub const fn expected_version_text(self) -> &'static str {
        match self {
            Self::Legacy => "7640 (7662)",
            Self::Global => "0x0C9DB301 (WYD Global)",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AccountLogin {
    /// Senha decodificada de cp1252 para UTF-8, como o importador a hasheou.
    pub password: String,
    pub name: String,
    pub client_version: i32,
    pub db_need_save: i32,
    /// Só existe no layout do 7662; zeros no WYD Global.
    pub adapter_name: [i32; 4],
    pub layout: LoginLayout,
}

impl AccountLogin {
    /// Lê o corpo de 104 ou 112 bytes. O frame já foi verificado pelo framer.
    pub fn parse(body: &[u8]) -> Result<Self, LoginError> {
        let layout = match body.len() {
            LEGACY_BODY_SIZE => LoginLayout::Legacy,
            GLOBAL_BODY_SIZE => LoginLayout::Global,
            got => return Err(LoginError::BadSize { got }),
        };

        let password = c_string(&body[0..12]);
        let name = c_string(&body[12..28]);
        let client_version = i32::from_le_bytes([body[80], body[81], body[82], body[83]]);
        let db_need_save = i32::from_le_bytes([body[84], body[85], body[86], body[87]]);
        let adapter_name = match layout {
            LoginLayout::Legacy => {
                let mut slots = [0i32; 4];
                for (index, slot) in slots.iter_mut().enumerate() {
                    let offset = 88 + index * 4;
                    *slot = i32::from_le_bytes([
                        body[offset],
                        body[offset + 1],
                        body[offset + 2],
                        body[offset + 3],
                    ]);
                }
                slots
            }
            LoginLayout::Global => [0i32; 4],
        };

        Ok(Self {
            password,
            name,
            client_version,
            db_need_save,
            adapter_name,
            layout,
        })
    }

    /// Rejeita nome/senha vazios e versão incompatível com o layout.
    pub fn validate(&self) -> Result<(), LoginError> {
        if self.name.is_empty() {
            return Err(LoginError::EmptyName);
        }
        if self.password.is_empty() {
            return Err(LoginError::EmptyPassword);
        }
        if self.client_version != self.layout.expected_version() {
            return Err(LoginError::BadVersion {
                got: self.client_version,
                layout: self.layout,
            });
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LoginError {
    BadSize { got: usize },
    EmptyName,
    EmptyPassword,
    BadVersion { got: i32, layout: LoginLayout },
}

impl fmt::Display for LoginError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::BadSize { got } => {
                write!(
                    f,
                    "MSG_AccountLogin com {got} bytes; esperado {LEGACY_BODY_SIZE} (7662) \
                     ou {GLOBAL_BODY_SIZE} (WYD Global)"
                )
            }
            Self::EmptyName => write!(f, "nome de conta vazio"),
            Self::EmptyPassword => write!(f, "senha vazia"),
            Self::BadVersion { got, layout } => {
                write!(
                    f,
                    "ClientVersion {got}; esperado {}",
                    layout.expected_version_text()
                )
            }
        }
    }
}

impl std::error::Error for LoginError {}

#[cfg(test)]
mod tests {
    use super::*;

    fn body_with(name: &str, password: &str, version: i32, size: usize) -> Vec<u8> {
        let mut body = vec![0u8; size];
        body[..password.len()].copy_from_slice(password.as_bytes());
        body[12..12 + name.len()].copy_from_slice(name.as_bytes());
        body[80..84].copy_from_slice(&version.to_le_bytes());
        body
    }

    fn body(name: &str, password: &str, version: i32) -> Vec<u8> {
        body_with(name, password, version, LEGACY_BODY_SIZE)
    }

    #[test]
    fn le_campos_nos_offsets_do_corpo() {
        let raw = body("TestAccount", "Secret123!", APP_VERSION);
        let login = AccountLogin::parse(&raw).unwrap();
        assert_eq!(login.name, "TestAccount");
        assert_eq!(login.password, "Secret123!");
        assert_eq!(login.client_version, APP_VERSION);
        assert_eq!(login.layout, LoginLayout::Legacy);
        login.validate().unwrap();
    }

    #[test]
    fn aceita_layout_global_de_112_bytes() {
        let raw = body_with(
            "TestAccount",
            "Secret123!",
            CLIENT_VERSION_GLOBAL,
            GLOBAL_BODY_SIZE,
        );
        let login = AccountLogin::parse(&raw).unwrap();
        assert_eq!(login.name, "TestAccount");
        assert_eq!(login.client_version, CLIENT_VERSION_GLOBAL);
        assert_eq!(login.layout, LoginLayout::Global);
        assert_eq!(login.adapter_name, [0; 4]);
        login.validate().unwrap();
    }

    #[test]
    fn rejeita_versao_diferente_no_layout_legado() {
        let login = AccountLogin::parse(&body("TestAccount", "x", 1)).unwrap();
        assert_eq!(
            login.validate(),
            Err(LoginError::BadVersion {
                got: 1,
                layout: LoginLayout::Legacy
            })
        );
    }

    #[test]
    fn rejeita_versao_global_no_corpo_do_7662() {
        let raw = body("TestAccount", "x", CLIENT_VERSION_GLOBAL);
        let login = AccountLogin::parse(&raw).unwrap();
        assert_eq!(
            login.validate(),
            Err(LoginError::BadVersion {
                got: CLIENT_VERSION_GLOBAL,
                layout: LoginLayout::Legacy
            })
        );
    }

    #[test]
    fn rejeita_versao_7640_no_corpo_global() {
        let raw = body_with("TestAccount", "x", APP_VERSION, GLOBAL_BODY_SIZE);
        let login = AccountLogin::parse(&raw).unwrap();
        assert_eq!(
            login.validate(),
            Err(LoginError::BadVersion {
                got: APP_VERSION,
                layout: LoginLayout::Global
            })
        );
    }

    #[test]
    fn rejeita_tamanho_errado() {
        for size in [0, 103, 110, 113] {
            assert_eq!(
                AccountLogin::parse(&vec![0u8; size]),
                Err(LoginError::BadSize { got: size })
            );
        }
    }

    #[test]
    fn rejeita_nome_ou_senha_vazios() {
        assert_eq!(
            AccountLogin::parse(&body("", "x", APP_VERSION))
                .unwrap()
                .validate(),
            Err(LoginError::EmptyName)
        );
        assert_eq!(
            AccountLogin::parse(&body("x", "", APP_VERSION))
                .unwrap()
                .validate(),
            Err(LoginError::EmptyPassword)
        );
    }
}
