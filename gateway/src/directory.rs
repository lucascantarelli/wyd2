//! Diretório de contas do gateway.
//!
//! `DemoDirectory` mantém a conta de demonstração em memória. `PostgresDirectory`
//! (módulo separado) lê `wyd.accounts`, `wyd.characters` e `wyd.items`. A trait
//! `Directory` permite testar o servidor sem banco.

use std::error::Error;
use std::fmt;

use crate::protocol::selchar::{SelChar, WireItem, CARGO_SLOTS};

/// Falha ao consultar o diretório. O texto vai para o log do operador, nunca
/// para o cliente.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DirectoryError {
    Unavailable(String),
    Query(String),
    /// Falha no pool de conexões PostgreSQL: reconexão, timeout, envenenado.
    Pool(String),
}

impl fmt::Display for DirectoryError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Unavailable(message) => write!(f, "diretorio indisponivel: {message}"),
            Self::Query(message) => write!(f, "consulta de conta falhou: {message}"),
            Self::Pool(message) => write!(f, "pool do banco: {message}"),
        }
    }
}

impl Error for DirectoryError {}

impl From<String> for DirectoryError {
    fn from(source: String) -> Self {
        Self::Pool(source)
    }
}

pub type DirectoryResult<T> = Result<T, DirectoryError>;

pub trait Directory: Send + Sync {
    fn find(&self, login: &str) -> DirectoryResult<Option<Account>>;
}

/// Como a senha da conta é conferida.
#[derive(Clone)]
pub enum Credential {
    /// Somente a conta demo em memória. A senha é pública na documentação e
    /// não existe fora do processo.
    DemoPlaintext(Vec<u8>),
    /// Hash PHC gravado pelo importador (`accounts.password_hash`).
    PasswordHash(String),
}

impl fmt::Debug for Credential {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::DemoPlaintext(_) => f.write_str("DemoPlaintext(<redacted>)"),
            Self::PasswordHash(_) => f.write_str("PasswordHash(<redacted>)"),
        }
    }
}

#[derive(Clone)]
pub struct Account {
    pub login: String,
    pub credential: Credential,
    pub blocked: bool,
    pub characters: Vec<SelChar>,
    pub cargo_coin: i32,
    pub cargo: [WireItem; CARGO_SLOTS],
}

impl fmt::Debug for Account {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Account")
            .field("login", &self.login)
            .field("credential", &self.credential)
            .field("blocked", &self.blocked)
            .field("characters", &self.characters)
            .field("cargo_coin", &self.cargo_coin)
            .finish_non_exhaustive()
    }
}

#[derive(Debug, Clone, Default)]
pub struct DemoDirectory {
    accounts: Vec<Account>,
}

impl DemoDirectory {
    /// Conta demo com dois personagens. Serve para exercitar o login e a
    /// tela de seleção sem banco; não é um cadastro.
    pub fn with_demo_account(login: impl Into<String>, password: impl Into<String>) -> Self {
        Self {
            accounts: vec![demo_account(login.into(), password.into())],
        }
    }

    pub fn with_account(mut self, account: Account) -> Self {
        self.accounts.push(account);
        self
    }

    pub fn is_empty(&self) -> bool {
        self.accounts.is_empty()
    }
}

impl Directory for DemoDirectory {
    fn find(&self, login: &str) -> DirectoryResult<Option<Account>> {
        Ok(self
            .accounts
            .iter()
            .find(|account| account.login.eq_ignore_ascii_case(login))
            .cloned())
    }
}

fn demo_account(login: String, password: String) -> Account {
    let mut hero = SelChar::new(0, "Hero");
    hero.spx = 100;
    hero.spy = 200;
    hero.level = 50;
    hero.max_hp = 1200;
    hero.hp = 700;
    hero.max_mp = 600;
    hero.mp = 250;
    hero.strength = 31;
    hero.intelligence = 11;
    hero.dexterity = 21;
    hero.constitution = 26;
    hero.direction = 0;
    hero.ac = 12;
    hero.damage = 25;
    hero.special = [1, 2, 3, 4];
    hero.coin = 1500;
    hero.exp = 250_000;
    hero.equip[0] = WireItem {
        index: 100,
        effects: [(43, 230), (1, 5), (0, 0)],
    };
    hero.equip[1] = WireItem {
        index: 101,
        effects: [(2, 7), (0, 0), (0, 0)],
    };

    let mut mage = SelChar::new(1, "Mage");
    mage.spx = 110;
    mage.spy = 210;
    mage.level = 10;
    mage.max_hp = 200;
    mage.hp = 150;
    mage.max_mp = 800;
    mage.mp = 700;
    mage.coin = 500;
    mage.exp = 1000;

    Account {
        login,
        credential: Credential::DemoPlaintext(password.into_bytes()),
        blocked: false,
        characters: vec![hero, mage],
        cargo_coin: 500,
        cargo: [WireItem::default(); CARGO_SLOTS],
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::selchar::EQUIP_SLOTS;

    #[test]
    fn busca_login_sem_case() {
        let directory = DemoDirectory::with_demo_account("TestAccount", "Secret123!");
        assert!(directory.find("testaccount").unwrap().is_some());
        assert!(directory.find("TESTACCOUNT").unwrap().is_some());
        assert!(directory.find("outra").unwrap().is_none());
    }

    #[test]
    fn conta_demo_tem_dois_personagens() {
        let directory = DemoDirectory::with_demo_account("TestAccount", "Secret123!");
        let account = directory.find("TestAccount").unwrap().unwrap();
        assert_eq!(account.characters.len(), 2);
        assert_eq!(account.characters[0].name, "Hero");
        assert_eq!(account.characters[0].equip[0].index, 100);
        assert_eq!(account.cargo_coin, 500);
        assert_eq!(account.cargo.len(), CARGO_SLOTS);
        assert_eq!(account.characters[0].equip.len(), EQUIP_SLOTS);
        assert!(!account.blocked);
        assert!(matches!(account.credential, Credential::DemoPlaintext(_)));
    }

    #[test]
    fn debug_nao_expoe_senha_nem_hash() {
        let directory = DemoDirectory::with_demo_account("TestAccount", "Secret123!");
        let account = directory.find("TestAccount").unwrap().unwrap();
        let rendered = format!("{account:?}");
        assert!(!rendered.contains("Secret123!"));
        assert!(rendered.contains("<redacted>"));
    }
}
