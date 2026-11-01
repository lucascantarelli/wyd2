//! Gateway PoC do WYD 7662.
//!
//! Cobre a camada de transporte documentada em `docs/02-PROTOCOLO.md`:
//! INITCODE, framing por `Size`, tabela `pKeyWord`, checksum e header de
//! 12 bytes. O login de conta devolve `MSG_CNFAccountLogin`; a entrada no
//! mundo ainda responde com falha controlada.
//!
//! Contas e personagens podem vir do PostgreSQL (`PostgresDirectory`) ou da
//! conta demo em memória (`DemoDirectory`). O código é uma implementação
//! clean-room a partir de `docs/` e `spec/`; a tabela de ofuscação é dado
//! público de protocolo, não código copiado.

pub mod directory;
pub mod hashing;
pub mod postgres_directory;
pub mod protocol;
pub mod rate_limit;
pub mod server;

pub use directory::{Account, Credential, DemoDirectory, Directory, DirectoryError};
pub use postgres_directory::PostgresDirectory;
pub use server::Gateway;
