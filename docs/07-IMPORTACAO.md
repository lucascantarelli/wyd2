# 07 — Importação de Contas Legadas

> **Escopo:** como transformar `STRUCT_ACCOUNTFILE` em dados PostgreSQL, com UUID por item, ledger append-only e relatório de reconciliação.
>
> **Fonte:** [schema/001_init.sql](../schema/001_init.sql), [importer/](../importer), [tests/](../tests). Layout derivado de `Basedef.h` e de [03-DADOS-LEGADOS.md](03-DADOS-LEGADOS.md).
>
> **Legenda:** ✅ implementado e testado · 🟡 implementado com limite conhecido · ⚠️ fora do escopo desta fase · 🔴 bloqueante

---

## 1. O que existe agora

| Componente | Caminho | Estado |
|---|---|---|
| Schema PostgreSQL 16 | [schema/001_init.sql](../schema/001_init.sql) | ✅ UUID, ledger, triggers, views |
| Decoder binário | [importer/decode.py](../importer/decode.py) | ✅ 7952; 7500–7600 opt-in (`--allow-padded-legacy`); 4294 recusado |
| Modelo de domínio | [importer/model.py](../importer/model.py) | ✅ scores, itens, afetos, `MOBEXTRA` |
| Refino empacotado | [importer/refine.py](../importer/refine.py) | ✅ `EF_SANC` → nível/gema/pity |
| Hash de senha/PIN | [importer/hashing.py](../importer/hashing.py) | ✅ argon2id; fallback PBKDF2 |
| Identidade determinística | [importer/ids.py](../importer/ids.py) | ✅ UUIDv5 |
| Reconciliação | [importer/reconcile.py](../importer/reconcile.py) | ✅ erros, avisos e checks |
| Pacote de carga | [importer/emit.py](../importer/emit.py) | ✅ CSV, JSONL, `load.sql` |
| CLI | [importer/\_\_main\_\_.py](../importer/__main__.py) | ✅ dry-run e `--emit` |
| Testes | [tests/](../tests) | ✅ 82 testes |

O conversor é **one-shot**: ele lê um dump, produz um pacote auditável e carrega em um banco limpo. Ele não é um sincronizador contínuo.

---

## 2. Pré-requisitos

- **Python 3.11+** (testado em 3.14).
- **PostgreSQL 16+** para executar `schema/001_init.sql` e `load.sql`.
- **argon2-cffi** (recomendado):

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# .venv/bin/pip install -r requirements.txt     # Linux/macOS
```

Sem `argon2-cffi`, o importador usa PBKDF2-HMAC-SHA256 com 600.000 iterações. O algoritmo fica gravado em `accounts.password_algo`, então é possível rehashar depois. Em produção, argon2id é o alvo.

---

## 3. Como executar

### 3.1. Dry-run (padrão)

```bash
python -m importer --source legacy/accounts --report out/report.json
python scripts/review_report.py out/report.json --markdown out/review.md
```

Lê, decodifica e reconcilia. **Não grava pacote.** O relatório mostra contas, personagens, itens, ouro, EXP, avisos e erros. O código de saída é `1` se houver erro de severidade `error`.

Aponte `--source` para um diretório que contenha **apenas** arquivos de conta (ou use um arquivo isolado). Qualquer outro arquivo de tamanho desconhecido vira `unknown_account_size` e bloqueia o `load.sql`; arquivos ocultos são ignorados.

Se o dump tiver contas de **7500–7600 bytes**, use `--allow-padded-legacy`. O importador faz zero-padding até 7952 (o mesmo comportamento do DBSrv antigo) e emite o aviso `legacy_account_zero_padded`; campos após o corte — `Donate`, `IsBlocked` e o fim de `mobExtra` — podem estar zerados. Contas de **4294 bytes** continuam recusadas.

### 3.2. Gerar o pacote

```bash
python -m importer \
  --source legacy/accounts \
  --catalog legacy/ItemList.csv \
  --emit out \
  --report out/report.json
```

Saídas em `out/`:

| Arquivo | Conteúdo |
|---|---|
| `accounts.csv` | conta, hash de senha, hash do PIN, email, donate, cargo gold |
| `characters.csv` | 4 slots, classe, tier, progressão, scores, arrays, JSON cru |
| `items.csv` | UUID, dono, container/slot, `sIndex`, refino, gema, efeitos |
| `character_affects.csv` | `STRUCT_AFFECT[32]` por personagem |
| `item_ledger.csv` | evento `import` por item |
| `import_runs.csv` / `import_issues.csv` | trilha da importação |
| `records.jsonl` | auditoria legível, **sem hash de senha** |
| `load.sql` | carga idempotente via `psql` |
| `report.json` | reconciliação completa |

Se houver qualquer `error`, o `load.sql` **não** é gerado e `LOAD_BLOCKED.txt` explica o motivo.

### 3.3. Criar o schema e carregar

```bash
psql -d wyd -f schema/001_init.sql
cd out
psql -d wyd -f load.sql
```

`load.sql` usa `\copy`, que resolve os CSV **relativos ao diretório atual**. Execute a partir de `out/`.

Sem PostgreSQL instalado no host, a mesma carga roda em container:

```bash
docker run -d --name wyd-pg16 -e POSTGRES_PASSWORD=wyd -e POSTGRES_DB=wyd postgres:16
docker cp schema wyd-pg16:/schema
docker cp out wyd-pg16:/pkg
docker exec -i wyd-pg16 psql -U postgres -d wyd -v ON_ERROR_STOP=1 -f /schema/001_init.sql
docker exec -w /pkg wyd-pg16 psql -U postgres -d wyd -v ON_ERROR_STOP=1 -f load.sql
```

No Git Bash, prefixe o último comando com `MSYS_NO_PATHCONV=1` para preservar `/pkg`.

### 3.4. Catálogo de itens e skills

São duas coisas diferentes, com comandos diferentes:

**a) Validar `sIndex` contra o `ItemList.csv` do servidor 7662.** `--catalog` lê a primeira coluna do CSV e emite `catalog_missing_item` para cada `sIndex` desconhecido. É aviso, não erro: o item pode ser de cash/evento e não estar no catálogo base.

**b) Importar o catálogo do cliente WYD Global** (o alvo do projeto, [08-CLIENTE-ALVO.md](08-CLIENTE-ALVO.md)). O cliente distribui `ItemList.bin` e `SkillData.bin`; o importador decodifica e gera as tabelas `catalog.*`:

```bash
python -m importer.catalog --client "reference/WYD Global"                      # dry-run
python -m importer.catalog --client "reference/WYD Global" --emit out/catalog     # pacote
psql -d wyd -f schema/002_catalog.sql                                            # uma vez
cd out/catalog && psql -d wyd -f load_catalog.sql                                # idempotente
```

Para reconciliar o catálogo com o que o gateway realmente serializa, aponte `--used-items` para o `items.csv` do pacote de contas:

```bash
python -m importer.catalog --client "reference/WYD Global" \
    --emit out/catalog --used-items out/items.csv --strict
```

Sem `--strict`, item ausente vira aviso no relatório; com `--strict`, o pacote não gera `load_catalog.sql` e escreve `LOAD_BLOCKED.txt`. As mesmas checagens rodam no banco pelas views de `catalog` (§5.5).

---

## 4. Pipeline

```text
1. discover      -> arquivos regulares, ordem estável, ocultos ignorados
2. size detect   -> 7952 aceito; 7500..7600 opt-in (zero-pad); 4294 recusado
3. decode        -> STRUCT_ACCOUNTFILE com alinhamento natural MSVC x86
4. migrate       -> senha/PIN -> hash; PII descartada; UUIDs determinísticos
5. reconcile     -> contagens, nomes, classes, refino, ouro, EXP, catálogo
6. emit          -> CSV + JSONL + load.sql + report.json
7. load          -> staging temporário + ON CONFLICT
```

O passo 4 é o único que vê texto plano. Ele não devolve, não loga e não grava esse texto.

---

## 5. Schema

### 5.1. Tabelas

| Tabela | Papel |
|---|---|
| `accounts` | login canônico, hash de senha/PIN, email, bloqueio, donate, ouro do cargo |
| `characters` | personagem por slot, classe, tier, progressão, scores e campos crus |
| `character_affects` | até 32 afetos por personagem |
| `items` | instância com UUID, dono, container/slot, refino, gema e 3 efeitos |
| `item_ledger` | histórico append-only de posse/posição |
| `import_runs` | uma linha por execução, com manifesto e totais |
| `import_issues` | erros/avisos da execução, deduplicados por chave natural |
| `character_item_counts` | view de conferência por personagem |
| `account_item_totals` | view de conferência por conta |

O catálogo do cliente fica em **outro schema** (`schema/002_catalog.sql`), porque é dado de referência e não estado de jogador:

| Tabela | Papel |
|---|---|
| `catalog.items` | item por `item_index`: nome, mesh/textura, requisitos, preço, `nPos`, grade, id canônico |
| `catalog.item_effects` | pares `(EF_*, valor)` por item — só posições preenchidas, sem o sentinela `(255,0)` |
| `catalog.skills` | registro de skill por slot, com `skill_id` (0 = slot vazio), atributos crus e cauda desconhecida preservada |
| `catalog.load_runs` | procedência: SHA-256 dos dois `.bin`, trailers, contagens |
| `catalog.coverage` | view: itens, efeitos, skills, índices usados, ausentes e fora do `int16` |
| `catalog.missing_items` | view: `item_index` usado em `wyd.items` sem linha no catálogo |
| `catalog.out_of_range_items` | view: `item_index` > 32767 (o gateway escreve o índice em `int16`) |

### 5.2. Identidade

O namespace UUID é fixo em [importer/ids.py](../importer/ids.py). As chaves são:

```text
account:{login canônico}
account:{login canônico}#slot:{0..3}
account:{login canônico}#char:{slot}:{equip|carry}:{slot}
account:{login canônico}#cargo:{slot}
```

Consequências:

- Reimportar o **mesmo** dump produz os mesmos UUIDs, então `ON CONFLICT` atualiza em vez de duplicar.
- Mudar o namespace quebra a idempotência e cria linhas novas. Não mude sem migração explícita.
- `sIndex` nunca é identidade de instância. Dois itens iguais têm UUIDs diferentes.

### 5.3. Ledger

`item_ledger` é append-only por trigger: `UPDATE`, `DELETE` e `TRUNCATE` falham. O ledger **não** tem FK para `items` de propósito: o histórico sobrevive ao item.

Cada item importado gera:

```text
action = import
to_container / to_slot = posição no dump
to_character_id = personagem, ou NULL para cargo
correlation_id = run_id
detail = { source, legacy_key }
```

A chave única `(item_id, action, correlation_id)` torna a carga repetível.

### 5.4. Refino

O efeito `EF_SANC` (43), ou a faixa 116–125, guarda o refino empacotado:

```text
cValue 0..9       -> nível = cValue,       pity = 0
cValue 10..229    -> nível = cValue % 10,  pity = cValue // 10
cValue 230..253   -> nível = 10 + (cValue - 230) // 4, gema = (cValue - 230) % 4
```

`items.refine` e `items.gem` são derivados; os três pares de efeito crus são preservados para re-derivação. Itens com refino fora de 0..15 ou pity > 20 geram aviso `refine_out_of_range`.

### 5.5. Reconciliação do catálogo

O gateway não envia nome nem atributos de item: em `SelChar` ele manda só o `item_index`, o refino e os três pares de efeito (`WireItem`, em `gateway/src/postgres_directory.rs`), e é o cliente que resolve esse índice no catálogo local. Logo, o que importa é: **todo `item_index` gravado em `wyd.items` existe no catálogo e cabe no `int16` do protocolo** — se não existir, o cliente mostra o item errado (ou nada); se não couber, o gateway recusa a sessão inteira. Estas consultas respondem isso:

```sql
-- 1. Deve retornar zero linhas.
SELECT * FROM catalog.missing_items;
SELECT * FROM catalog.out_of_range_items;

-- 2. Placar único.
SELECT * FROM catalog.coverage;

-- 3. Quais itens do catálogo ninguém usa (catálogo maior que o dump).
SELECT i.item_index, i.name
FROM catalog.items i
LEFT JOIN catalog.item_usage u ON u.item_index = i.item_index
WHERE u.item_index IS NULL
ORDER BY i.item_index;

-- 4. Efeito mais comum — sanidade do decodificador.
SELECT effect, count(*) AS itens
FROM catalog.item_effects
GROUP BY effect
ORDER BY itens DESC
LIMIT 10;
```

`out_of_range_items` existe porque `load_item` aplica `narrow_i16` (e rejeita índice `<= 0`) em `gateway/src/postgres_directory.rs`: um índice acima de 32767 não falha na carga do catálogo, falha na sessão do jogador. O importador de contas já grava `items.item_index` como `integer`, então a checagem tem de acontecer aqui — depois da carga, antes do go-live.

As views não são só diagnóstico: o gateway aplica a mesma regra ao carregar a conta. `EQUIP_SQL` e `CARGO_SQL` trazem `EXISTS (SELECT 1 FROM catalog.items ...) AS catalog_known`, e um item ausente vira erro de diretório com o índice e o container no log do operador (`item de equip com item_index 9999 nao existe em catalog.items...`). O cliente recebe o painel genérico de serviço indisponível e a sessão não abre — melhor do que mandar um índice que ele não sabe resolver. Sem o schema `catalog`, o gateway falha no boot, ao preparar as consultas.

---

## 6. Regras de conversão

| Legado | Novo | Observação |
|---|---|---|
| `Info.AccountName` | `accounts.login` | `strip()` + lower para o índice canônico; o valor original é preservado |
| `Info.AccountPass` | `accounts.password_hash` | argon2id ou PBKDF2; nunca texto plano |
| `Info.NumericToken` | `accounts.numeric_token_hash` | hash; PIN vazio vira `NULL` |
| `Info.Email` | `accounts.email` | PII mantida para recuperação de conta |
| `Info.RealName`, `SSN1/2`, `Telephone`, `Address` | — | **descartados** (retenção mínima/LGPD) |
| `Char[0..3]` | `characters.slot` | slot vazio não gera linha |
| `Char[].Equip[16]` | `items(container='equip')` | `sIndex == 0` é slot vazio |
| `Char[].Carry[64]` | `items(container='carry')` | |
| `Cargo[128]` | `items(container='cargo')` | dono é a conta, não o personagem |
| `Char[].Coin` | `characters.gold` | |
| `Cargo Coin` | `accounts.cargo_gold` | |
| `Char[].Exp` | `characters.exp` | `bigint`; o legado usa 64 bits |
| `affect[4][32]` | `character_affects` | `time_value` é o tick cru |
| `mobExtra[4].ClassMaster` | `characters.class_master` | 1..5; 0 vira `desconhecido` |
| `mobExtra[4].QuestInfo` | colunas de progressão | Mortal/Arch/Celestial/Reset/Cristal |
| `IsBlocked` | `accounts.blocked` | |
| `Donate` | `accounts.donate` | |

### 6.1. O que é preservado cru

`characters.raw_base_score`, `raw_current_score` e `raw_mobextra` guardam o conteúdo original (JSON/bytea). Isso permite auditar campos que o schema ainda não modela, especialmente `SaveCelestial`, `NT`, `KefraTicket` e as flags de quest.

---

## 7. Relatório de reconciliação

`report.json` responde:

1. **Inventário:** todo arquivo foi decodificado, recusado ou ignorado?
2. **Contagens:** contas, personagens, equip/carry/cargo, ouro e EXP batem com a soma do dump?
3. **Aceitação:** o banco vai recusar alguma linha (nome duplicado, classe inválida, refino, etc.)?

### 7.1. Erros (bloqueiam `load.sql`)

| Código | Quando |
|---|---|
| `unknown_account_size` | tamanho não reconhecido |
| `unsupported_account_version` | 4294, ou 7500–7600 sem `--allow-padded-legacy` |
| `decode_error` | bytes insuficientes/estrutura inválida |
| `duplicate_account_login` | dois arquivos com o mesmo login canônico |
| `account_login_present` | login vazio |
| `character_name_empty` | personagem sem nome |
| `duplicate_character_name_in_account` | mesmo nome no mesmo arquivo |
| `duplicate_character_name_global` | mesmo nome em outra conta |
| `character_class_invalid` | classe fora de 0..3 |
| `class_master_invalid` | tier fora de 0..5 |
| `character_level_out_of_range` | nível fora de 0..999 |
| `arch_level_out_of_range` | ArchLevel fora de 0..255 |
| `celestial_level_negative` / `fame_negative` | campos que o schema recusaria |
| `character_gold_negative` / `character_exp_negative` | valores negativos |
| `cargo_gold_negative` / `donate_negative` | valores negativos |

### 7.2. Avisos (não bloqueiam)

`empty_password`, `account_without_characters`, `refine_out_of_range`, `catalog_missing_item`, `legacy_account_zero_padded`, entre outros. Avisos aparecem em `report.checks` e `import_issues`.

### 7.3. Checks do pacote

`write_package` verifica o próprio resultado antes de liberar `load.sql`:

- contagens de contas/personagens/itens/afetos;
- ledger cobre todos os itens;
- ouro e EXP reconciliados;
- hash de senha e PIN presentes;
- nenhuma senha em claro nos arquivos gerados;
- JSONL sem `password_hash`;
- `load.sql` com `BEGIN`/`COMMIT` e `ON CONFLICT`.

Se um check falhar, o `load.sql` é removido e `LOAD_BLOCKED.txt` é gravado.

### 7.4. Revisão automatizada

```bash
python scripts/review_report.py out/report.json --markdown out/review.md
```

O revisor confere a aritmética do relatório (arquivos vistos/decodificados/pulados, somas de personagens/itens), limites por container, contas sem personagem, códigos de issue e checks do pacote. Sai com `1` quando o relatório está bloqueado; `0` quando está apto. `--markdown` grava a revisão para anexar ao processo de migração.

---

## 8. Segurança

- Texto plano de senha/PIN existe apenas em memória, dentro de `migrate_account`; o `MigratedAccount` não o expõe.
- `out/` está no `.gitignore`: o pacote contém hashes e dados de conta.
- `report.json` e `records.jsonl` não contêm hash nem senha.
- Contas migradas entram com `must_reset_password = true`; o gateway ainda **não aplica** esse flag porque não existe fluxo de troca de senha (ver `gateway/README.md`).
- O gateway verifica os mesmos formatos argon2id/PBKDF2 com as crates `argon2`/`pbkdf2`, rejeita algoritmo desconhecido e nunca registra senha nem hash.
- PII forte (SSN, endereço, telefone, nome real) não é persistida.
- O `load.sql` não é seguro para versionar nem para compartilhar.

---

## 9. Idempotência e limites

### 9.1. O que é idempotente

O mesmo dump, com o mesmo manifesto, gera o mesmo `run_id`, os mesmos UUIDs e o mesmo ledger. Rodar `load.sql` duas vezes atualiza as linhas e não duplica o ledger.

### 9.2. O que não é

- **Dump diferente no mesmo banco:** o importador faz upsert, mas não remove itens/personagens que desapareceram do dump. Isso evita apagar dados por engano, mas deixa estado obsoleto. A recomendação é carregar em banco/schema limpo.
- **Contas de 7500–7600:** só são aceitas com `--allow-padded-legacy`; o zero-padding recupera o núcleo (conta, personagens, itens, afetos), mas perde o que estava depois do corte. Não é o mesmo que ter o layout antigo mapeado.
- **Item que mudou de slot:** o UUID é por posição, então o item antigo permanece e um novo é criado. Um diff de inventário é trabalho de uma fase posterior.
- **Contas antigas:** 4294 é detectada e recusada. 7500–7600 exigem opt-in e passam por zero-padding; não há adivinhação de offsets.
- **Catálogo de itens:** o `.bin` do cliente WYD Global é importado para `catalog.*`; o `ItemList.csv` do 7662 continua servindo só de validação. Os dois catálogos **não** são cruzados automaticamente.
- **`STRUCT_MOBEXTRA` completo:** `SaveCelestial`, `NT`, `KefraTicket` e `DayLog` ficam no `raw_mobextra`; não há colunas dedicadas.

### 9.3. Verificação executada

- `python -m pytest -q` → **82 testes OK**; `ruff check .` sem apontamentos.
- Conta sintética truncada em **7600 bytes** + `--allow-padded-legacy` → pacote completo (13/13 checks), aviso `legacy_account_zero_padded` e `padding_bytes=352`.
- Schema e `load.sql` validados sintaticamente com `pglast` (libpg_query).
- Schema e `load.sql` **executados em PGlite 0.5.14** (PostgreSQL 18.6 compilado para WASM), com o pacote sintético:
  - 1 conta, 2 personagens, 5 itens, 1 afeto, 5 eventos de ledger, 0 issues;
  - `view account_item_totals` → 2 personagens, 2 itens de cargo, 5 itens no total;
  - `item_ledger` bloqueia `UPDATE`; segunda carga mantém 5 eventos (idempotência);
  - `items_owner_exactly_one`, nome duplicado e `items_gem_consistency` rejeitados;
  - `raw_mobextra` com 552 bytes; `arch_level=1`, `celestial_level=2`, `sub_celestial_level=3`, `celestial_reset=1`, `resist[0]=-5`.
- Schema e `load.sql` executados em **PostgreSQL 16.15** (imagem oficial `postgres:16`, via Docker), com o mesmo pacote sintético:
  - schema aplicado sem erro; `load.sql` com 13/13 checks; 1 conta, 2 personagens, 5 itens, 1 afeto e 5 eventos de ledger;
  - segunda carga manteve as contagens (idempotência);
  - views: Hero com 2 equip/1 carry, Mage com 0/0; conta com 2 personagens, 2 itens de cargo e 5 no total;
  - 10 violações rejeitadas: `UPDATE`, `DELETE` e `TRUNCATE` do ledger; login e nome duplicados (case-insensitive); item com dois donos; cargo com dono personagem; duas instâncias na mesma posição; gema abaixo de +10; slot de equip 16;
  - `raw_mobextra` com 552 bytes; `arch_level=1`, `celestial_level=2`, `sub_celestial_level=3`, `celestial_reset=1`, `resist[0]=-5`.
- **Catálogo do cliente real:** `ItemList.bin` → 4.300 itens e 16.083 efeitos; `SkillData.bin` → 248 slots, 152 com `skill_id`. Round-trip exato em [tests/test_client_tables.py](../tests/test_client_tables.py); pacote e reconciliação em [tests/test_catalog.py](../tests/test_catalog.py); contrato de colunas emissor → DDL coberto por teste.
- **`schema/002_catalog.sql` + `load_catalog.sql` gerado, executados em PGlite 0.5.14** (PostgreSQL em WASM):
  - fixture: 7 violações rejeitadas (`item_index = 0`, nome vazio, `mesh < -1`, offset negativo, `flag` de skill fora de 0/1, efeito sentinela 255 e slot de efeito 12);
  - pacote real (4.300 itens / 16.083 efeitos / 248 skills): carga completa sem erro; segunda execução do **mesmo** `load_catalog.sql` deixa as contagens idênticas e `load_runs` com 1 linha;
  - full-refresh: apagar o último item dos CSVs e reexecutar remove o item (`6499`) e seus efeitos (`16.083 → 16.082`), sem tocar nas skills — o `ON DELETE CASCADE` de `item_effects` cobre o caso;
  - troca de skills entre slots (`slot 0 ↔ 1`): a carga zera o `skill_id` dos slots que serão regravados antes do upsert, então o índice único parcial `catalog_skills_id_uq` não aborta no meio do statement;
  - views de reconciliação: dois itens usados em `wyd.items` (`40.000` e `999.999`) aparecem em `missing_items` **e** em `out_of_range_items`, e `coverage` fecha em `used=2`, `missing=2`, `out_of_range=2`;
  - **limitação:** PGlite não executa meta-comandos do `psql`, então as três linhas `\copy` foram substituídas por `INSERT`s equivalentes no staging; todo o resto do arquivo (staging, upsert, deletes, `load_runs`) rodou literalmente. Não há `psql`/PostgreSQL nativo nesta máquina para executar o `\copy` em si.
- **`schema/002_catalog.sql` + `load_catalog.sql` (com `\copy`) executados em PostgreSQL 16.15** (imagem oficial `postgres:16`, Docker), com o pacote real:
  - primeira carga: **4.300 itens, 16.083 efeitos, 248 skills** (152 com `skill_id`), `load_runs = 1`;
  - segunda execução do mesmo pacote: contagens idênticas e `load_runs` continua 1 (idempotência);
  - full-refresh: pacote sem o item `6499` → **4.299 itens, 16.082 efeitos**, item e efeitos ausentes, skills intactas;
  - as três linhas `\copy` correram relativas ao diretório do pacote, sem ajuste no SQL gerado.
- **Pendência de ambiente:** a carga de **contas** (`load.sql`) ainda precisa rodar no PostgreSQL 16 do provedor com o dump real; o catálogo já foi validado no motor oficial.
- Gateway validado contra `postgres:16` em Docker (`gateway/scripts/test-postgres.sh`): conta, 2 personagens, equipamento, cargo, bloqueio, hash PBKDF2 e dois logins TCP reais, além de consultas preparadas e erros de banco.
- **Validação de catálogo no gateway:** os SQLs reais de `EQUIP_SQL`/`CARGO_SQL` (extraídos do Rust, sem reescrita) rodaram em PGlite com o fixture: equipamento e cargo de `TestAccount` com `catalog_known=true`; o item `9999` de `BrokenCatalogAccount` sai com `catalog_known=false`, e `ensure_catalog_known` é coberto por teste unitário com a mensagem completa.
- **Integração do gateway em PostgreSQL 16.15:** `gateway/scripts/test-postgres.sh` aplicou `001_init.sql`, `002_catalog.sql` e o fixture no `postgres:16` e rodou os **5 testes** de `gateway/tests/postgres.rs` — **5 passed**, incluindo `recusa_item_fora_do_catalogo` e os dois logins TCP reais.
- **Limitação:** a carga validada usa fixture sintética, não um dump real. O PostgreSQL 16.15 é o motor oficial, mas as extensões e a configuração do provedor de produção ainda precisam ser testadas com o dump real antes do go-live.

---

## 10. Próximos passos

1. Rodar o dry-run em um dump real e revisar `report.json` antes de qualquer carga.
2. Repetir schema + `load.sql` no PostgreSQL 16 do provedor com o dump real e comparar as views.
3. Mapear o layout de 4294 e confirmar o zero-padding de 7500–7600 com amostras reais.
4. Decidir se o catálogo do 7662 (`ItemList.csv`) e o do cliente (`ItemList.bin`) convivem, e como preferência de preços/efeitos é resolvida quando divergirem.
5. Levar `kefra_ticket`, `NT` e `SaveCelestial` para colunas próprias, se o gameplay exigir.

---

**Voltar ao índice:** [00-INDICE.md](00-INDICE.md)
