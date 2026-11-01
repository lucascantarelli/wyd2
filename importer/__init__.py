"""Importador legado WYD -> PostgreSQL.

Fase 2 do projeto: decodifica STRUCT_ACCOUNTFILE (7952 bytes, alinhamento
natural MSVC x86), gera um pacote auditavel (JSONL + COPY CSV + load.sql) e um
relatorio de reconciliacao.

O texto plano de senha/PIN nunca sai do decode: e transformado em hash antes
de qualquer gravacao.
"""

__version__ = "0.1.0"
SCHEMA_VERSION = "001"
# schema/002_catalog.sql: catalogo de itens e skills do cliente.
CATALOG_SCHEMA_VERSION = "002"
TOOL_NAME = "wyd-importer"
