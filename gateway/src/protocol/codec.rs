//! Header de 12 bytes, ofuscação `pKeyWord` e checksum.
//!
//! A transformação cobre `[4, Size)`: `Size`, `KeyWord` e `CheckSum` viajam
//! em claro. O checksum é `(soma cifrada - soma plana) & 0xFF`.

use std::fmt;

use super::keytable::KEY_WORD;
use super::{HEADER_SIZE, MAX_MESSAGE_SIZE};

const TRANSFORM_START: usize = 4;

/// `HEADER` de 12 bytes, little-endian.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Header {
    pub size: u16,
    pub key_word: u8,
    pub check_sum: u8,
    pub msg_type: u16,
    pub id: u16,
    pub client_tick: u32,
}

/// Frame decodificado: header plano e corpo plano.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecodedFrame {
    pub header: Header,
    pub payload: Vec<u8>,
    /// `false` quando o `CheckSum` armazenado não confere.
    pub checksum_valid: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CodecError {
    FrameTooShort { got: usize },
    SizeMismatch { size: u16, actual: usize },
    SizeOutOfRange(usize),
}

impl fmt::Display for CodecError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::FrameTooShort { got } => {
                write!(f, "frame curto: {got} < {HEADER_SIZE} bytes")
            }
            Self::SizeMismatch { size, actual } => {
                write!(f, "Size do header ({size}) != frame ({actual})")
            }
            Self::SizeOutOfRange(size) => {
                write!(
                    f,
                    "Size fora da faixa {HEADER_SIZE}..={MAX_MESSAGE_SIZE}: {size}"
                )
            }
        }
    }
}

impl std::error::Error for CodecError {}

/// Escreve o header plano em `dst` por offset explícito.
pub fn encode_header(dst: &mut [u8], header: Header) -> Result<(), CodecError> {
    if dst.len() < HEADER_SIZE {
        return Err(CodecError::FrameTooShort { got: dst.len() });
    }
    dst[0..2].copy_from_slice(&header.size.to_le_bytes());
    dst[2] = header.key_word;
    dst[3] = header.check_sum;
    dst[4..6].copy_from_slice(&header.msg_type.to_le_bytes());
    dst[6..8].copy_from_slice(&header.id.to_le_bytes());
    dst[8..12].copy_from_slice(&header.client_tick.to_le_bytes());
    Ok(())
}

/// Lê o header plano de `src`.
pub fn decode_header(src: &[u8]) -> Result<Header, CodecError> {
    if src.len() < HEADER_SIZE {
        return Err(CodecError::FrameTooShort { got: src.len() });
    }
    Ok(Header {
        size: u16::from_le_bytes([src[0], src[1]]),
        key_word: src[2],
        check_sum: src[3],
        msg_type: u16::from_le_bytes([src[4], src[5]]),
        id: u16::from_le_bytes([src[6], src[7]]),
        client_tick: u32::from_le_bytes([src[8], src[9], src[10], src[11]]),
    })
}

/// Codifica um frame completo: header + corpo, ofuscado e com checksum.
///
/// `header.size`, `header.key_word` e `header.check_sum` são recalculados.
pub fn encode(header: Header, payload: &[u8], key_word: u8) -> Result<Vec<u8>, CodecError> {
    let size = HEADER_SIZE
        .checked_add(payload.len())
        .ok_or(CodecError::SizeOutOfRange(usize::MAX))?;
    if !(HEADER_SIZE..=MAX_MESSAGE_SIZE).contains(&size) {
        return Err(CodecError::SizeOutOfRange(size));
    }

    let mut wire = vec![0u8; size];
    let plain_header = Header {
        size: size as u16,
        key_word,
        check_sum: 0,
        ..header
    };
    encode_header(&mut wire, plain_header)?;
    wire[HEADER_SIZE..].copy_from_slice(payload);

    let (sum_plain, sum_cipher) = transform_encode(&mut wire, key_word);
    wire[3] = sum_cipher.wrapping_sub(sum_plain);
    Ok(wire)
}

/// Decodifica um frame completo. Não altera o slice de entrada.
///
/// O chamador decide o que fazer com `checksum_valid == false`; o gateway
/// fecha a conexão (endurecimento em relação ao legado).
pub fn decode(wire: &[u8]) -> Result<DecodedFrame, CodecError> {
    if wire.len() < HEADER_SIZE {
        return Err(CodecError::FrameTooShort { got: wire.len() });
    }
    let size = u16::from_le_bytes([wire[0], wire[1]]);
    if usize::from(size) != wire.len() {
        return Err(CodecError::SizeMismatch {
            size,
            actual: wire.len(),
        });
    }
    if !(HEADER_SIZE..=MAX_MESSAGE_SIZE).contains(&usize::from(size)) {
        return Err(CodecError::SizeOutOfRange(usize::from(size)));
    }

    let stored_check = wire[3];
    let key_word = wire[2];
    let mut buffer = wire.to_vec();
    let (sum_plain, sum_cipher) = transform_decode(&mut buffer, key_word);
    let header = decode_header(&buffer)?;

    Ok(DecodedFrame {
        header,
        payload: buffer[HEADER_SIZE..].to_vec(),
        checksum_valid: sum_cipher.wrapping_sub(sum_plain) == stored_check,
    })
}

fn transform_encode(buf: &mut [u8], key_word: u8) -> (u8, u8) {
    let mut pos = KEY_WORD[usize::from(key_word) * 2];
    let mut sum_plain = 0u8;
    let mut sum_cipher = 0u8;

    for (index, byte) in buf.iter_mut().enumerate().skip(TRANSFORM_START) {
        let plain = *byte;
        sum_plain = sum_plain.wrapping_add(plain);

        let trans = KEY_WORD[usize::from(pos) * 2 + 1];
        let cipher = match index & 0x3 {
            0 => plain.wrapping_add(trans << 1),
            1 => plain.wrapping_sub(trans >> 3),
            2 => plain.wrapping_add(trans << 2),
            _ => plain.wrapping_sub(trans >> 5),
        };
        *byte = cipher;
        sum_cipher = sum_cipher.wrapping_add(cipher);
        pos = pos.wrapping_add(1);
    }

    (sum_plain, sum_cipher)
}

fn transform_decode(buf: &mut [u8], key_word: u8) -> (u8, u8) {
    let mut pos = KEY_WORD[usize::from(key_word) * 2];
    let mut sum_plain = 0u8;
    let mut sum_cipher = 0u8;

    for (index, byte) in buf.iter_mut().enumerate().skip(TRANSFORM_START) {
        let cipher = *byte;
        sum_cipher = sum_cipher.wrapping_add(cipher);

        let trans = KEY_WORD[usize::from(pos) * 2 + 1];
        let plain = match index & 0x3 {
            0 => cipher.wrapping_sub(trans << 1),
            1 => cipher.wrapping_add(trans >> 3),
            2 => cipher.wrapping_sub(trans << 2),
            _ => cipher.wrapping_add(trans >> 5),
        };
        *byte = plain;
        sum_plain = sum_plain.wrapping_add(plain);
        pos = pos.wrapping_add(1);
    }

    (sum_plain, sum_cipher)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn header_round_trip_e_bytes_em_claro() {
        let header = Header {
            size: 116,
            key_word: 42,
            check_sum: 200,
            msg_type: 0x020D,
            id: 7,
            client_tick: 0xDEAD_BEEF,
        };
        let mut buf = [0u8; HEADER_SIZE];
        encode_header(&mut buf, header).unwrap();
        assert_eq!(&buf[..4], &[116, 0, 42, 200]);
        assert_eq!(decode_header(&buf).unwrap(), header);
    }

    #[test]
    fn codec_faz_round_trip() {
        let payloads: [&[u8]; 5] = [&[], &[1, 2, 3], &[0xFF; 64], &[0; 64], b"Hero"];
        for payload in payloads {
            for keyword in [0u8, 1, 42, 128, 255] {
                let wire = encode(
                    Header {
                        msg_type: 0x036C,
                        id: 5,
                        client_tick: 1234,
                        ..Header::default()
                    },
                    payload,
                    keyword,
                )
                .unwrap();
                assert_eq!(usize::from(wire[0]) | usize::from(wire[1]) << 8, wire.len());
                assert_eq!(wire[2], keyword);

                let decoded = decode(&wire).unwrap();
                assert!(decoded.checksum_valid);
                assert_eq!(decoded.payload, payload);
                assert_eq!(decoded.header.msg_type, 0x036C);
                assert_eq!(decoded.header.id, 5);
                assert_eq!(decoded.header.client_tick, 1234);
            }
        }
    }

    #[test]
    fn decode_nao_altera_a_entrada() {
        let wire = encode(Header::default(), &[1, 2, 3, 4], 7).unwrap();
        let original = wire.clone();
        decode(&wire).unwrap();
        assert_eq!(wire, original);
    }

    #[test]
    fn detecta_checksum_corrompido() {
        let mut wire = encode(Header::default(), &[10, 20, 30, 40], 99).unwrap();
        wire[3] = wire[3].wrapping_add(1);
        assert!(!decode(&wire).unwrap().checksum_valid);
    }

    #[test]
    fn limites_de_tamanho() {
        assert!(encode(Header::default(), &vec![0; MAX_MESSAGE_SIZE], 0).is_err());
        assert!(encode(
            Header::default(),
            &vec![0; MAX_MESSAGE_SIZE - HEADER_SIZE],
            0
        )
        .is_ok());
        assert!(decode(&[0u8; HEADER_SIZE - 1]).is_err());
        let mut header_only = [0u8; HEADER_SIZE];
        header_only[0] = HEADER_SIZE as u8;
        assert!(decode(&header_only).is_ok());
    }

    #[test]
    fn rejeita_size_divergente() {
        let mut wire = encode(Header::default(), &[1, 2, 3], 0).unwrap();
        wire[0] = wire[0].wrapping_add(1);
        assert!(matches!(
            decode(&wire),
            Err(CodecError::SizeMismatch { .. })
        ));
    }
}
