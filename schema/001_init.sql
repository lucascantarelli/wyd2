-- =============================================================================
-- WYD Next-Gen -- Fase 2: schema de persistencia
--
-- Alvo: PostgreSQL 16+.
-- Aplicar UMA VEZ em um banco vazio:
--     psql -d wyd -f schema/001_init.sql
--
-- Decisoes:
--  * Todo item instanciado tem UUID (nunca o sIndex legado como identidade).
--  * Item tem dono por personagem (equip/carry) OU por conta (cargo), nunca os dois.
--  * O ledger e append-only: UPDATE/DELETE/TRUNCATE sao bloqueados por trigger.
--  * Importacao e idempotente por chaves deterministicas (ver importer/ids.py).
--  * Senha e PIN nunca entram em claro; o schema so aceita hash.
-- =============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS wyd;
SET LOCAL search_path TO wyd, public;

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------

CREATE TYPE item_container AS ENUM ('equip', 'carry', 'cargo');

CREATE TYPE ledger_reason AS ENUM (
    'import', 'trade', 'drop', 'pickup', 'buy', 'sell',
    'refine', 'combine', 'quest', 'admin', 'death', 'unknown'
);

CREATE TYPE import_mode AS ENUM ('dry_run', 'commit');

CREATE TYPE import_status AS ENUM ('running', 'succeeded', 'partial', 'failed');

-- ---------------------------------------------------------------------------
-- Contas
-- ---------------------------------------------------------------------------

CREATE TABLE accounts (
    id                  uuid PRIMARY KEY,
    login               text NOT NULL,
    password_hash       text NOT NULL,
    password_algo       text NOT NULL
                        CHECK (password_algo IN ('argon2id', 'pbkdf2-sha256')),
    numeric_token_hash  text,
    email               text,
    blocked             boolean NOT NULL DEFAULT false,
    must_reset_password boolean NOT NULL DEFAULT true,
    donate              integer NOT NULL DEFAULT 0 CHECK (donate >= 0),
    cargo_gold          bigint NOT NULL DEFAULT 0 CHECK (cargo_gold >= 0),
    legacy_key          text UNIQUE,
    legacy_source       text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Login e case-insensitive: "ANTONIO" e "antonio" sao a mesma conta.
CREATE UNIQUE INDEX accounts_login_canonical_uq ON accounts (lower(login));

COMMENT ON COLUMN accounts.password_hash IS
    'Hash PHC (argon2id) ou pbkdf2-sha256. Texto plano nunca e persistido.';
COMMENT ON COLUMN accounts.numeric_token_hash IS
    'PIN de 6 digitos com hash. Campo legado era texto plano.';
COMMENT ON COLUMN accounts.cargo_gold IS
    'STRUCT_ACCOUNTFILE.Coin (gold do cargo).';
COMMENT ON COLUMN accounts.must_reset_password IS
    'Contas migradas entram com reset obrigatorio por padrao.';

-- ---------------------------------------------------------------------------
-- Personagens
-- ---------------------------------------------------------------------------

CREATE TABLE characters (
    id                    uuid PRIMARY KEY,
    account_id            uuid NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
    slot                  smallint NOT NULL CHECK (slot BETWEEN 0 AND 3),
    name                  text NOT NULL CHECK (length(name) BETWEEN 1 AND 16),
    class                 smallint NOT NULL CHECK (class BETWEEN 0 AND 3),
    class_master          smallint NOT NULL DEFAULT 2
                          CHECK (class_master BETWEEN 0 AND 5),
    clan                  smallint NOT NULL DEFAULT 0 CHECK (clan BETWEEN 0 AND 255),
    citizen               smallint NOT NULL DEFAULT 0 CHECK (citizen BETWEEN 0 AND 255),
    guild_legacy_id       integer CHECK (guild_legacy_id BETWEEN 0 AND 65535),
    guild_level           smallint NOT NULL DEFAULT 0 CHECK (guild_level BETWEEN 0 AND 255),
    level                 integer NOT NULL CHECK (level BETWEEN 0 AND 999),
    exp                   bigint NOT NULL CHECK (exp >= 0),
    gold                  bigint NOT NULL CHECK (gold >= 0),
    spx                   integer,
    spy                   integer,
    fame                  integer NOT NULL DEFAULT 0 CHECK (fame >= 0),
    soul                  smallint NOT NULL DEFAULT 0 CHECK (soul BETWEEN 0 AND 255),
    arch_level            smallint NOT NULL DEFAULT 0 CHECK (arch_level BETWEEN 0 AND 255),
    celestial_level       smallint NOT NULL DEFAULT 0,
    sub_celestial_level   smallint NOT NULL DEFAULT 0,
    celestial_reset       smallint NOT NULL DEFAULT 0 CHECK (celestial_reset >= 0),
    arch_cristal          smallint NOT NULL DEFAULT 0 CHECK (arch_cristal >= 0),
    mortal_level          smallint NOT NULL DEFAULT 0 CHECK (mortal_level >= 0),

    base_ac               integer NOT NULL DEFAULT 0,
    base_damage           integer NOT NULL DEFAULT 0,
    base_max_hp           integer NOT NULL DEFAULT 0,
    base_max_mp           integer NOT NULL DEFAULT 0,
    base_hp               integer NOT NULL DEFAULT 0,
    base_mp               integer NOT NULL DEFAULT 0,
    base_str              smallint NOT NULL DEFAULT 0,
    base_int              smallint NOT NULL DEFAULT 0,
    base_dex              smallint NOT NULL DEFAULT 0,
    base_con              smallint NOT NULL DEFAULT 0,

    current_ac            integer NOT NULL DEFAULT 0,
    current_damage        integer NOT NULL DEFAULT 0,
    current_max_hp        integer NOT NULL DEFAULT 0,
    current_max_mp        integer NOT NULL DEFAULT 0,
    current_hp            integer NOT NULL DEFAULT 0,
    current_mp            integer NOT NULL DEFAULT 0,
    current_str           smallint NOT NULL DEFAULT 0,
    current_int           smallint NOT NULL DEFAULT 0,
    current_dex           smallint NOT NULL DEFAULT 0,
    current_con           smallint NOT NULL DEFAULT 0,
    current_special       smallint[] NOT NULL DEFAULT '{}',

    learned_skill         bigint NOT NULL DEFAULT 0
                          CHECK (learned_skill BETWEEN 0 AND 4294967295),
    magic                 integer NOT NULL DEFAULT 0 CHECK (magic >= 0),
    score_bonus           integer NOT NULL DEFAULT 0 CHECK (score_bonus >= 0),
    special_bonus         integer NOT NULL DEFAULT 0 CHECK (special_bonus >= 0),
    skill_bonus           integer NOT NULL DEFAULT 0 CHECK (skill_bonus >= 0),
    critical              smallint NOT NULL DEFAULT 0 CHECK (critical >= 0),
    save_mana             smallint NOT NULL DEFAULT 0 CHECK (save_mana >= 0),
    skill_bar             smallint[] NOT NULL DEFAULT '{}',
    short_skills          smallint[] NOT NULL DEFAULT '{}',
    regen_hp              smallint NOT NULL DEFAULT 0,
    regen_mp              smallint NOT NULL DEFAULT 0,
    resist                smallint[] NOT NULL DEFAULT '{}',
    merchant              smallint NOT NULL DEFAULT 0,
    quest                 smallint NOT NULL DEFAULT 0,
    rsv                   integer NOT NULL DEFAULT 0,

    direction             smallint NOT NULL DEFAULT 0,
    chaos_rate            smallint NOT NULL DEFAULT 0,
    attack_run            smallint NOT NULL DEFAULT 0,

    raw_base_score        jsonb NOT NULL DEFAULT '{}'::jsonb,
    raw_current_score     jsonb NOT NULL DEFAULT '{}'::jsonb,
    raw_mobextra          bytea,

    legacy_key            text UNIQUE,
    legacy_source         text,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT characters_account_slot_uq UNIQUE (account_id, slot),
    CONSTRAINT characters_skill_bar_len CHECK (cardinality(skill_bar) IN (0, 4)),
    CONSTRAINT characters_short_skills_len CHECK (cardinality(short_skills) IN (0, 16)),
    CONSTRAINT characters_resist_len CHECK (cardinality(resist) IN (0, 4)),
    CONSTRAINT characters_current_special_len CHECK (cardinality(current_special) IN (0, 4))
);

CREATE UNIQUE INDEX characters_name_canonical_uq ON characters (lower(name));
CREATE INDEX characters_account_idx ON characters (account_id);
CREATE INDEX characters_level_idx ON characters (level DESC, exp DESC);

COMMENT ON COLUMN characters.class IS '0=TK, 1=FM, 2=BM, 3=HT (STRUCT_MOB.Class).';
COMMENT ON COLUMN characters.class_master IS
    'Tier: 0=desconhecido, 1=ARCH, 2=MORTAL, 3=CELESTIAL, 4=CELESTIALCS, 5=SCELESTIAL (STRUCT_MOBEXTRA.ClassMaster).';
COMMENT ON COLUMN characters.level IS
    'STRUCT_SCORE.Level. A tabela Mortal/Arch vai ate 596; nao limitar a 399.';
COMMENT ON COLUMN characters.current_special IS
    'STRUCT_SCORE.Special[4] corrente (raw preservado em raw_current_score).';
COMMENT ON COLUMN characters.raw_base_score IS
    'STRUCT_SCORE BaseScore completo, para fidelidade de migracao.';
COMMENT ON COLUMN characters.raw_mobextra IS
    'STRUCT_MOBEXTRA cru (552 bytes), para auditoria dos campos nao modelados.';
COMMENT ON COLUMN characters.exp IS
    'long long legado. Pode passar de INT32_MAX; usar bigint.';

-- ---------------------------------------------------------------------------
-- Afetos persistidos (STRUCT_AFFECT[32] por personagem)
-- ---------------------------------------------------------------------------

CREATE TABLE character_affects (
    character_id  uuid NOT NULL REFERENCES characters (id) ON DELETE CASCADE,
    slot          smallint NOT NULL CHECK (slot BETWEEN 0 AND 31),
    type          smallint NOT NULL CHECK (type BETWEEN 0 AND 255),
    value         smallint NOT NULL CHECK (value BETWEEN 0 AND 255),
    level         integer NOT NULL CHECK (level >= 0),
    time_value    bigint NOT NULL CHECK (time_value >= 0),
    PRIMARY KEY (character_id, slot)
);

COMMENT ON COLUMN character_affects.time_value IS
    'STRUCT_AFFECT.Time cru (tick/duracao do legado), nao convertido para timestamp.';

-- ---------------------------------------------------------------------------
-- Itens
-- ---------------------------------------------------------------------------

CREATE TABLE items (
    id                  uuid PRIMARY KEY,
    owner_account_id    uuid REFERENCES accounts (id) ON DELETE CASCADE,
    owner_character_id  uuid REFERENCES characters (id) ON DELETE CASCADE,
    container           item_container NOT NULL,
    slot                smallint NOT NULL CHECK (slot >= 0),
    item_index          integer NOT NULL CHECK (item_index > 0),
    refine              smallint NOT NULL DEFAULT 0 CHECK (refine BETWEEN 0 AND 15),
    gem                 smallint CHECK (gem BETWEEN 0 AND 3),

    effect_0_type       smallint NOT NULL CHECK (effect_0_type BETWEEN 0 AND 255),
    effect_0_value      smallint NOT NULL CHECK (effect_0_value BETWEEN 0 AND 255),
    effect_1_type       smallint NOT NULL CHECK (effect_1_type BETWEEN 0 AND 255),
    effect_1_value      smallint NOT NULL CHECK (effect_1_value BETWEEN 0 AND 255),
    effect_2_type       smallint NOT NULL CHECK (effect_2_type BETWEEN 0 AND 255),
    effect_2_value      smallint NOT NULL CHECK (effect_2_value BETWEEN 0 AND 255),

    legacy_key          text UNIQUE,
    legacy_source       text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT items_owner_exactly_one
        CHECK (num_nonnulls(owner_account_id, owner_character_id) = 1),
    CONSTRAINT items_cargo_owner
        CHECK ((container = 'cargo' AND owner_account_id IS NOT NULL)
            OR (container <> 'cargo' AND owner_character_id IS NOT NULL)),
    CONSTRAINT items_slot_in_container
        CHECK (slot < CASE container
                        WHEN 'equip' THEN 16
                        WHEN 'carry' THEN 64
                        WHEN 'cargo' THEN 128
                      END),
    CONSTRAINT items_gem_consistency
        CHECK ((refine < 10 AND gem IS NULL) OR (refine >= 10 AND gem IS NOT NULL))
);

-- Anti-dupe estrutural: um unico item por posicao.
CREATE UNIQUE INDEX items_character_slot_uq
    ON items (owner_character_id, container, slot)
    WHERE owner_character_id IS NOT NULL;

CREATE UNIQUE INDEX items_account_slot_uq
    ON items (owner_account_id, container, slot)
    WHERE owner_account_id IS NOT NULL;

CREATE INDEX items_item_index_idx ON items (item_index);
CREATE INDEX items_owner_character_idx ON items (owner_character_id);

COMMENT ON COLUMN items.id IS
    'UUID imutavel da instancia. Gerado por UUIDv5 sobre a origem legada.';
COMMENT ON COLUMN items.refine IS
    'Nivel 0..15 decodificado de EF_SANC (43) ou 116..125.';
COMMENT ON COLUMN items.gem IS
    'Tipo de joia 0..3 para refino 10..15; NULL abaixo de +10.';
COMMENT ON COLUMN items.effect_0_type IS
    'Par EF_* cru. Preservado para fidelidade e futura re-derivacao.';

-- ---------------------------------------------------------------------------
-- Ledger de itens (append-only)
-- ---------------------------------------------------------------------------

CREATE TABLE item_ledger (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id             uuid NOT NULL,
    action              ledger_reason NOT NULL,
    from_character_id   uuid,
    to_character_id     uuid,
    from_container      item_container,
    to_container        item_container,
    from_slot           smallint,
    to_slot             smallint,
    actor               text NOT NULL DEFAULT 'importer',
    correlation_id      uuid NOT NULL,
    detail              jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),

    -- Idempotencia: o mesmo evento nao pode ser aplicado duas vezes.
    CONSTRAINT item_ledger_event_uq UNIQUE (item_id, action, correlation_id)
);

CREATE INDEX item_ledger_item_idx ON item_ledger (item_id, created_at);
CREATE INDEX item_ledger_correlation_idx ON item_ledger (correlation_id);

COMMENT ON TABLE item_ledger IS
    'Registro imutavel de toda mudanca de posse/posicao de item. Sem FK para items porque o historico sobrevive ao item.';

CREATE FUNCTION forbid_ledger_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'item_ledger e append-only (tentativa de %)', TG_OP
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE TRIGGER item_ledger_no_update
    BEFORE UPDATE ON item_ledger
    FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation();

CREATE TRIGGER item_ledger_no_delete
    BEFORE DELETE ON item_ledger
    FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation();

CREATE TRIGGER item_ledger_no_truncate
    BEFORE TRUNCATE ON item_ledger
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_ledger_mutation();

-- ---------------------------------------------------------------------------
-- Importacao e reconciliacao
-- ---------------------------------------------------------------------------

CREATE TABLE import_runs (
    id              uuid PRIMARY KEY,
    started_at      timestamptz NOT NULL,
    finished_at     timestamptz,
    mode            import_mode NOT NULL,
    status          import_status NOT NULL DEFAULT 'running',
    tool_version    text NOT NULL,
    source_path     text NOT NULL,
    schema_version  text NOT NULL,
    manifest_sha256 text NOT NULL CHECK (length(manifest_sha256) = 64),
    totals          jsonb NOT NULL DEFAULT '{}'::jsonb,
    report          jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE import_issues (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id         uuid NOT NULL REFERENCES import_runs (id) ON DELETE CASCADE,
    severity       text NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    code           text NOT NULL,
    account_login  text,
    legacy_path    text,
    detail         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT import_issues_natural_uq
        UNIQUE NULLS NOT DISTINCT (run_id, code, account_login, legacy_path)
);

CREATE INDEX import_issues_run_idx ON import_issues (run_id, severity);

-- ---------------------------------------------------------------------------
-- updated_at
-- ---------------------------------------------------------------------------

CREATE FUNCTION touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER accounts_touch BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER characters_touch BEFORE UPDATE ON characters
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER items_touch BEFORE UPDATE ON items
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ---------------------------------------------------------------------------
-- Views de reconciliacao
-- ---------------------------------------------------------------------------

CREATE VIEW character_item_counts AS
SELECT
    c.id                                        AS character_id,
    a.login,
    c.name,
    c.level,
    count(i.id) FILTER (WHERE i.container = 'equip') AS equip_items,
    count(i.id) FILTER (WHERE i.container = 'carry') AS carry_items,
    count(i.id)                                 AS total_items,
    c.gold
FROM characters c
JOIN accounts a ON a.id = c.account_id
LEFT JOIN items i ON i.owner_character_id = c.id
GROUP BY c.id, a.login, c.name, c.level, c.gold;

CREATE VIEW account_item_totals AS
SELECT
    a.id AS account_id,
    a.login,
    (SELECT count(*) FROM characters c WHERE c.account_id = a.id) AS characters,
    (SELECT count(*) FROM items i WHERE i.owner_account_id = a.id) AS cargo_items,
    (SELECT count(*) FROM items i
      WHERE i.owner_account_id = a.id
         OR i.owner_character_id IN (SELECT c.id FROM characters c WHERE c.account_id = a.id))
                                                                   AS total_items,
    a.cargo_gold
FROM accounts a;

COMMENT ON VIEW character_item_counts IS
    'Contagem por personagem para reconciliar importacao (equip<=16, carry<=64).';
COMMENT ON VIEW account_item_totals IS
    'Contagem por conta, incluindo o cargo compartilhado (<=128).';

COMMIT;
