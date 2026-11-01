//! Strings de tamanho fixo do legado.
//!
//! O cliente usa cp1252 (Latin-1 do Windows). Nomes de conta/personagem são
//! ASCII na fixture e na maioria dos dumps, mas a leitura correta não deve
//! transformar 0x80..0x9F em caracteres de controle.

/// Mapeamento cp1252 para a faixa 0x80..=0x9F. Posições indefinidas no
/// cp1252 viram U+FFFD em vez de um caractere de controle.
const CP1252_HIGH: [char; 32] = [
    '\u{20AC}', '\u{FFFD}', '\u{201A}', '\u{0192}', '\u{201E}', '\u{2026}', '\u{2020}', '\u{2021}',
    '\u{02C6}', '\u{2030}', '\u{0160}', '\u{2039}', '\u{0152}', '\u{FFFD}', '\u{017D}', '\u{FFFD}',
    '\u{FFFD}', '\u{2018}', '\u{2019}', '\u{201C}', '\u{201D}', '\u{2022}', '\u{2013}', '\u{2014}',
    '\u{02DC}', '\u{2122}', '\u{0161}', '\u{203A}', '\u{0153}', '\u{FFFD}', '\u{017E}', '\u{0178}',
];

/// Decodifica bytes cp1252 (fallback Latin-1 para 0xA0..0xFF).
pub fn decode_cp1252(bytes: &[u8]) -> String {
    bytes
        .iter()
        .map(|&byte| match byte {
            0x00..=0x7F => char::from(byte),
            0x80..=0x9F => CP1252_HIGH[usize::from(byte - 0x80)],
            _ => char::from(byte),
        })
        .collect()
}

/// Lê uma string C: corta no primeiro NUL e decodifica cp1252.
pub fn c_string(bytes: &[u8]) -> String {
    let end = bytes
        .iter()
        .position(|&byte| byte == 0)
        .unwrap_or(bytes.len());
    decode_cp1252(&bytes[..end])
}

/// Escreve uma string C em um campo fixo, zerando o restante.
///
/// O PoC usa ASCII (nomes de demo). Caracteres não ASCII viram `?` para não
/// produzir um campo cp1252 inválido; a conversão completa fica para quando o
/// gateway ler nomes reais do PostgreSQL.
pub fn write_c_string(dst: &mut [u8], value: &str) {
    dst.fill(0);
    if dst.is_empty() {
        return;
    }
    let limit = dst.len().saturating_sub(1);
    for (slot, byte) in dst.iter_mut().take(limit).zip(value.bytes()) {
        *slot = if byte.is_ascii() { byte } else { b'?' };
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn corta_no_primeiro_nulo() {
        assert_eq!(c_string(b"Hero\0lixo"), "Hero");
        assert_eq!(c_string(b"Hero"), "Hero");
    }

    #[test]
    fn decodifica_cp1252_sem_controle() {
        assert_eq!(decode_cp1252(&[0x80]), "\u{20AC}");
        assert_eq!(decode_cp1252(&[0xE9]), "é");
    }

    #[test]
    fn escrita_termina_com_nulo() {
        let mut buf = [0xAAu8; 8];
        write_c_string(&mut buf, "Teste");
        assert_eq!(&buf[..6], b"Teste\0");
        assert!(buf[6..].iter().all(|&byte| byte == 0));
    }
}
