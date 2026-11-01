//! Diretório PostgreSQL: `wyd.accounts`, `wyd.characters`, `wyd.items` e
//! `catalog.items`.
//!
//! As consultas são preparadas uma vez no início do processo e todas usam
//! parâmetros vinculados. O login é comparado por `lower(login)`, o mesmo
//! índice canônico do schema. O diretório não grava nada: leitura apenas.
//!
//! Todo `item_index` gravado em `wyd.items` precisa existir em `catalog.items`:
//! o cliente resolve o índice no catálogo local, então enviar um índice que
//! ele não conhece produz item errado (ou invisível). A validação acontece no
//! carregamento da conta e falha a sessão com erro de operador.

use std::collections::HashMap;
use std::sync::Mutex;

use postgres::types::ToSql;
use postgres::{Client, Config, NoTls, Row, Statement};

use crate::directory::{Account, Credential, Directory, DirectoryError, DirectoryResult};
use crate::protocol::selchar::{SelChar, WireItem, CARGO_SLOTS, EQUIP_SLOTS};

const ACCOUNT_SQL: &str = "\
SELECT login, password_hash, blocked, cargo_gold
FROM wyd.accounts
WHERE lower(login) = lower($1)";

const CHARACTERS_SQL: &str = "\
SELECT c.id::text AS id,
       c.slot,
       c.name,
       c.spx,
       c.spy,
       c.level,
       c.current_max_hp,
       c.current_hp,
       c.current_max_mp,
       c.current_mp,
       c.current_str,
       c.current_int,
       c.current_dex,
       c.current_con,
       c.merchant,
       c.attack_run,
       c.direction,
       c.chaos_rate,
       c.current_ac,
       c.current_damage,
       c.current_special,
       c.guild_legacy_id,
       c.gold,
       c.exp
FROM wyd.characters c
JOIN wyd.accounts a ON a.id = c.account_id
WHERE lower(a.login) = lower($1)
ORDER BY c.slot";

const EQUIP_SQL: &str = "\
SELECT i.owner_character_id::text AS character_id,
       i.slot,
       i.item_index,
       EXISTS (SELECT 1 FROM catalog.items c WHERE c.item_index = i.item_index)
           AS catalog_known,
       i.effect_0_type,
       i.effect_0_value,
       i.effect_1_type,
       i.effect_1_value,
       i.effect_2_type,
       i.effect_2_value
FROM wyd.items i
JOIN wyd.characters c ON c.id = i.owner_character_id
JOIN wyd.accounts a ON a.id = c.account_id
WHERE lower(a.login) = lower($1)
  AND i.container = 'equip'
ORDER BY i.owner_character_id, i.slot";

const CARGO_SQL: &str = "\
SELECT i.slot,
       i.item_index,
       EXISTS (SELECT 1 FROM catalog.items c WHERE c.item_index = i.item_index)
           AS catalog_known,
       i.effect_0_type,
       i.effect_0_value,
       i.effect_1_type,
       i.effect_1_value,
       i.effect_2_type,
       i.effect_2_value
FROM wyd.items i
JOIN wyd.accounts a ON a.id = i.owner_account_id
WHERE lower(a.login) = lower($1)
  AND i.container = 'cargo'
ORDER BY i.slot";

pub struct PostgresDirectory {
    conn: Mutex<Client>,
    account_stmt: Statement,
    characters_stmt: Statement,
    equip_stmt: Statement,
    cargo_stmt: Statement,
}

impl PostgresDirectory {
    /// Abre a conexão e prepara as consultas. Uma falha aqui impede o boot:
    /// o gateway não deve subir aparentando autenticar sem banco.
    pub fn connect(database_url: &str) -> Result<Self, DirectoryError> {
        // Parse separado para nunca ecoar a connection string (que pode
        // conter senha) em uma mensagem de erro.
        let config: Config = database_url.parse().map_err(|_| {
            DirectoryError::Unavailable(
                "connection string invalida; use postgres://... ou host=... user=... dbname=..."
                    .to_owned(),
            )
        })?;
        let conn = config
            .connect(NoTls)
            .map_err(|err| DirectoryError::Unavailable(err.to_string()))?;
        Self::from_client(conn)
    }

    fn from_client(mut conn: Client) -> Result<Self, DirectoryError> {
        let account_stmt = prepare(&mut conn, ACCOUNT_SQL)?;
        let characters_stmt = prepare(&mut conn, CHARACTERS_SQL)?;
        let equip_stmt = prepare(&mut conn, EQUIP_SQL)?;
        let cargo_stmt = prepare(&mut conn, CARGO_SQL)?;
        Ok(Self {
            conn: Mutex::new(conn),
            account_stmt,
            characters_stmt,
            equip_stmt,
            cargo_stmt,
        })
    }
}

impl Directory for PostgresDirectory {
    fn find(&self, login: &str) -> DirectoryResult<Option<Account>> {
        let mut conn = self
            .conn
            .lock()
            .map_err(|_| DirectoryError::Unavailable("mutex do banco envenenado".to_owned()))?;

        let params: &[&(dyn ToSql + Sync)] = &[&login];
        let Some(row) = conn
            .query_opt(&self.account_stmt, params)
            .map_err(|err| DirectoryError::Query(format!("conta: {err}")))?
        else {
            return Ok(None);
        };

        let login: String = row.get("login");
        let password_hash: String = row.get("password_hash");
        let blocked: bool = row.get("blocked");
        let cargo_gold: i64 = row.get("cargo_gold");
        let cargo_coin = narrow_i32(cargo_gold, "cargo_gold")?;

        let mut loaded = Vec::new();
        for character_row in conn
            .query(&self.characters_stmt, params)
            .map_err(|err| DirectoryError::Query(format!("personagens: {err}")))?
        {
            loaded.push(load_character(&character_row)?);
        }

        let mut equipment: HashMap<String, Vec<(usize, WireItem)>> = HashMap::new();
        for item_row in conn
            .query(&self.equip_stmt, params)
            .map_err(|err| DirectoryError::Query(format!("equipamentos: {err}")))?
        {
            let character_id: String = item_row.get("character_id");
            let (slot, item) = load_item(&item_row, "slot", "equip")?;
            if slot >= EQUIP_SLOTS {
                return Err(DirectoryError::Query(format!(
                    "item de equipamento no slot {slot}, fora de 0..{EQUIP_SLOTS}"
                )));
            }
            let slots = equipment.entry(character_id).or_default();
            if slots.iter().any(|(occupied, _)| *occupied == slot) {
                return Err(DirectoryError::Query(format!(
                    "equipamento duplicado no slot {slot}"
                )));
            }
            slots.push((slot, item));
        }

        let mut characters = Vec::with_capacity(loaded.len());
        for (character_id, mut character) in loaded {
            if let Some(items) = equipment.remove(&character_id) {
                for (slot, item) in items {
                    character.equip[slot] = item;
                }
            }
            characters.push(character);
        }

        let mut cargo = [WireItem::default(); CARGO_SLOTS];
        for item_row in conn
            .query(&self.cargo_stmt, params)
            .map_err(|err| DirectoryError::Query(format!("cargo: {err}")))?
        {
            let (slot, item) = load_item(&item_row, "slot", "cargo")?;
            if slot >= CARGO_SLOTS {
                return Err(DirectoryError::Query(format!(
                    "item de cargo no slot {slot}, fora de 0..{CARGO_SLOTS}"
                )));
            }
            cargo[slot] = item;
        }

        Ok(Some(Account {
            login,
            credential: Credential::PasswordHash(password_hash),
            blocked,
            characters,
            cargo_coin,
            cargo,
        }))
    }
}

fn prepare(conn: &mut Client, sql: &str) -> Result<Statement, DirectoryError> {
    conn.prepare(sql)
        .map_err(|err| DirectoryError::Query(format!("preparar consulta: {err}")))
}

fn load_character(row: &Row) -> DirectoryResult<(String, SelChar)> {
    let id: String = row.get("id");
    let slot = narrow_u8(row.get::<_, i16>("slot"), "characters.slot")?;
    if slot >= 4 {
        return Err(DirectoryError::Query(format!(
            "personagem {id} com slot {slot}; esperado 0..4"
        )));
    }

    let spx = row.get::<_, Option<i32>>("spx").unwrap_or(0);
    let spy = row.get::<_, Option<i32>>("spy").unwrap_or(0);

    let mut character = SelChar::new(slot, row.get::<_, String>("name"));
    character.spx = narrow_i16(spx, "characters.spx")?;
    character.spy = narrow_i16(spy, "characters.spy")?;
    character.level = row.get("level");
    character.max_hp = row.get("current_max_hp");
    character.hp = row.get("current_hp");
    character.max_mp = row.get("current_max_mp");
    character.mp = row.get("current_mp");
    character.strength = row.get("current_str");
    character.intelligence = row.get("current_int");
    character.dexterity = row.get("current_dex");
    character.constitution = row.get("current_con");
    character.merchant = narrow_u8(row.get::<_, i16>("merchant"), "characters.merchant")?;
    character.attack_run = narrow_u8(row.get::<_, i16>("attack_run"), "characters.attack_run")?;
    character.direction = narrow_u8(row.get::<_, i16>("direction"), "characters.direction")?;
    character.chaos_rate = narrow_u8(row.get::<_, i16>("chaos_rate"), "characters.chaos_rate")?;
    character.ac = row.get("current_ac");
    character.damage = row.get("current_damage");

    let special: Vec<i16> = row.get("current_special");
    if special.len() > 4 {
        return Err(DirectoryError::Query(format!(
            "personagem {id} com {} valores em current_special; esperado no maximo 4",
            special.len()
        )));
    }
    for (index, value) in special.iter().enumerate() {
        character.special[index] = *value;
    }

    character.guild = match row.get::<_, Option<i32>>("guild_legacy_id") {
        Some(value) => narrow_u16(value, "characters.guild_legacy_id")?,
        None => 0,
    };
    character.coin = narrow_i32(row.get::<_, i64>("gold"), "characters.gold")?;
    character.exp = row.get("exp");

    Ok((id, character))
}

fn load_item(row: &Row, slot_column: &str, container: &str) -> DirectoryResult<(usize, WireItem)> {
    let slot = narrow_u8(row.get::<_, i16>(slot_column), "items.slot")?;
    let item_index = narrow_i16(row.get::<_, i32>("item_index"), "items.item_index")?;
    if item_index <= 0 {
        return Err(DirectoryError::Query(
            "items.item_index precisa ser positivo".to_owned(),
        ));
    }
    ensure_catalog_known(row.get::<_, bool>("catalog_known"), container, item_index)?;

    let effects = [
        (
            narrow_u8(row.get::<_, i16>("effect_0_type"), "items.effect_0_type")?,
            narrow_u8(row.get::<_, i16>("effect_0_value"), "items.effect_0_value")?,
        ),
        (
            narrow_u8(row.get::<_, i16>("effect_1_type"), "items.effect_1_type")?,
            narrow_u8(row.get::<_, i16>("effect_1_value"), "items.effect_1_value")?,
        ),
        (
            narrow_u8(row.get::<_, i16>("effect_2_type"), "items.effect_2_type")?,
            narrow_u8(row.get::<_, i16>("effect_2_value"), "items.effect_2_value")?,
        ),
    ];

    Ok((
        usize::from(slot),
        WireItem {
            index: item_index,
            effects,
        },
    ))
}

/// Recusa o item quando o indice nao existe em `catalog.items`. O cliente
/// resolve o indice no catalogo local; enviar um indice desconhecido produz
/// item errado ou invisivel, entao a sessao falha em vez de seguir.
fn ensure_catalog_known(
    catalog_known: bool,
    container: &str,
    item_index: i16,
) -> DirectoryResult<()> {
    if catalog_known {
        return Ok(());
    }
    Err(DirectoryError::Query(format!(
        "item de {container} com item_index {item_index} nao existe em catalog.items; carregue o catalogo do cliente (schema/002_catalog.sql + load_catalog.sql)"
    )))
}

fn narrow_u8(value: i16, field: &str) -> DirectoryResult<u8> {
    u8::try_from(value)
        .map_err(|_| DirectoryError::Query(format!("{field}={value} nao cabe em u8")))
}

fn narrow_u16(value: i32, field: &str) -> DirectoryResult<u16> {
    u16::try_from(value)
        .map_err(|_| DirectoryError::Query(format!("{field}={value} nao cabe em u16")))
}

fn narrow_i16(value: i32, field: &str) -> DirectoryResult<i16> {
    i16::try_from(value)
        .map_err(|_| DirectoryError::Query(format!("{field}={value} nao cabe em i16")))
}

fn narrow_i32(value: i64, field: &str) -> DirectoryResult<i32> {
    i32::try_from(value)
        .map_err(|_| DirectoryError::Query(format!("{field}={value} nao cabe em i32")))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn item_fora_do_catalogo_falha_com_erro_claro() {
        assert!(ensure_catalog_known(true, "equip", 100).is_ok());

        let error = ensure_catalog_known(false, "equip", 9999).unwrap_err();
        let message = error.to_string();
        assert!(message.contains("9999"), "{message}");
        assert!(message.contains("equip"), "{message}");
        assert!(message.contains("catalog.items"), "{message}");
        assert!(message.contains("load_catalog.sql"), "{message}");
    }

    #[test]
    fn conversoes_recusam_valores_que_nao_cabem_no_fio() {
        assert_eq!(narrow_u8(255, "x").unwrap(), 255);
        assert!(narrow_u8(256, "x").is_err());
        assert_eq!(narrow_i16(-32_768, "x").unwrap(), -32_768);
        assert!(narrow_i16(32_768, "x").is_err());
        assert_eq!(narrow_u16(65_535, "x").unwrap(), 65_535);
        assert!(narrow_u16(65_536, "x").is_err());
        assert_eq!(narrow_i32(2_147_483_647, "x").unwrap(), 2_147_483_647);
        assert!(narrow_i32(2_147_483_648, "x").is_err());
    }
}
