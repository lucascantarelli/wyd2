-- =============================================================================
-- WYD Next-Gen -- Fase 3: catalogo do cliente (itens e skills)
--
-- Alvo: PostgreSQL 16+. Aplicar DEPOIS de 001_init.sql:
--     psql -d wyd -f schema/001_init.sql
--     psql -d wyd -f schema/002_catalog.sql
--
-- Conteudo: o que o cliente WYD Global distribui em ItemList.bin e
-- SkillData.bin, decodificado por importer/client_tables.py.
-- Layout medido: docs/03-DADOS-LEGADOS.md §6.7.
--
-- Decisoes:
--  * `catalog` e dado de REFERENCIA, separado de `wyd` (estado do jogador).
--  * A identidade do item e o `item_index` do cliente (nao UUID: UUID e para
--    instancia, em `wyd.items`).
--  * Efeitos ficam normalizados para permitir consulta ("quais itens tem
--    EF_SANC?"), mas so as posicoes preenchidas: o sentinela (255,0) do
--    arquivo nao e dado.
--  * A carga e idempotente e reflete o cliente inteiro: linhas que sumiram do
--    arquivo somem do catalogo (ver load_catalog.sql).
--  * As views de reconciliacao dependem de `wyd.items`; por isso a ordem de
--    aplicacao acima e obrigatoria.
-- =============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS catalog;
SET LOCAL search_path TO catalog, wyd, public;

-- ---------------------------------------------------------------------------
-- Procedencia da carga
-- ---------------------------------------------------------------------------

CREATE TABLE catalog.load_runs (
    id              uuid PRIMARY KEY,
    loaded_at       timestamptz NOT NULL DEFAULT now(),
    client_dir      text NOT NULL,
    skill_sha256    text NOT NULL CHECK (length(skill_sha256) = 64),
    item_sha256     text NOT NULL CHECK (length(item_sha256) = 64),
    skill_records   integer NOT NULL CHECK (skill_records >= 0),
    item_records    integer NOT NULL CHECK (item_records >= 0),
    skill_trailer   bigint NOT NULL,
    item_trailer    bigint NOT NULL,
    tool_version    text NOT NULL
);

COMMENT ON TABLE catalog.load_runs IS
    'Uma linha por pacote de catalogo carregado. Os trailers sao os int32 crus do fim dos .bin.';

-- ---------------------------------------------------------------------------
-- Itens
-- ---------------------------------------------------------------------------

CREATE TABLE catalog.items (
    item_index      integer PRIMARY KEY CHECK (item_index > 0),
    name            text NOT NULL CHECK (name <> ''),
    mesh            smallint NOT NULL CHECK (mesh >= -1),
    texture         smallint NOT NULL DEFAULT 0,
    visual_effect   smallint NOT NULL DEFAULT 0,
    req_level       smallint NOT NULL DEFAULT 0 CHECK (req_level >= 0),
    req_str         smallint NOT NULL DEFAULT 0 CHECK (req_str >= 0),
    req_int         smallint NOT NULL DEFAULT 0 CHECK (req_int >= 0),
    req_dex         smallint NOT NULL DEFAULT 0 CHECK (req_dex >= 0),
    req_con         smallint NOT NULL DEFAULT 0 CHECK (req_con >= 0),
    price           bigint NOT NULL DEFAULT 0 CHECK (price >= 0),
    position        integer NOT NULL DEFAULT 0 CHECK (position BETWEEN 0 AND 65535),
    grade           smallint NOT NULL DEFAULT 0 CHECK (grade BETWEEN 0 AND 4),
    unique_id       smallint NOT NULL DEFAULT 0 CHECK (unique_id >= 0),
    extra           smallint NOT NULL DEFAULT 0,
    canonical_id    integer,
    source_file     text NOT NULL DEFAULT 'ItemList.bin',
    source_offset   integer NOT NULL CHECK (source_offset >= 0),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN catalog.items.mesh IS
    'IndexMesh do cliente. -1 (0xFFFF) e um valor real observado, nao ausencia.';
COMMENT ON COLUMN catalog.items.position IS
    'nPos: bitmask dos 16 slots de equipamento. 0 = nao equipavel.';
COMMENT ON COLUMN catalog.items.canonical_id IS
    'Id canonico da extensao (+168). Igual ao item_index na maioria; nas variantes aponta para o primeiro item de mesmo nome.';
COMMENT ON COLUMN catalog.items.source_offset IS
    'Offset do registro em ItemList.bin, para auditar qualquer linha contra o arquivo.';

CREATE INDEX catalog_items_position_idx ON catalog.items (position);
CREATE INDEX catalog_items_canonical_idx ON catalog.items (canonical_id);

CREATE TABLE catalog.item_effects (
    item_index      integer NOT NULL REFERENCES catalog.items (item_index) ON DELETE CASCADE,
    slot            smallint NOT NULL CHECK (slot BETWEEN 0 AND 11),
    effect          smallint NOT NULL CHECK (effect BETWEEN 1 AND 254),
    -- sValue e um short cru: neste cliente vai de 0 a 2000 (nao e 0..255).
    value           smallint NOT NULL CHECK (value BETWEEN -32768 AND 32767),
    PRIMARY KEY (item_index, slot)
);

COMMENT ON TABLE catalog.item_effects IS
    'Pares (EF_*, valor) do item. Somente posicoes preenchidas; (255,0) e sentinela e nao e armazenado.';

CREATE INDEX catalog_item_effects_effect_idx ON catalog.item_effects (effect, value);

-- ---------------------------------------------------------------------------
-- Skills
-- ---------------------------------------------------------------------------

CREATE TABLE catalog.skills (
    slot                smallint PRIMARY KEY CHECK (slot >= 0),
    skill_id            integer NOT NULL DEFAULT 0 CHECK (skill_id >= 0),
    skill_point         integer NOT NULL DEFAULT 0 CHECK (skill_point >= 0),
    target_type         integer NOT NULL DEFAULT 0,
    mana                integer NOT NULL DEFAULT 0 CHECK (mana >= 0),
    delay               integer NOT NULL DEFAULT 0 CHECK (delay >= 0),
    range               integer NOT NULL DEFAULT 0 CHECK (range >= 0),
    instance_type       integer NOT NULL DEFAULT 0,
    instance_value      integer NOT NULL DEFAULT 0,
    tick_type           integer NOT NULL DEFAULT 0,
    tick_value          integer NOT NULL DEFAULT 0,
    affect_type         integer NOT NULL DEFAULT 0,
    affect_value        integer NOT NULL DEFAULT 0,
    affect_time         integer NOT NULL DEFAULT 0,
    instance_attribute  bytea NOT NULL CHECK (length(instance_attribute) = 8),
    tick_attribute      bytea NOT NULL CHECK (length(tick_attribute) = 8),
    tail_values         smallint[] NOT NULL CHECK (array_length(tail_values, 1) = 8),
    flag                smallint NOT NULL CHECK (flag IN (0, 1)),
    source_offset       integer NOT NULL CHECK (source_offset >= 0),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE catalog.skills IS
    'Registros de SkillData.bin por posicao (slot). skill_id = 0 significa slot nao usado; por isso a PK e o slot.';
COMMENT ON COLUMN catalog.skills.tail_values IS
    'Os 8 ints de +64..+92, cuja semantica ainda nao foi identificada. Preservados crus.';

CREATE UNIQUE INDEX catalog_skills_id_uq
    ON catalog.skills (skill_id)
    WHERE skill_id > 0;

-- ---------------------------------------------------------------------------
-- Reconciliacao com o que o gateway serializa
--
-- O gateway (gateway/src/postgres_directory.rs) le `wyd.items` e escreve o
-- `item_index` em um campo int16 (narrow_i16). Logo:
--   * item_index usado sem linha em catalog.items = item sem nome/atributos;
--   * item_index > 32767 nao cabe no campo e o gateway recusa a sessao.
-- ---------------------------------------------------------------------------

CREATE VIEW catalog.item_usage AS
SELECT i.item_index, count(*) AS instances
FROM wyd.items i
GROUP BY i.item_index;

CREATE VIEW catalog.missing_items AS
SELECT usage.item_index, usage.instances
FROM catalog.item_usage usage
LEFT JOIN catalog.items item ON item.item_index = usage.item_index
WHERE item.item_index IS NULL;

CREATE VIEW catalog.out_of_range_items AS
SELECT usage.item_index, usage.instances
FROM catalog.item_usage usage
WHERE usage.item_index > 32767;

CREATE VIEW catalog.coverage AS
SELECT
    (SELECT count(*) FROM catalog.items)        AS catalog_items,
    (SELECT count(*) FROM catalog.item_effects) AS catalog_effects,
    (SELECT count(*) FROM catalog.skills)       AS catalog_skills,
    (SELECT count(*) FROM catalog.item_usage)   AS used_indexes,
    (SELECT count(*) FROM wyd.items)            AS item_instances,
    (SELECT count(*) FROM catalog.missing_items) AS missing_indexes,
    (SELECT count(*) FROM catalog.out_of_range_items) AS out_of_range_indexes;

COMMENT ON VIEW catalog.coverage IS
    'Uma linha com o placar do catalogo. missing_indexes e out_of_range_indexes devem ser 0 antes do go-live.';

COMMIT;
