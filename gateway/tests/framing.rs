//! Matriz hostil de framing contra um gateway TCP real.
//!
//! Cada caso abre conexao, envia bytes malformados e exige que o gateway
//! feche sem responder e sem panic. Depois de todos, um login valido prova
//! que o listener e o estado por conexao nao ficaram quebrados.
//!
//! Frames parciais e colados (reader entregando um byte por vez e dois frames
//! na mesma leitura) sao cobertos em `src/protocol/framing.rs`.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use wyd_gateway::protocol::codec::{self, Header};
use wyd_gateway::protocol::login::GLOBAL_BODY_SIZE;
use wyd_gateway::protocol::selchar::CNF_FRAME_SIZE;
use wyd_gateway::protocol::{
    CLIENT_VERSION_GLOBAL, INIT_CODE, MAX_USER, MSG_ACCOUNT_LOGIN, MSG_CNF_ACCOUNT_LOGIN,
};
use wyd_gateway::{DemoDirectory, Gateway};

const READ_TIMEOUT: Duration = Duration::from_secs(5);

fn start_gateway(session_timeout: Duration) -> SocketAddr {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind efemero");
    let address = listener.local_addr().expect("endereco local");
    let directory = DemoDirectory::with_demo_account("TestAccount", "Secret123!");
    let gateway = Arc::new(Gateway::new(Arc::new(directory)).with_timeout(session_timeout));
    thread::spawn(move || gateway.serve(listener));
    address
}

fn connect(address: SocketAddr) -> TcpStream {
    let stream = TcpStream::connect(address).expect("connect");
    stream
        .set_read_timeout(Some(READ_TIMEOUT))
        .expect("read timeout");
    stream
}

fn login_frame() -> Vec<u8> {
    let mut body = vec![0u8; GLOBAL_BODY_SIZE];
    body[..10].copy_from_slice(b"Secret123!");
    body[12..23].copy_from_slice(b"TestAccount");
    body[80..84].copy_from_slice(&CLIENT_VERSION_GLOBAL.to_le_bytes());
    body[84..88].copy_from_slice(&1i32.to_le_bytes());
    codec::encode(
        Header {
            msg_type: MSG_ACCOUNT_LOGIN,
            id: 1,
            ..Header::default()
        },
        &body,
        0x42,
    )
    .expect("encode login")
}

fn header_with_size(size: u16) -> Vec<u8> {
    let mut header = vec![0u8; 12];
    header[..2].copy_from_slice(&size.to_le_bytes());
    header
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

fn expect_close(stream: &mut TcpStream, case: &str) {
    let mut byte = [0u8; 1];
    match stream.read(&mut byte) {
        Ok(0) => {}
        Ok(read) => panic!("{case}: gateway respondeu {read} byte(s)"),
        Err(err) => panic!("{case}: conexao nao fechou: {err}"),
    }
}

#[test]
fn framing_hostil_fecha_sem_resposta_e_gateway_continua() {
    let address = start_gateway(Duration::from_millis(300));
    let init = INIT_CODE.to_le_bytes().to_vec();

    let checksum_adulterado = {
        let mut frame = login_frame();
        // O CheckSum do header cobre a soma cifrada menos a plana; mexer so
        // no corpo nao o invalida (diferenca constante da keytable). Adulterar
        // o proprio byte do CheckSum e o caso que o gateway precisa recusar.
        frame[3] ^= 0xFF;
        let mut handshake = init.clone();
        handshake.extend_from_slice(&frame);
        handshake
    };
    let id_invalido = {
        let frame = codec::encode(
            Header {
                msg_type: MSG_ACCOUNT_LOGIN,
                id: MAX_USER,
                ..Header::default()
            },
            &[0u8; GLOBAL_BODY_SIZE],
            9,
        )
        .expect("encode id invalido");
        let mut handshake = init.clone();
        handshake.extend_from_slice(&frame);
        handshake
    };

    let cases: Vec<(&str, Vec<u8>)> = vec![
        ("size zero", [init.clone(), header_with_size(0)].concat()),
        (
            "size menor que o header",
            [init.clone(), header_with_size(11)].concat(),
        ),
        (
            "size no limite do u16",
            [init.clone(), header_with_size(u16::MAX)].concat(),
        ),
        ("header truncado", [init.clone(), vec![0x7C]].concat()),
        (
            "size valido sem corpo",
            [init.clone(), header_with_size(124)].concat(),
        ),
        ("checksum adulterado", checksum_adulterado),
        ("id fora de MAX_USER", id_invalido),
    ];

    for (case, bytes) in &cases {
        let mut stream = connect(address);
        stream.write_all(bytes).expect("write hostil");
        stream.flush().expect("flush hostil");
        expect_close(&mut stream, case);
    }

    // Limpeza: depois de todas as sessoes hostis, um login normal recebe CNF.
    let mut stream = connect(address);
    stream.write_all(&init).expect("write initcode");
    stream.write_all(&login_frame()).expect("write login");
    stream.flush().expect("flush login");

    let cnf = read_packet(&mut stream);
    assert_eq!(cnf.len(), CNF_FRAME_SIZE);
    let decoded = codec::decode(&cnf).expect("decode cnf");
    assert!(decoded.checksum_valid);
    assert_eq!(decoded.header.msg_type, MSG_CNF_ACCOUNT_LOGIN);
}
