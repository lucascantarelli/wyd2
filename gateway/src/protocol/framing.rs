//! Framer do CPSock: INITCODE de 4 bytes e frames delimitados por `Size`.
//!
//! O reader pode entregar bytes parciais ou vários frames colados; o buffer
//! interno drena um frame por chamada.

use std::fmt;
use std::io::{self, Read};

use super::{HEADER_SIZE, INIT_CODE, MAX_MESSAGE_SIZE};

#[derive(Debug)]
pub enum FrameError {
    Io(io::Error),
    BadInitCode,
    BadSize(u16),
    UnexpectedEof,
}

impl fmt::Display for FrameError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(err) => write!(f, "erro de I/O: {err}"),
            Self::BadInitCode => write!(f, "INITCODE invalido"),
            Self::BadSize(size) => write!(
                f,
                "Size invalido: {size} (esperado {HEADER_SIZE}..={MAX_MESSAGE_SIZE})"
            ),
            Self::UnexpectedEof => write!(f, "stream terminou no meio de um frame"),
        }
    }
}

impl std::error::Error for FrameError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io(err) => Some(err),
            _ => None,
        }
    }
}

impl From<io::Error> for FrameError {
    fn from(err: io::Error) -> Self {
        if err.kind() == io::ErrorKind::UnexpectedEof {
            Self::UnexpectedEof
        } else {
            Self::Io(err)
        }
    }
}

/// Lê INITCODE e frames inteiros de um stream.
pub struct Framer<R: Read> {
    reader: R,
    buffer: Vec<u8>,
    init_consumed: bool,
}

impl<R: Read> Framer<R> {
    pub fn new(reader: R) -> Self {
        Self {
            reader,
            buffer: Vec::with_capacity(MAX_MESSAGE_SIZE),
            init_consumed: false,
        }
    }

    /// Consome o INITCODE (uma vez) e devolve o próximo frame completo.
    pub fn read_frame(&mut self) -> Result<Vec<u8>, FrameError> {
        if !self.init_consumed {
            let mut init = [0u8; 4];
            self.reader.read_exact(&mut init)?;
            if u32::from_le_bytes(init) != INIT_CODE {
                return Err(FrameError::BadInitCode);
            }
            self.init_consumed = true;
        }

        self.fill_to(HEADER_SIZE)?;
        let size = u16::from_le_bytes([self.buffer[0], self.buffer[1]]);
        if !(HEADER_SIZE as u16..=MAX_MESSAGE_SIZE as u16).contains(&size) {
            return Err(FrameError::BadSize(size));
        }

        self.fill_to(usize::from(size))?;
        Ok(self.buffer.drain(..usize::from(size)).collect())
    }

    fn fill_to(&mut self, wanted: usize) -> Result<(), FrameError> {
        let mut chunk = [0u8; 4096];
        while self.buffer.len() < wanted {
            let read = self.reader.read(&mut chunk)?;
            if read == 0 {
                return Err(FrameError::UnexpectedEof);
            }
            self.buffer.extend_from_slice(&chunk[..read]);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::codec;

    struct DripReader {
        data: Vec<u8>,
    }

    impl Read for DripReader {
        fn read(&mut self, out: &mut [u8]) -> io::Result<usize> {
            if self.data.is_empty() {
                return Ok(0);
            }
            out[0] = self.data.remove(0);
            Ok(1)
        }
    }

    fn with_init(frames: &[&[u8]]) -> Vec<u8> {
        let mut stream = INIT_CODE.to_le_bytes().to_vec();
        for frame in frames {
            stream.extend_from_slice(frame);
        }
        stream
    }

    fn encoded(payload: &[u8], keyword: u8) -> Vec<u8> {
        codec::encode(
            codec::Header {
                msg_type: 0x036C,
                id: 1,
                ..codec::Header::default()
            },
            payload,
            keyword,
        )
        .unwrap()
    }

    #[test]
    fn exige_initcode() {
        let mut framer = Framer::new(&b"nope"[..]);
        assert!(matches!(framer.read_frame(), Err(FrameError::BadInitCode)));
    }

    #[test]
    fn le_frame_unico() {
        let frame = encoded(&[1, 2, 3, 4], 7);
        let stream = with_init(&[&frame]);
        let mut framer = Framer::new(&stream[..]);
        assert_eq!(framer.read_frame().unwrap(), frame);
    }

    #[test]
    fn le_frames_parciais_e_colados() {
        let first = encoded(&[1, 2, 3], 7);
        let second = encoded(&[9; 30], 200);
        let stream = with_init(&[&first, &second]);
        let mut framer = Framer::new(DripReader { data: stream });
        assert_eq!(framer.read_frame().unwrap(), first);
        assert_eq!(framer.read_frame().unwrap(), second);
        assert!(matches!(
            framer.read_frame(),
            Err(FrameError::UnexpectedEof)
        ));
    }

    #[test]
    fn rejeita_size_fora_da_faixa() {
        for size in [
            0u16,
            (HEADER_SIZE as u16) - 1,
            (MAX_MESSAGE_SIZE as u16) + 1,
        ] {
            let mut header = [0u8; HEADER_SIZE];
            header[0..2].copy_from_slice(&size.to_le_bytes());
            let stream = with_init(&[&header]);
            let mut framer = Framer::new(&stream[..]);
            assert!(matches!(framer.read_frame(), Err(FrameError::BadSize(_))));
        }
    }

    #[test]
    fn fuzz_deterministico_de_bytes_nao_panica() {
        // xorshift64* com semente fixa: o teste e reproduzivel e nao depende
        // de crate de fuzz. O stream sempre comeca com INITCODE valido; o
        // resto e lixo que pode virar Size, header ou corpo pela metade.
        let mut state = 0x9E37_79B9_7F4A_7C15u64;
        let mut next = || {
            state ^= state >> 12;
            state ^= state << 25;
            state ^= state >> 27;
            state.wrapping_mul(0x2545_F491_4F6C_DD1D)
        };

        for _ in 0..500 {
            let len = (next() % 600) as usize;
            let mut stream = INIT_CODE.to_le_bytes().to_vec();
            for _ in 0..len {
                stream.push(next() as u8);
            }
            let mut framer = Framer::new(&stream[..]);
            for _ in 0..64 {
                if framer.read_frame().is_err() {
                    break;
                }
            }
        }
    }

    #[test]
    fn detecta_frame_truncado() {
        let frame = encoded(&[5; 20], 1);
        let mut stream = with_init(&[&frame]);
        stream.pop();
        let mut framer = Framer::new(&stream[..]);
        assert!(matches!(
            framer.read_frame(),
            Err(FrameError::UnexpectedEof)
        ));
    }
}
