//! Rate limit de falhas de login (R06).
//!
//! A janela deslizante conta falhas por IP e por conta; um login valido nao
//! consome a janela e um gateway novo comeca zerado. Estes testes usam um
//! limite baixo para nao depender de espera real.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use wyd_gateway::protocol::codec::{self, Header};
use wyd_gateway::protocol::login::ACCOUNT_LOGIN_BODY_SIZE;
use wyd_gateway::protocol::text::c_string;
use wyd_gateway::protocol::{
    APP_VERSION, INIT_CODE, MSG_ACCOUNT_LOGIN, MSG_CNF_ACCOUNT_LOGIN, MSG_MESSAGE_PANEL,
};
use wyd_gateway::{DemoDirectory, Gateway};

const LIMIT: u32 = 2;

fn start_gateway() -> SocketAddr {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind efemero");
    let address = listener.local_addr().expect("endereco local");
    let directory = DemoDirectory::with_demo_account("TestAccount", "Secret123!");
    let gateway = Arc::new(
        Gateway::new(Arc::new(directory))
            .with_timeout(Duration::from_secs(5))
            .with_login_limit(LIMIT, Duration::from_secs(60)),
    );
    thread::spawn(move || gateway.serve(listener));
    address
}

fn connect(address: SocketAddr) -> TcpStream {
    let stream = TcpStream::connect(address).expect("connect");
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .expect("read timeout");
    stream
}

fn send_login(stream: &mut TcpStream, password: &str) {
    let mut body = vec![0u8; ACCOUNT_LOGIN_BODY_SIZE];
    body[..password.len()].copy_from_slice(password.as_bytes());
    body[12..23].copy_from_slice(b"TestAccount");
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

fn panel_text(stream: &mut TcpStream) -> String {
    let packet = read_packet(stream);
    let decoded = codec::decode(&packet).expect("decode painel");
    assert_eq!(decoded.header.msg_type, MSG_MESSAGE_PANEL);
    c_string(&decoded.payload)
}

#[test]
fn falhas_repetidas_bloqueiam_mesmo_com_senha_certa() {
    let address = start_gateway();
    for _ in 0..LIMIT {
        let mut stream = connect(address);
        send_login(&mut stream, "senha-errada");
        assert!(panel_text(&mut stream).contains("invalidos"));
    }

    let mut stream = connect(address);
    send_login(&mut stream, "Secret123!");
    let text = panel_text(&mut stream);
    assert!(text.contains("Muitas tentativas"), "painel: {text}");
}

#[test]
fn login_valido_nao_consome_a_janela() {
    let address = start_gateway();
    for _ in 0..LIMIT {
        let mut stream = connect(address);
        send_login(&mut stream, "Secret123!");
        let packet = read_packet(&mut stream);
        let decoded = codec::decode(&packet).expect("decode cnf");
        assert_eq!(decoded.header.msg_type, MSG_CNF_ACCOUNT_LOGIN);
    }

    let mut stream = connect(address);
    send_login(&mut stream, "senha-errada");
    assert!(panel_text(&mut stream).contains("invalidos"));

    let mut stream = connect(address);
    send_login(&mut stream, "Secret123!");
    let packet = read_packet(&mut stream);
    let decoded = codec::decode(&packet).expect("decode cnf");
    assert_eq!(decoded.header.msg_type, MSG_CNF_ACCOUNT_LOGIN);
}

#[test]
fn bloqueio_vive_no_processo_e_nao_vaza_para_outra_instancia() {
    let first = start_gateway();
    for _ in 0..LIMIT {
        let mut stream = connect(first);
        send_login(&mut stream, "senha-errada");
        assert!(panel_text(&mut stream).contains("invalidos"));
    }

    let second = start_gateway();
    let mut stream = connect(second);
    send_login(&mut stream, "Secret123!");
    let packet = read_packet(&mut stream);
    let decoded = codec::decode(&packet).expect("decode cnf");
    assert_eq!(decoded.header.msg_type, MSG_CNF_ACCOUNT_LOGIN);
}
