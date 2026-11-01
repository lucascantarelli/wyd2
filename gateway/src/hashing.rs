//! Verificação dos hashes de senha gravados pelo importador.
//!
//! O importador grava PHC argon2id (`$argon2id$...`) ou
//! `pbkdf2-sha256$iterações$salt_b64$hash_b64`. O gateway não gera hashes:
//! só verifica, para não duplicar a política de hash na fase de importação.
//! A verificação usa as crates `argon2` (RustCrypto) e `pbkdf2`; criptografia
//! não é reimplementada aqui.

use std::fmt;

use argon2::password_hash::{Error as PasswordHashError, PasswordHash, PasswordVerifier};
use argon2::Argon2;
use base64::engine::general_purpose::{STANDARD, STANDARD_NO_PAD};
use base64::Engine;
use sha2::Sha256;

/// O importador usa 600k; o teto evita que uma linha adulterada force CPU
/// excessiva por tentativa de login.
const MAX_PBKDF2_ITERATIONS: u32 = 10_000_000;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum HashError {
    /// Prefixo desconhecido; a senha não pode ser verificada.
    Unsupported(String),
    /// Hash truncado, PHC inválido ou parâmetro fora da faixa aceita.
    Malformed(String),
}

impl fmt::Display for HashError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Unsupported(algorithm) => {
                write!(f, "algoritmo de hash nao suportado: {algorithm}")
            }
            Self::Malformed(reason) => write!(f, "hash de senha invalido: {reason}"),
        }
    }
}

impl std::error::Error for HashError {}

/// Verifica uma senha contra o valor persistido em `accounts.password_hash`.
///
/// `Ok(false)` é senha errada; `Err` é hash inválido ou algoritmo não
/// suportado. O chamador deve tratar os dois como falha de login, mas só
/// registrar o erro interno no log.
pub fn verify_password(stored: &str, password: &str) -> Result<bool, HashError> {
    let stored = stored.trim();
    if stored.is_empty() {
        return Err(HashError::Malformed("hash vazio".to_owned()));
    }

    if stored.starts_with("$argon2id$") {
        return verify_argon2id(stored, password);
    }
    if stored.starts_with("$argon2") {
        return Err(HashError::Unsupported(algorithm_of(stored)));
    }
    if let Some(rest) = stored.strip_prefix("pbkdf2-sha256$") {
        return verify_pbkdf2(rest, password.as_bytes());
    }

    Err(HashError::Unsupported(algorithm_of(stored)))
}

fn algorithm_of(stored: &str) -> String {
    stored
        .split('$')
        .find(|part| !part.is_empty())
        .unwrap_or("<vazio>")
        .to_owned()
}

fn verify_argon2id(stored: &str, password: &str) -> Result<bool, HashError> {
    // O PHC canônico não usa padding, mas hashes gerados por bibliotecas
    // diferentes podem trazê-lo. `password-hash` recusa `=`; normalizamos.
    let normalized = if stored.contains('=') {
        stored
            .split('$')
            .map(|field| field.trim_end_matches('='))
            .collect::<Vec<_>>()
            .join("$")
    } else {
        stored.to_owned()
    };
    let parsed = PasswordHash::new(&normalized)
        .map_err(|err| HashError::Malformed(format!("PHC argon2: {err}")))?;

    match Argon2::default().verify_password(password.as_bytes(), &parsed) {
        Ok(()) => Ok(true),
        Err(PasswordHashError::Password) => Ok(false),
        Err(err) => Err(HashError::Malformed(err.to_string())),
    }
}

fn verify_pbkdf2(rest: &str, password: &[u8]) -> Result<bool, HashError> {
    let mut parts = rest.splitn(3, '$');
    let iterations = parts
        .next()
        .ok_or_else(|| HashError::Malformed("PBKDF2 sem iteracoes".to_owned()))?;
    let salt_b64 = parts
        .next()
        .ok_or_else(|| HashError::Malformed("PBKDF2 sem salt".to_owned()))?;
    let hash_b64 = parts
        .next()
        .ok_or_else(|| HashError::Malformed("PBKDF2 sem hash".to_owned()))?;

    let iterations: u32 = iterations
        .parse()
        .map_err(|_| HashError::Malformed("iteracoes PBKDF2 nao numericas".to_owned()))?;
    if iterations == 0 || iterations > MAX_PBKDF2_ITERATIONS {
        return Err(HashError::Malformed(format!(
            "iteracoes PBKDF2 fora da faixa: {iterations}"
        )));
    }

    let salt = decode_b64(salt_b64)?;
    let expected = decode_b64(hash_b64)?;
    if !(8..=64).contains(&salt.len()) {
        return Err(HashError::Malformed(
            "tamanho de salt PBKDF2 invalido".to_owned(),
        ));
    }
    if !(16..=64).contains(&expected.len()) {
        return Err(HashError::Malformed(
            "tamanho de hash PBKDF2 invalido".to_owned(),
        ));
    }

    let mut derived = vec![0u8; expected.len()];
    pbkdf2::pbkdf2_hmac::<Sha256>(password, &salt, iterations, &mut derived);
    Ok(constant_time_eq(&derived, &expected))
}

fn decode_b64(input: &str) -> Result<Vec<u8>, HashError> {
    STANDARD
        .decode(input)
        .or_else(|_| STANDARD_NO_PAD.decode(input))
        .map_err(|err| HashError::Malformed(format!("base64: {err}")))
}

fn constant_time_eq(left: &[u8], right: &[u8]) -> bool {
    if left.len() != right.len() {
        return false;
    }
    let mut difference = 0u8;
    for (left, right) in left.iter().zip(right.iter()) {
        difference |= left ^ right;
    }
    difference == 0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pbkdf2_confere_com_o_importador_e_rejeita_senha_errada() {
        let stored = "pbkdf2-sha256$1000$MDEyMzQ1Njc4OWFiY2RlZg==$\
                      nibRk0BLojzFhMvAObtOXTZRhpPNAF/ntMkY5zAJpoY=";
        assert!(verify_password(stored, "Secret123!").unwrap());
        assert!(!verify_password(stored, "secret123!").unwrap());
        assert!(!verify_password(stored, "").unwrap());
    }

    #[test]
    fn pbkdf2_com_iteracoes_de_producao_tambem_confere() {
        let stored = "pbkdf2-sha256$600000$MDEyMzQ1Njc4OWFiY2RlZg==$\
                      nv6IWRZ4rw+jq8KPLvvKumO/hTt8Zb6S3fUs5WCqEFY=";
        assert!(verify_password(stored, "Secret123!").unwrap());
    }

    #[test]
    fn argon2id_com_parametros_de_producao_confere_com_referencia() {
        // Vetor gerado por argon2-cffi 25.x, Type.ID, v=19, m=19456, t=2, p=1.
        let stored = "$argon2id$v=19$m=19456,t=2,p=1$\
                      MDEyMzQ1Njc4OWFiY2RlZg==$\
                      0qsHs573+LgGInzYb7sRqlOTBmqY4X6srNEm6ybpJ20=";
        assert!(verify_password(stored, "password").unwrap());
        assert!(!verify_password(stored, "errada").unwrap());
    }

    #[test]
    fn argon2id_com_padding_tambem_e_aceito() {
        let stored = "$argon2id$v=19$m=19456,t=2,p=1$\
                      MDEyMzQ1Njc4OWFiY2RlZg==$\
                      0qsHs573+LgGInzYb7sRqlOTBmqY4X6srNEm6ybpJ20=";
        assert!(verify_password(stored, "password").unwrap());
    }

    #[test]
    fn argon2id_aceita_phc_sem_padding() {
        let stored = "$argon2id$v=19$m=32,t=1,p=1$\
                      CQkJCQkJCQkJCQkJCQkJCQ$\
                      QVPpMCCbkSN6YdcBJQdeeRC+UbwCsYoTV0CBhMBntu4";
        assert!(verify_password(stored, "password").unwrap());
    }

    #[test]
    fn rejeita_algoritmo_desconhecido_e_hash_vazio() {
        assert!(matches!(
            verify_password("md5$abc", "x"),
            Err(HashError::Unsupported(_))
        ));
        assert!(matches!(
            verify_password("", "x"),
            Err(HashError::Malformed(_))
        ));
        assert!(matches!(
            verify_password("pbkdf2-sha256$0$AAAA$AAAA", "x"),
            Err(HashError::Malformed(_))
        ));
        assert!(matches!(
            verify_password("$argon2i$v=19$m=32,t=1,p=1$AAAA$AAAA", "x"),
            Err(HashError::Unsupported(_))
        ));
    }

    #[test]
    fn phc_truncado_e_erro_de_formato_nao_de_senha() {
        let result = verify_password("$argon2id$v=19$m=19456", "x");
        eprintln!("phc truncado: {result:?}");
        assert!(!matches!(result, Ok(true)));
    }
}
