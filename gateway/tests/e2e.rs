use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use wyd_gateway::protocol::codec::{self, Header};
use wyd_gateway::protocol::login::{
    AccountLogin, LoginLayout, ACCOUNT_LOGIN_BODY_SIZE, GLOBAL_BODY_SIZE,
};
use wyd_gateway::protocol::text::c_string;
use wyd_gateway::protocol::{
    APP_VERSION, CLIENT_VERSION_GLOBAL, INIT_CODE, MSG_ACCOUNT_LOGIN, MSG_CHARACTER_LOGIN,
    MSG_CHARACTER_LOGIN_FAIL, MSG_CNF_ACCOUNT_LOGIN, MSG_MESSAGE_PANEL,
};
use wyd_gateway::{DemoDirectory, Gateway};

/// Handshake congelado do cliente WYD Global (INITCODE + frame de 124 B).
///
/// Sintetico: credenciais de teste, token de 22 B zerado. Ver o cabecalho do
/// proprio arquivo e `docs/08-CLIENTE-ALVO.md` §6.1.
const GOLDEN_GLOBAL: &str = include_str!("fixtures/account_login_global.hex");

fn start_gateway() -> SocketAddr {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let directory = DemoDirectory::with_demo_account("TestAccount", "Secret123!");
    let gateway = Arc::new(Gateway::new(Arc::new(directory)).with_timeout(Duration::from_secs(5)));
    thread::spawn(move || gateway.serve(listener));
    address
}

fn connect(address: SocketAddr) -> TcpStream {
    let stream = TcpStream::connect(address).unwrap();
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .unwrap();
    stream
        .set_write_timeout(Some(Duration::from_secs(5)))
        .unwrap();
    stream
}

fn login_body_with_size(name: &str, password: &str, version: i32, size: usize) -> Vec<u8> {
    let mut body = vec![0u8; size];
    body[..password.len()].copy_from_slice(password.as_bytes());
    body[12..12 + name.len()].copy_from_slice(name.as_bytes());
    body[80..84].copy_from_slice(&version.to_le_bytes());
    body
}

fn send_login(stream: &mut TcpStream, name: &str, password: &str, version: i32) {
    send_login_with_size(stream, name, password, version, ACCOUNT_LOGIN_BODY_SIZE);
}

fn send_login_with_size(
    stream: &mut TcpStream,
    name: &str,
    password: &str,
    version: i32,
    size: usize,
) {
    let body = login_body_with_size(name, password, version, size);
    let frame = codec::encode(
        Header {
            msg_type: MSG_ACCOUNT_LOGIN,
            id: 1,
            ..Header::default()
        },
        &body,
        42,
    )
    .unwrap();
    stream.write_all(&INIT_CODE.to_le_bytes()).unwrap();
    stream.write_all(&frame).unwrap();
    stream.flush().unwrap();
}

fn send_character_login(stream: &mut TcpStream, slot: i32) {
    let mut body = vec![0u8; 8];
    body[..4].copy_from_slice(&slot.to_le_bytes());
    let frame = codec::encode(
        Header {
            msg_type: MSG_CHARACTER_LOGIN,
            id: 1,
            ..Header::default()
        },
        &body,
        77,
    )
    .unwrap();
    stream.write_all(&frame).unwrap();
    stream.flush().unwrap();
}

fn read_packet(stream: &mut TcpStream) -> Vec<u8> {
    let mut header = [0u8; 12];
    stream.read_exact(&mut header).unwrap();
    let size = usize::from(u16::from_le_bytes([header[0], header[1]]));
    let mut wire = vec![0u8; size];
    wire[..12].copy_from_slice(&header);
    stream.read_exact(&mut wire[12..]).unwrap();
    wire
}

fn text_of(payload: &[u8]) -> String {
    c_string(payload)
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

#[test]
fn login_valido_recebe_cnf_e_selecao_termina_com_falha_controlada() {
    let mut stream = connect(start_gateway());
    send_login(&mut stream, "TestAccount", "Secret123!", APP_VERSION);

    let cnf = read_packet(&mut stream);
    assert_eq!(cnf.len(), 2008);
    let decoded = codec::decode(&cnf).unwrap();
    assert!(decoded.checksum_valid);
    assert_eq!(decoded.header.msg_type, MSG_CNF_ACCOUNT_LOGIN);
    assert_eq!(decoded.header.id, 30002);
    assert_eq!(decoded.payload.len(), 1996);
    assert_eq!(
        i32::from_le_bytes(decoded.payload[16..20].try_into().unwrap()),
        1
    );
    assert_eq!(&decoded.payload[36..40], b"Hero");
    assert_eq!(&decoded.payload[1888..1899], b"TestAccount");

    send_character_login(&mut stream, 0);
    let panel = read_packet(&mut stream);
    let panel = codec::decode(&panel).unwrap();
    assert_eq!(panel.header.msg_type, MSG_MESSAGE_PANEL);
    assert_eq!(panel.payload.len(), 128);
    assert!(text_of(&panel.payload).contains("Hero"));

    let fail = read_packet(&mut stream);
    let fail = codec::decode(&fail).unwrap();
    assert_eq!(fail.header.msg_type, MSG_CHARACTER_LOGIN_FAIL);
    assert!(fail.payload.is_empty());
}

#[test]
fn login_do_wyd_global_com_112_bytes_recebe_cnf() {
    let mut stream = connect(start_gateway());
    send_login_with_size(
        &mut stream,
        "TestAccount",
        "Secret123!",
        CLIENT_VERSION_GLOBAL,
        GLOBAL_BODY_SIZE,
    );

    let cnf = read_packet(&mut stream);
    assert_eq!(cnf.len(), 2008);
    let decoded = codec::decode(&cnf).unwrap();
    assert!(decoded.checksum_valid);
    assert_eq!(decoded.header.msg_type, MSG_CNF_ACCOUNT_LOGIN);
    assert_eq!(decoded.header.id, 30002);
    assert_eq!(decoded.payload.len(), 1996);
}

#[test]
fn corpo_global_com_versao_do_7662_recebe_a_versao_esperada() {
    let mut stream = connect(start_gateway());
    send_login_with_size(
        &mut stream,
        "TestAccount",
        "Secret123!",
        APP_VERSION,
        GLOBAL_BODY_SIZE,
    );

    let panel = read_packet(&mut stream);
    let panel = codec::decode(&panel).unwrap();
    assert_eq!(panel.header.msg_type, MSG_MESSAGE_PANEL);
    assert!(text_of(&panel.payload).contains("0x0C9DB301"));
}

#[test]
fn senha_incorreta_recebe_painel_e_conexao_fecha() {
    let mut stream = connect(start_gateway());
    send_login(&mut stream, "TestAccount", "senha-errada", APP_VERSION);

    let panel = read_packet(&mut stream);
    let panel = codec::decode(&panel).unwrap();
    assert_eq!(panel.header.msg_type, MSG_MESSAGE_PANEL);
    assert!(text_of(&panel.payload).contains("invalidos"));

    let mut byte = [0u8; 1];
    assert_eq!(stream.read(&mut byte).unwrap(), 0);
}

#[test]
fn versao_incorreta_recebe_mensagem_com_a_versao_esperada() {
    let mut stream = connect(start_gateway());
    send_login(&mut stream, "TestAccount", "Secret123!", 1);

    let panel = read_packet(&mut stream);
    let panel = codec::decode(&panel).unwrap();
    assert_eq!(panel.header.msg_type, MSG_MESSAGE_PANEL);
    assert!(text_of(&panel.payload).contains("7640"));
}

#[test]
fn handshake_global_congelado_recebe_cnf() {
    let raw = golden_handshake();
    assert_eq!(raw.len(), 128);
    assert_eq!(u32::from_le_bytes(raw[..4].try_into().unwrap()), INIT_CODE);

    let decoded = codec::decode(&raw[4..]).unwrap();
    assert!(decoded.checksum_valid);
    assert_eq!(decoded.header.size, 124);
    assert_eq!(decoded.header.key_word, 0xEB);
    assert_eq!(decoded.header.msg_type, MSG_ACCOUNT_LOGIN);
    assert_eq!(decoded.payload.len(), 112);
    assert!(
        decoded.payload[0x58..0x6E].iter().all(|byte| *byte == 0),
        "o vetor nao deve carregar o token de 22 B da maquina"
    );

    let login = AccountLogin::parse(&decoded.payload).unwrap();
    assert_eq!(login.layout, LoginLayout::Global);
    assert_eq!(login.name, "TestAccount");
    assert_eq!(login.password, "Secret123!");
    assert_eq!(login.client_version, CLIENT_VERSION_GLOBAL);
    login.validate().unwrap();

    let mut stream = connect(start_gateway());
    stream.write_all(&raw).unwrap();
    stream.flush().unwrap();

    let cnf = read_packet(&mut stream);
    assert_eq!(cnf.len(), 2008);
    let cnf = codec::decode(&cnf).unwrap();
    assert!(cnf.checksum_valid);
    assert_eq!(cnf.header.msg_type, MSG_CNF_ACCOUNT_LOGIN);
    assert_eq!(&cnf.payload[36..40], b"Hero");
    assert_eq!(&cnf.payload[1888..1899], b"TestAccount");
}

#[test]
fn codec_reproduz_o_handshake_congelado_byte_a_byte() {
    let raw = golden_handshake();
    let decoded = codec::decode(&raw[4..]).unwrap();
    let again = codec::encode(decoded.header, &decoded.payload, decoded.header.key_word).unwrap();
    assert_eq!(again, raw[4..].to_vec());
}

#[test]
fn initcode_invalido_fecha_sem_resposta() {
    let mut stream = connect(start_gateway());
    stream.write_all(&[0xAA; 4]).unwrap();
    let mut byte = [0u8; 1];
    assert_eq!(stream.read(&mut byte).unwrap(), 0);
}
