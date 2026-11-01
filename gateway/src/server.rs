//! Servidor TCP do PoC.
//!
//! Uma thread por conexão é suficiente para validar o fio. A troca por
//! Tokio/métricas fica para quando o gateway tiver carga real.

use std::io::{self, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use crate::directory::{Account, Credential, Directory};
use crate::hashing;
use crate::protocol::codec::{self, Header};
use crate::protocol::framing::{FrameError, Framer};
use crate::protocol::login::AccountLogin;
use crate::protocol::selchar::{encode_cnf_body, ID_SEL_CHAR};
use crate::protocol::text::write_c_string;
use crate::protocol::{
    MAX_USER, MESSAGE_PANEL_LENGTH, MSG_ACCOUNT_LOGIN, MSG_CHARACTER_LOGIN,
    MSG_CHARACTER_LOGIN_FAIL, MSG_CNF_ACCOUNT_LOGIN, MSG_MESSAGE_PANEL, MSG_PING, SKIP_CHECK_TICK,
};
use crate::rate_limit::FailureWindow;

/// Falhas de login toleradas por chave (IP ou conta) na janela padrao.
const DEFAULT_LOGIN_ATTEMPTS: u32 = 10;
const DEFAULT_LOGIN_WINDOW: Duration = Duration::from_secs(60);

pub struct Gateway {
    directory: Arc<dyn Directory>,
    timeout: Duration,
    login_failures: Mutex<FailureWindow>,
}

impl Gateway {
    pub fn new(directory: Arc<dyn Directory>) -> Self {
        Self {
            directory,
            timeout: Duration::from_secs(30),
            login_failures: Mutex::new(FailureWindow::new(
                DEFAULT_LOGIN_ATTEMPTS,
                DEFAULT_LOGIN_WINDOW,
            )),
        }
    }

    pub fn with_timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }

    /// Troca a janela de falhas de login; usado nos testes.
    pub fn with_login_limit(mut self, attempts: u32, window: Duration) -> Self {
        self.login_failures = Mutex::new(FailureWindow::new(attempts, window));
        self
    }

    /// Aceita conexões indefinidamente, uma thread por cliente.
    pub fn serve(self: Arc<Self>, listener: TcpListener) {
        for incoming in listener.incoming() {
            match incoming {
                Ok(stream) => {
                    let gateway = Arc::clone(&self);
                    thread::spawn(move || {
                        if let Err(err) = gateway.handle_connection(stream) {
                            eprintln!("[gateway] conexao encerrada com erro: {err}");
                        }
                    });
                }
                Err(err) => eprintln!("[gateway] accept falhou: {err}"),
            }
        }
    }

    /// Atende uma conexão até EOF, erro de protocolo ou falha de login.
    pub fn handle_connection(&self, stream: TcpStream) -> io::Result<()> {
        let peer = stream.peer_addr().ok();
        stream.set_read_timeout(Some(self.timeout))?;
        stream.set_write_timeout(Some(self.timeout))?;
        stream.set_nodelay(true)?;

        let mut writer = stream.try_clone()?;
        let mut framer = Framer::new(stream);
        let mut account: Option<Account> = None;

        loop {
            let frame = match framer.read_frame() {
                Ok(frame) => frame,
                Err(FrameError::UnexpectedEof) => return Ok(()),
                Err(err) => {
                    log(peer, format!("framer: {err}"));
                    return Ok(());
                }
            };

            let decoded = match codec::decode(&frame) {
                Ok(decoded) => decoded,
                Err(err) => {
                    log(peer, format!("codec: {err}"));
                    return Ok(());
                }
            };

            if !decoded.checksum_valid {
                log(peer, "checksum invalido; conexao fechada");
                return Ok(());
            }
            if decoded.header.id >= MAX_USER {
                log(peer, format!("ID invalido: {}", decoded.header.id));
                return Ok(());
            }
            if decoded.header.client_tick == SKIP_CHECK_TICK {
                log(peer, "ClientTick SKIPCHECKTICK descartado");
                continue;
            }

            match decoded.header.msg_type {
                MSG_ACCOUNT_LOGIN => {
                    if account.is_some() {
                        log(peer, "segundo login de conta ignorado");
                        continue;
                    }
                    match self.handle_login(&mut writer, &decoded.payload, peer)? {
                        LoginOutcome::Authenticated(found) => account = Some(*found),
                        LoginOutcome::Rejected => return Ok(()),
                    }
                }
                MSG_CHARACTER_LOGIN => {
                    let Some(found) = account.as_ref() else {
                        send_panel(&mut writer, "Faca login antes de escolher personagem.")?;
                        return Ok(());
                    };
                    self.handle_character_login(&mut writer, &decoded.payload, found, peer)?;
                    return Ok(());
                }
                MSG_PING => {}
                other => log(peer, format!("tipo nao tratado: {other:#06x}")),
            }
        }
    }

    fn handle_login(
        &self,
        writer: &mut TcpStream,
        payload: &[u8],
        peer: Option<SocketAddr>,
    ) -> io::Result<LoginOutcome> {
        let login = match AccountLogin::parse(payload) {
            Ok(login) => login,
            Err(err) => {
                log(peer, format!("login malformado: {err}"));
                send_panel(writer, "Pacote de login invalido.")?;
                return Ok(LoginOutcome::Rejected);
            }
        };

        if let Err(err) = login.validate() {
            log(peer, format!("login recusado: {err}"));
            let text = match err {
                crate::protocol::login::LoginError::BadVersion { got, layout } => format!(
                    "Versao do cliente nao confere ({got}); esperado {}.",
                    layout.expected_version_text()
                ),
                _ => "Login invalido.".to_owned(),
            };
            send_panel(writer, &text)?;
            return Ok(LoginOutcome::Rejected);
        }

        let account_key = format!("account:{}", login.name.to_lowercase());
        let peer_key = peer.map(|addr| format!("ip:{}", addr.ip()));
        let limit_keys: Vec<String> = peer_key
            .iter()
            .cloned()
            .chain(std::iter::once(account_key.clone()))
            .collect();
        let now = Instant::now();
        {
            let mut failures = self
                .login_failures
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            for key in &limit_keys {
                if let Some(retry) = failures.blocked_for(key, now) {
                    let seconds = retry.as_secs().max(1);
                    log(peer, format!("login limitado ({key}); aguarde {seconds}s"));
                    send_panel(writer, &format!("Muitas tentativas. Aguarde {seconds}s."))?;
                    return Ok(LoginOutcome::Rejected);
                }
            }
        }

        let account = match self.directory.find(&login.name) {
            Ok(Some(account)) => account,
            Ok(None) => {
                log(peer, "login recusado: conta inexistente");
                self.record_login_failure(&limit_keys);
                send_panel(writer, "Conta ou senha invalidos.")?;
                return Ok(LoginOutcome::Rejected);
            }
            Err(err) => {
                log(peer, format!("login recusado: {err}"));
                send_panel(writer, "Servico de contas indisponivel.")?;
                return Ok(LoginOutcome::Rejected);
            }
        };

        let password_matches = match &account.credential {
            Credential::DemoPlaintext(expected) => {
                Ok(constant_time_eq(expected, login.password.as_bytes()))
            }
            Credential::PasswordHash(hash) => hashing::verify_password(hash, &login.password),
        };
        match password_matches {
            Ok(true) => {}
            Ok(false) => {
                log(peer, "login recusado: senha incorreta");
                self.record_login_failure(&limit_keys);
                send_panel(writer, "Conta ou senha invalidos.")?;
                return Ok(LoginOutcome::Rejected);
            }
            Err(err) => {
                log(peer, format!("login recusado: {err}"));
                send_panel(writer, "Conta ou senha invalidos.")?;
                return Ok(LoginOutcome::Rejected);
            }
        }

        if account.blocked {
            log(peer, "login recusado: conta bloqueada");
            send_panel(writer, "Conta bloqueada. Procure o suporte.")?;
            return Ok(LoginOutcome::Rejected);
        }

        {
            let mut failures = self
                .login_failures
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            failures.clear(&account_key);
        }

        let body = encode_cnf_body(
            &account.login,
            &account.characters,
            account.cargo_coin,
            &account.cargo,
        );
        send_packet(writer, MSG_CNF_ACCOUNT_LOGIN, ID_SEL_CHAR, &body)?;
        log(
            peer,
            format!(
                "login ok: {} ({} personagens, layout {:?})",
                account.login,
                account.characters.len(),
                login.layout
            ),
        );
        Ok(LoginOutcome::Authenticated(Box::new(account)))
    }

    fn record_login_failure(&self, keys: &[String]) {
        let now = Instant::now();
        let mut failures = self
            .login_failures
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        for key in keys {
            failures.record(key, now);
        }
    }

    fn handle_character_login(
        &self,
        writer: &mut TcpStream,
        payload: &[u8],
        account: &Account,
        peer: Option<SocketAddr>,
    ) -> io::Result<()> {
        if payload.len() < 8 {
            log(peer, "MSG_CharacterLogin curto");
            send_panel(writer, "Personagem invalido.")?;
            send_character_login_fail(writer)?;
            return Ok(());
        }
        let slot = i32::from_le_bytes([payload[0], payload[1], payload[2], payload[3]]);
        let found = account
            .characters
            .iter()
            .find(|character| i32::from(character.slot) == slot);

        match found {
            Some(character) => {
                log(
                    peer,
                    format!("personagem selecionado: {} (slot {slot})", character.name),
                );
                send_panel(
                    writer,
                    &format!(
                        "{} selecionado. O mundo ainda nao foi implementado.",
                        character.name
                    ),
                )?;
            }
            None => {
                log(peer, format!("slot de personagem invalido: {slot}"));
                send_panel(writer, "Personagem invalido.")?;
            }
        }
        send_character_login_fail(writer)
    }
}

enum LoginOutcome {
    Authenticated(Box<Account>),
    Rejected,
}

fn send_panel(writer: &mut TcpStream, text: &str) -> io::Result<()> {
    let mut body = [0u8; MESSAGE_PANEL_LENGTH];
    write_c_string(&mut body, text);
    send_packet(writer, MSG_MESSAGE_PANEL, 0, &body)
}

fn send_character_login_fail(writer: &mut TcpStream) -> io::Result<()> {
    send_packet(writer, MSG_CHARACTER_LOGIN_FAIL, 0, &[])
}

fn send_packet(writer: &mut TcpStream, msg_type: u16, id: u16, payload: &[u8]) -> io::Result<()> {
    let frame = codec::encode(
        Header {
            msg_type,
            id,
            client_tick: now_tick(),
            ..Header::default()
        },
        payload,
        next_key_word(),
    )
    .map_err(|err| io::Error::new(io::ErrorKind::InvalidData, err))?;
    writer.write_all(&frame)?;
    writer.flush()
}

/// Compara sem saída antecipada. O tamanho das senhas legadas é curto; isto
/// não é uma primitiva criptográfica, apenas evita comparação byte-a-byte
/// trivial.
fn constant_time_eq(expected: &[u8], actual: &[u8]) -> bool {
    let max = expected.len().max(actual.len());
    let mut diff = u8::from(expected.len() != actual.len());
    for index in 0..max {
        let left = expected.get(index).copied().unwrap_or(0);
        let right = actual.get(index).copied().unwrap_or(0);
        diff |= left ^ right;
    }
    diff == 0
}

fn now_tick() -> u32 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs() as u32)
        .unwrap_or(0)
}

/// `KeyWord` é ofuscação, não segredo. Ainda assim, evita repetir a mesma
/// semente em todos os pacotes de uma sessão.
fn next_key_word() -> u8 {
    static SEQUENCE: AtomicU64 = AtomicU64::new(0);
    let sequence = SEQUENCE.fetch_add(1, Ordering::Relaxed);
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_nanos() as u64)
        .unwrap_or(0);
    let mixed = sequence.wrapping_mul(0x9E37_79B9_7F4A_7C15).rotate_left(17)
        ^ nanos
        ^ u64::from(std::process::id());
    (mixed >> 24) as u8
}

fn log(peer: Option<SocketAddr>, message: impl AsRef<str>) {
    match peer {
        Some(peer) => eprintln!("[gateway] {peer}: {}", message.as_ref()),
        None => eprintln!("[gateway] {}", message.as_ref()),
    }
}

#[cfg(test)]
mod tests {
    use super::constant_time_eq;

    #[test]
    fn comparacao_de_senha_so_aceita_igual() {
        assert!(constant_time_eq(b"Secret123!", b"Secret123!"));
        assert!(!constant_time_eq(b"Secret123!", b"Secret123?"));
        assert!(!constant_time_eq(b"Secret123!", b"Secret123"));
        assert!(!constant_time_eq(b"", b"x"));
    }
}
