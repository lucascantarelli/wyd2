//! Teste de integração opcional contra PostgreSQL 16.
//!
//! Rode com `gateway/scripts/test-postgres.sh` (sobe o container, aplica o
//! schema e o fixture e executa este binário). Sem `WYD_TEST_DATABASE_URL`,
//! o teste é pulado para não quebrar `cargo test` em máquina sem Docker.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use wyd_gateway::hashing::verify_password;
use wyd_gateway::protocol::codec::{self, Header};
use wyd_gateway::protocol::login::ACCOUNT_LOGIN_BODY_SIZE;
use wyd_gateway::protocol::selchar::{
    CNF_ACCOUNT_NAME_OFFSET, CNF_COIN_OFFSET, CNF_FRAME_SIZE, CNF_SELCHAR_OFFSET,
};
use wyd_gateway::protocol::text::c_string;
use wyd_gateway::protocol::{
    APP_VERSION, INIT_CODE, MSG_ACCOUNT_LOGIN, MSG_CNF_ACCOUNT_LOGIN, MSG_MESSAGE_PANEL,
};
use wyd_gateway::{Credential, Directory, Gateway, PostgresDirectory};

/// Handshake congelado do cliente WYD Global (INITCODE + login de 112 B).
/// O fixture `postgres.sql` tem `TestAccount`/`Secret123!`, as mesmas
/// credenciais sinteticas do vetor.
const GOLDEN_GLOBAL: &str = include_str!("fixtures/account_login_global.hex");

fn database_url() -> Option<String> {
    match std::env::var("WYD_TEST_DATABASE_URL") {
        Ok(url) if !url.trim().is_empty() => Some(url),
        _ => None,
    }
}

#[test]
fn carrega_conta_personagens_equipamento_e_cargo() {
    let Some(url) = database_url() else {
        eprintln!("pulado: defina WYD_TEST_DATABASE_URL ou rode gateway/scripts/test-postgres.sh");
        return;
    };

    let directory = PostgresDirectory::connect(&url).expect("conectar no PostgreSQL de teste");
    let account = directory
        .find("testaccount")
        .expect("consulta de conta")
        .expect("conta TestAccount existe");

    assert_eq!(account.login, "TestAccount");
    assert!(!account.blocked);
    assert_eq!(account.cargo_coin, 777);
    assert_eq!(account.characters.len(), 2);

    let hero = &account.characters[0];
    assert_eq!(hero.slot, 0);
    assert_eq!(hero.name, "Hero");
    assert_eq!(hero.level, 50);
    assert_eq!(hero.exp, 250_000);
    assert_eq!(hero.coin, 1_500);
    assert_eq!(hero.spx, 100);
    assert_eq!(hero.spy, 200);
    assert_eq!(hero.merchant, 0);
    assert_eq!(hero.attack_run, 1);
    assert_eq!(hero.direction, 2);
    assert_eq!(hero.chaos_rate, 0);
    assert_eq!(hero.ac, 12);
    assert_eq!(hero.damage, 25);
    assert_eq!(hero.strength, 31);
    assert_eq!(hero.intelligence, 11);
    assert_eq!(hero.dexterity, 21);
    assert_eq!(hero.constitution, 26);
    assert_eq!(hero.special, [1, 2, 3, 4]);
    assert_eq!(hero.guild, 7);
    assert_eq!(hero.equip[0].index, 100);
    assert_eq!(hero.equip[0].effects, [(43, 230), (1, 5), (0, 0)]);
    assert_eq!(hero.equip[1].index, 101);
    assert_eq!(hero.equip[1].effects, [(2, 7), (0, 0), (0, 0)]);
    assert_eq!(hero.equip[2].index, 0);

    let mage = &account.characters[1];
    assert_eq!(mage.slot, 1);
    assert_eq!(mage.name, "Mage");
    assert_eq!(mage.level, 10);
    assert_eq!(mage.coin, 500);
    assert_eq!(mage.exp, 1_000);
    assert_eq!(mage.equip[0].index, 0);

    assert_eq!(account.cargo[3].index, 200);
    assert_eq!(account.cargo[3].effects, [(9, 4), (0, 0), (0, 0)]);
    assert_eq!(account.cargo[0].index, 0);

    match &account.credential {
        Credential::PasswordHash(hash) => {
            assert!(verify_password(hash, "Secret123!").expect("hash valido"));
            assert!(!verify_password(hash, "senha-errada").expect("hash valido"));
        }
        Credential::DemoPlaintext(_) => panic!("conta do banco nao pode ser demo"),
    }
}

#[test]
fn recusa_item_fora_do_catalogo() {
    let Some(url) = database_url() else {
        eprintln!("pulado: defina WYD_TEST_DATABASE_URL ou rode gateway/scripts/test-postgres.sh");
        return;
    };

    let directory = PostgresDirectory::connect(&url).expect("conectar no PostgreSQL de teste");
    let error = directory
        .find("BrokenCatalogAccount")
        .expect_err("item fora de catalog.items deve falhar a sessao");
    let message = error.to_string();

    assert!(message.contains("9999"), "mensagem: {message}");
    assert!(message.contains("equip"), "mensagem: {message}");
    assert!(message.contains("catalog.items"), "mensagem: {message}");
}

fn golden_handshake() -> Vec<u8> {
    let hex: String = GOLDEN_GLOBAL
        .lines()
        .filter(|line| !line.trim_start().starts_with('#'))
        .flat_map(|line| line.split_whitespace())
        .collect();
    assert_eq!(hex.len() % 2, 0, "hex do golden vector com tamanho impar");
    (0..hex.len())
        .step_by(2)
        .map(|index| u8::from_str_radix(&hex[index..index + 2], 16).expect("hex invalido"))
        .collect()
}

fn start_gateway(directory: PostgresDirectory) -> SocketAddr {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind efemero");
    let address = listener.local_addr().expect("endereco local");
    let gateway = Arc::new(Gateway::new(Arc::new(directory)).with_timeout(Duration::from_secs(5)));
    thread::spawn(move || gateway.serve(listener));
    address
}

fn send_login(stream: &mut TcpStream, name: &str, password: &str) {
    let mut body = vec![0u8; ACCOUNT_LOGIN_BODY_SIZE];
    body[..password.len()].copy_from_slice(password.as_bytes());
    body[12..12 + name.len()].copy_from_slice(name.as_bytes());
    body[80..84].copy_from_slice(&APP_VERSION.to_le_bytes());
    let frame = codec::encode(
        Header {
            msg_type: MSG_ACCOUNT_LOGIN,
            id: 1,
            ..Header::default()
        },
        &body,
        42,
    )
    .expect("encode login");

    stream
        .write_all(&INIT_CODE.to_le_bytes())
        .expect("write initcode");
    stream.write_all(&frame).expect("write login");
    stream.flush().expect("flush login");
}

fn read_packet(stream: &mut TcpStream) -> Vec<u8> {
    let mut header = [0u8; 12];
    stream.read_exact(&mut header).expect("read header");
    let size = usize::from(u16::from_le_bytes([header[0], header[1]]));
    let mut wire = vec![0u8; size];
    wire[..12].copy_from_slice(&header);
    stream.read_exact(&mut wire[12..]).expect("read body");
    wire
}

fn connect(address: SocketAddr) -> TcpStream {
    let stream = TcpStream::connect(address).expect("connect");
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .expect("read timeout");
    stream
}

#[test]
fn gateway_autentica_conta_do_postgres() {
    let Some(url) = database_url() else {
        eprintln!("pulado: defina WYD_TEST_DATABASE_URL ou rode gateway/scripts/test-postgres.sh");
        return;
    };

    let directory = PostgresDirectory::connect(&url).expect("conectar no PostgreSQL de teste");
    let mut stream = connect(start_gateway(directory));
    send_login(&mut stream, "TestAccount", "Secret123!");

    let cnf = read_packet(&mut stream);
    assert_eq!(cnf.len(), CNF_FRAME_SIZE);
    let decoded = codec::decode(&cnf).expect("decode cnf");
    assert!(decoded.checksum_valid);
    assert_eq!(decoded.header.msg_type, MSG_CNF_ACCOUNT_LOGIN);
    assert_eq!(
        i32::from_le_bytes(
            decoded.payload[CNF_COIN_OFFSET..CNF_COIN_OFFSET + 4]
                .try_into()
                .expect("coin")
        ),
        777
    );
    assert_eq!(
        c_string(&decoded.payload[CNF_ACCOUNT_NAME_OFFSET..CNF_ACCOUNT_NAME_OFFSET + 16]),
        "TestAccount"
    );
}

#[test]
fn handshake_global_congelado_autentica_no_postgres() {
    let Some(url) = database_url() else {
        eprintln!("pulado: defina WYD_TEST_DATABASE_URL ou rode gateway/scripts/test-postgres.sh");
        return;
    };

    let directory = PostgresDirectory::connect(&url).expect("conectar no PostgreSQL de teste");
    let mut stream = connect(start_gateway(directory));
    let handshake = golden_handshake();
    assert_eq!(handshake.len(), 128);
    stream.write_all(&handshake).expect("write handshake");
    stream.flush().expect("flush handshake");

    let cnf = read_packet(&mut stream);
    assert_eq!(cnf.len(), CNF_FRAME_SIZE);
    let decoded = codec::decode(&cnf).expect("decode cnf");
    assert!(decoded.checksum_valid);
    assert_eq!(decoded.header.msg_type, MSG_CNF_ACCOUNT_LOGIN);
    assert_eq!(
        c_string(&decoded.payload[CNF_SELCHAR_OFFSET + 16..CNF_SELCHAR_OFFSET + 32]),
        "Hero"
    );
    assert_eq!(
        c_string(&decoded.payload[CNF_SELCHAR_OFFSET + 32..CNF_SELCHAR_OFFSET + 48]),
        "Mage"
    );
    assert_eq!(
        i32::from_le_bytes(
            decoded.payload[CNF_COIN_OFFSET..CNF_COIN_OFFSET + 4]
                .try_into()
                .expect("coin")
        ),
        777
    );
    assert_eq!(
        c_string(&decoded.payload[CNF_ACCOUNT_NAME_OFFSET..CNF_ACCOUNT_NAME_OFFSET + 16]),
        "TestAccount"
    );
}

#[test]
fn gateway_recusa_conta_bloqueada_do_postgres() {
    let Some(url) = database_url() else {
        eprintln!("pulado: defina WYD_TEST_DATABASE_URL ou rode gateway/scripts/test-postgres.sh");
        return;
    };

    let directory = PostgresDirectory::connect(&url).expect("conectar no PostgreSQL de teste");
    let mut stream = connect(start_gateway(directory));
    send_login(&mut stream, "BlockedAccount", "Secret123!");

    let panel = read_packet(&mut stream);
    let panel = codec::decode(&panel).expect("decode painel");
    assert_eq!(panel.header.msg_type, MSG_MESSAGE_PANEL);
    assert!(c_string(&panel.payload).contains("bloqueada"));

    let mut byte = [0u8; 1];
    assert_eq!(stream.read(&mut byte).expect("read eof"), 0);
}

#[test]
fn conta_bloqueada_e_login_inexistente() {
    let Some(url) = database_url() else {
        eprintln!("pulado: defina WYD_TEST_DATABASE_URL ou rode gateway/scripts/test-postgres.sh");
        return;
    };

    let directory = PostgresDirectory::connect(&url).expect("conectar no PostgreSQL de teste");

    let blocked = directory
        .find("blockedaccount")
        .expect("consulta de conta")
        .expect("conta BlockedAccount existe");
    assert!(blocked.blocked);
    assert!(blocked.characters.is_empty());

    assert!(directory
        .find("nao-existe")
        .expect("consulta de conta")
        .is_none());
}
