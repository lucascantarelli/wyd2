//! `STRUCT_SELCHAR` e `MSG_CNFAccountLogin`.
//!
//! Layout documentado em `docs/02-PROTOCOLO.md` §7.8:
//! corpo de 1996 bytes + header de 12 = 2008. A tela de seleção usa
//! `Score`, `Equip`, `Guild`, `Coin` e `Exp` de cada slot.

use super::text::write_c_string;

pub const SELCHAR_SIZE: usize = 840;
pub const CNF_BODY_SIZE: usize = 1996;
pub const CNF_FRAME_SIZE: usize = 2008;
pub const CNF_SELCHAR_OFFSET: usize = 20;
pub const CNF_CARGO_OFFSET: usize = 860;
pub const CNF_COIN_OFFSET: usize = 1884;
pub const CNF_ACCOUNT_NAME_OFFSET: usize = 1888;
pub const CARGO_SLOTS: usize = 128;
pub const EQUIP_SLOTS: usize = 16;
/// `ID` do header para a tela de seleção (`ESCENE_FIELD + 2`).
pub const ID_SEL_CHAR: u16 = 30002;

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct WireItem {
    pub index: i16,
    pub effects: [(u8, u8); 3],
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SelChar {
    pub slot: u8,
    pub name: String,
    pub spx: i16,
    pub spy: i16,
    pub level: i32,
    pub max_hp: i32,
    pub hp: i32,
    pub max_mp: i32,
    pub mp: i32,
    pub strength: i16,
    pub intelligence: i16,
    pub dexterity: i16,
    pub constitution: i16,
    pub merchant: u8,
    pub attack_run: u8,
    pub direction: u8,
    pub chaos_rate: u8,
    pub ac: i32,
    pub damage: i32,
    pub special: [i16; 4],
    pub guild: u16,
    pub coin: i32,
    pub exp: i64,
    pub equip: [WireItem; EQUIP_SLOTS],
}

impl SelChar {
    pub fn new(slot: u8, name: impl Into<String>) -> Self {
        Self {
            slot,
            name: name.into(),
            ..Self::default()
        }
    }
}

/// Serializa quatro slots em 840 bytes; slots vazios ficam zerados.
pub fn encode_selchar(chars: &[SelChar]) -> [u8; SELCHAR_SIZE] {
    let mut out = [0u8; SELCHAR_SIZE];
    for character in chars {
        if character.slot >= 4 {
            continue;
        }
        let slot = usize::from(character.slot);
        put_i16(&mut out, slot * 2, character.spx);
        put_i16(&mut out, 8 + slot * 2, character.spy);

        let name_offset = 16 + slot * 16;
        write_c_string(&mut out[name_offset..name_offset + 16], &character.name);

        encode_score(&mut out, 80 + slot * 48, character);

        let equip_offset = 272 + slot * 128;
        for (index, item) in character.equip.iter().enumerate() {
            encode_item(&mut out, equip_offset + index * 8, *item);
        }

        put_u16(&mut out, 784 + slot * 2, character.guild);
        put_i32(&mut out, 792 + slot * 4, character.coin);
        put_i64(&mut out, 808 + slot * 8, character.exp);
    }
    out
}

/// Monta o corpo de `MSG_CNFAccountLogin` (1996 bytes).
///
/// `HashKeyTable`, `Keys`, `QuestDiaria`, `BlockPass` e `IsBlocked` ficam
/// zerados neste PoC; `Unknow_28` é 1 para não recriar as poções iniciais.
pub fn encode_cnf_body(
    account_name: &str,
    chars: &[SelChar],
    coin: i32,
    cargo: &[WireItem; CARGO_SLOTS],
) -> Vec<u8> {
    let mut body = vec![0u8; CNF_BODY_SIZE];
    put_i32(&mut body, 16, 1);
    body[CNF_SELCHAR_OFFSET..CNF_SELCHAR_OFFSET + SELCHAR_SIZE]
        .copy_from_slice(&encode_selchar(chars));
    for (index, item) in cargo.iter().enumerate() {
        encode_item(&mut body, CNF_CARGO_OFFSET + index * 8, *item);
    }
    put_i32(&mut body, CNF_COIN_OFFSET, coin);
    write_c_string(
        &mut body[CNF_ACCOUNT_NAME_OFFSET..CNF_ACCOUNT_NAME_OFFSET + 16],
        account_name,
    );
    body
}

fn encode_score(out: &mut [u8], offset: usize, character: &SelChar) {
    put_i32(out, offset, character.level);
    put_i32(out, offset + 4, character.ac);
    put_i32(out, offset + 8, character.damage);
    out[offset + 12] = character.merchant;
    out[offset + 13] = character.attack_run;
    out[offset + 14] = character.direction;
    out[offset + 15] = character.chaos_rate;
    put_i32(out, offset + 16, character.max_hp);
    put_i32(out, offset + 20, character.max_mp);
    put_i32(out, offset + 24, character.hp);
    put_i32(out, offset + 28, character.mp);
    put_i16(out, offset + 32, character.strength);
    put_i16(out, offset + 34, character.intelligence);
    put_i16(out, offset + 36, character.dexterity);
    put_i16(out, offset + 38, character.constitution);
    for (index, value) in character.special.iter().enumerate() {
        put_i16(out, offset + 40 + index * 2, *value);
    }
}

fn encode_item(out: &mut [u8], offset: usize, item: WireItem) {
    put_i16(out, offset, item.index);
    for (index, (effect, value)) in item.effects.iter().enumerate() {
        out[offset + 2 + index * 2] = *effect;
        out[offset + 3 + index * 2] = *value;
    }
}

fn put_i16(out: &mut [u8], offset: usize, value: i16) {
    out[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
}

fn put_u16(out: &mut [u8], offset: usize, value: u16) {
    out[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
}

fn put_i32(out: &mut [u8], offset: usize, value: i32) {
    out[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}

fn put_i64(out: &mut [u8], offset: usize, value: i64) {
    out[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::codec::{self, Header};
    use crate::protocol::MSG_CNF_ACCOUNT_LOGIN;

    fn demo_character() -> SelChar {
        let mut character = SelChar::new(0, "Hero");
        character.spx = 100;
        character.spy = 200;
        character.level = 50;
        character.max_hp = 1200;
        character.hp = 700;
        character.max_mp = 600;
        character.mp = 250;
        character.strength = 31;
        character.intelligence = 11;
        character.dexterity = 21;
        character.constitution = 26;
        character.direction = 2;
        character.guild = 7;
        character.coin = 1500;
        character.exp = 250_000;
        character.special = [1, 2, 3, 4];
        character.equip[0] = WireItem {
            index: 100,
            effects: [(43, 230), (1, 5), (0, 0)],
        };
        character
    }

    #[test]
    fn selchar_tem_tamanho_e_offsets_documentados() {
        assert_eq!(SELCHAR_SIZE, 840);
        let character = demo_character();
        let encoded = encode_selchar(std::slice::from_ref(&character));
        assert_eq!(&encoded[16..20], b"Hero");
        assert_eq!(i32::from_le_bytes(encoded[80..84].try_into().unwrap()), 50);
        assert_eq!(i32::from_le_bytes(encoded[84..88].try_into().unwrap()), 0);
        assert_eq!(i32::from_le_bytes(encoded[88..92].try_into().unwrap()), 0);
        assert_eq!(encoded[94], 2);
        assert_eq!(
            i32::from_le_bytes(encoded[96..100].try_into().unwrap()),
            1200
        );
        assert_eq!(
            i16::from_le_bytes(encoded[112..114].try_into().unwrap()),
            31
        );
        assert_eq!(u16::from_le_bytes(encoded[784..786].try_into().unwrap()), 7);
        assert_eq!(
            i32::from_le_bytes(encoded[792..796].try_into().unwrap()),
            1500
        );
        assert_eq!(
            i64::from_le_bytes(encoded[808..816].try_into().unwrap()),
            250_000
        );
        assert_eq!(i16::from_le_bytes(encoded[0..2].try_into().unwrap()), 100);
    }

    #[test]
    fn cnf_tem_2008_bytes_e_campos_nos_offsets() {
        let mut cargo = [WireItem::default(); CARGO_SLOTS];
        cargo[0] = WireItem {
            index: 300,
            effects: [(43, 240), (0, 0), (0, 0)],
        };
        let body = encode_cnf_body("TestAccount", &[demo_character()], 500, &cargo);
        assert_eq!(body.len(), CNF_BODY_SIZE);
        assert_eq!(i32::from_le_bytes(body[16..20].try_into().unwrap()), 1);
        assert_eq!(&body[20 + 16..20 + 20], b"Hero");
        assert_eq!(
            i16::from_le_bytes(
                body[CNF_CARGO_OFFSET..CNF_CARGO_OFFSET + 2]
                    .try_into()
                    .unwrap()
            ),
            300
        );
        assert_eq!(
            i32::from_le_bytes(
                body[CNF_COIN_OFFSET..CNF_COIN_OFFSET + 4]
                    .try_into()
                    .unwrap()
            ),
            500
        );
        assert_eq!(
            &body[CNF_ACCOUNT_NAME_OFFSET..CNF_ACCOUNT_NAME_OFFSET + 11],
            b"TestAccount"
        );

        let wire = codec::encode(
            Header {
                msg_type: MSG_CNF_ACCOUNT_LOGIN,
                id: 30002,
                ..Header::default()
            },
            &body,
            42,
        )
        .unwrap();
        assert_eq!(wire.len(), CNF_FRAME_SIZE);
        let decoded = codec::decode(&wire).unwrap();
        assert_eq!(decoded.header.msg_type, MSG_CNF_ACCOUNT_LOGIN);
        assert_eq!(decoded.header.id, 30002);
        assert!(decoded.checksum_valid);
    }

    #[test]
    fn slot_fora_da_faixa_e_ignorado() {
        let mut character = demo_character();
        character.slot = 4;
        let encoded = encode_selchar(&[character]);
        assert!(encoded.iter().all(|&byte| byte == 0));
    }
}
