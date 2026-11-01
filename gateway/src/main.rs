//! Binário do gateway PoC.

use std::env;
use std::net::TcpListener;
use std::process::ExitCode;
use std::sync::Arc;

use wyd_gateway::{DemoDirectory, Directory, Gateway, PostgresDirectory};

const DEFAULT_LISTEN: &str = "0.0.0.0:8281";
const DEFAULT_LOGIN: &str = "TestAccount";
const DEFAULT_PASSWORD: &str = "Secret123!";

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("erro: {message}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), String> {
    let mut listen = env::var("WYD_LISTEN").unwrap_or_else(|_| DEFAULT_LISTEN.to_owned());
    let mut database_url = env::var("WYD_DATABASE_URL")
        .ok()
        .filter(|value| !value.is_empty());
    let mut login = env::var("WYD_LOGIN").ok().filter(|value| !value.is_empty());
    let mut password = env::var("WYD_PASSWORD")
        .ok()
        .filter(|value| !value.is_empty());

    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--listen" => listen = next_value(&mut args, "--listen")?,
            "--database-url" => database_url = Some(next_value(&mut args, "--database-url")?),
            "--login" => login = Some(next_value(&mut args, "--login")?),
            "--password" => password = Some(next_value(&mut args, "--password")?),
            "-h" | "--help" => {
                print_usage();
                return Ok(());
            }
            other => return Err(format!("argumento desconhecido: {other}")),
        }
    }

    let listener = TcpListener::bind(&listen).map_err(|err| format!("bind {listen}: {err}"))?;
    let address = listener
        .local_addr()
        .map_err(|err| format!("local_addr: {err}"))?;

    println!("wyd-gateway 0.1.0 (Fase 3 PoC)");
    println!("escuta: {address}");
    println!("transporte: INITCODE + HEADER 12 + pKeyWord + checksum (sem TLS)");
    println!("escopo: login de conta + MSG_CNFAccountLogin; CharacterLogin responde fail");

    let directory: Arc<dyn Directory> = match database_url {
        Some(url) => {
            if login.is_some() || password.is_some() {
                eprintln!(
                    "aviso: --login/--password e WYD_LOGIN/WYD_PASSWORD sao ignorados com banco"
                );
            }
            let directory =
                PostgresDirectory::connect(&url).map_err(|err| format!("PostgreSQL: {err}"))?;
            println!(
                "contas: PostgreSQL (wyd.accounts, wyd.characters, wyd.items) + catalog.items"
            );
            Arc::new(directory)
        }
        None => {
            let login = login.unwrap_or_else(|| DEFAULT_LOGIN.to_owned());
            let password = password.unwrap_or_else(|| DEFAULT_PASSWORD.to_owned());
            if login.is_empty() || password.is_empty() {
                return Err("--login e --password nao podem ser vazios no modo demo".to_owned());
            }
            println!("contas: demo em memoria ({login})");
            Arc::new(DemoDirectory::with_demo_account(login, password))
        }
    };

    println!("documentacao: docs/02-PROTOCOLO.md §7.8 e gateway/README.md");

    let gateway = Arc::new(Gateway::new(directory));
    gateway.serve(listener);
    Ok(())
}

fn next_value(args: &mut impl Iterator<Item = String>, flag: &str) -> Result<String, String> {
    args.next().ok_or_else(|| format!("{flag} exige um valor"))
}

fn print_usage() {
    println!(
        "uso: wyd-gateway [--listen ADDR] [--database-url URL | --login NOME --password SENHA]\n\
         \n\
         padroes: listen={DEFAULT_LISTEN}, login={DEFAULT_LOGIN}\n\
         variaveis: WYD_LISTEN, WYD_DATABASE_URL, WYD_LOGIN, WYD_PASSWORD\n\
         \n\
         Com --database-url/WYD_DATABASE_URL o gateway le wyd.accounts,\n\
         wyd.characters e wyd.items, e recusa item cujo index nao exista em\n\
         catalog.items. Sem banco, sobe a conta demo em memoria.\n\
         A senha e os hashes nao sao registrados em log. Nao ha TLS: o banco\n\
         deve estar em rede confiavel (ou tunel) e o gateway nao deve ser\n\
         exposto a internet sem uma camada de protecao."
    );
}
