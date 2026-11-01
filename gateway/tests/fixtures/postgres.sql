-- Fixture do teste de integração do gateway.
-- A senha de TestAccount/BlockedAccount é "Secret123!" (PBKDF2 1000 iterações).
-- O hash abaixo é o mesmo vetor coberto pelos testes unitários do gateway.

SET search_path TO wyd, public;

TRUNCATE wyd.items, wyd.characters, wyd.accounts CASCADE;
-- Catalogo: o gateway recusa item cujo index nao exista aqui.
TRUNCATE catalog.item_effects, catalog.items CASCADE;

INSERT INTO catalog.items (item_index, name, mesh, source_offset)
VALUES
    (100, 'Steel_Helmet', 1, 4),
    (101, 'Steel_Sword', 2, 4),
    (200, 'Potion', 3, 4);

INSERT INTO wyd.accounts
    (id, login, password_hash, password_algo, cargo_gold, blocked)
VALUES
    ('11111111-1111-1111-1111-111111111111',
     'TestAccount',
     'pbkdf2-sha256$1000$MDEyMzQ1Njc4OWFiY2RlZg==$nibRk0BLojzFhMvAObtOXTZRhpPNAF/ntMkY5zAJpoY=',
     'pbkdf2-sha256',
     777,
     false),
    ('22222222-2222-2222-2222-222222222222',
     'BlockedAccount',
     'pbkdf2-sha256$1000$MDEyMzQ1Njc4OWFiY2RlZg==$nibRk0BLojzFhMvAObtOXTZRhpPNAF/ntMkY5zAJpoY=',
     'pbkdf2-sha256',
     0,
     true),
    -- Conta cujo inventario tem item fora do catalogo: o login deve falhar.
    ('33333333-3333-3333-3333-333333333333',
     'BrokenCatalogAccount',
     'pbkdf2-sha256$1000$MDEyMzQ1Njc4OWFiY2RlZg==$nibRk0BLojzFhMvAObtOXTZRhpPNAF/ntMkY5zAJpoY=',
     'pbkdf2-sha256',
     0,
     false);

INSERT INTO wyd.characters
    (id, account_id, slot, name, class, class_master,
     guild_legacy_id, guild_level, level, exp, gold, spx, spy,
     current_ac, current_damage, current_max_hp, current_hp,
     current_max_mp, current_mp, current_str, current_int, current_dex,
     current_con, current_special, merchant, attack_run, direction, chaos_rate)
VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1',
     '11111111-1111-1111-1111-111111111111',
     0, 'Hero', 0, 2, 7, 3, 50, 250000, 1500, 100, 200,
     12, 25, 1200, 700, 600, 250, 31, 11, 21, 26,
     ARRAY[1, 2, 3, 4]::smallint[], 0, 1, 2, 0),
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3',
     '33333333-3333-3333-3333-333333333333',
     0, 'Broken', 0, 0, NULL, 0, 1, 0, 0, 0, 0,
     0, 0, 10, 10, 10, 10, 1, 1, 1, 1,
     ARRAY[]::smallint[], 0, 0, 0, 0),
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2',
     '11111111-1111-1111-1111-111111111111',
     1, 'Mage', 1, 2, NULL, 0, 10, 1000, 500, 110, 210,
     3, 5, 200, 150, 800, 700, 9, 40, 14, 18,
     ARRAY[]::smallint[], 0, 0, 0, 0);

INSERT INTO wyd.items
    (id, owner_character_id, owner_account_id, container, slot, item_index,
     refine, gem, effect_0_type, effect_0_value, effect_1_type,
     effect_1_value, effect_2_type, effect_2_value)
VALUES
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1',
     'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', NULL, 'equip', 0, 100,
     14, 1, 43, 230, 1, 5, 0, 0),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2',
     'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', NULL, 'equip', 1, 101,
     0, NULL, 2, 7, 0, 0, 0, 0),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb3',
     NULL, '11111111-1111-1111-1111-111111111111', 'cargo', 3, 200,
     0, NULL, 9, 4, 0, 0, 0, 0),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb4',
     'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3', NULL, 'equip', 0, 9999,
     0, NULL, 0, 0, 0, 0, 0, 0);
