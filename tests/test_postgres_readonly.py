"""Testes de integração da camada 2: a sessão read-only do PostgreSQL.

Diferente de `test_sql_guard.py` (lógica pura), estes testes exigem um PostgreSQL de
verdade — é o único jeito de provar que quem recusa a escrita é o banco, e não o Python.

Configure a URI e rode:

    export PRJ07_TEST_DSN="postgresql://postgres:postgres@localhost:55432/ecommerce"
    uv run pytest tests/test_postgres_readonly.py

Sem a variável definida, os testes são pulados (skip), não falham.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

psycopg2 = pytest.importorskip("psycopg2")

from postgres_connection import PostgresConnection  # noqa: E402

DSN = os.getenv("PRJ07_TEST_DSN")

pytestmark = pytest.mark.skipif(
    not DSN, reason="defina PRJ07_TEST_DSN para rodar os testes de integração"
)


@pytest.fixture
def conn():
    c = PostgresConnection(DSN)
    c.connect()
    yield c
    c.close()


# --------------------------------------------------------------------------
# Leitura continua funcionando
# --------------------------------------------------------------------------

def test_select_funciona(conn):
    conn.cursor.execute("SELECT count(*) FROM clientes")
    assert conn.cursor.fetchone()[0] > 0


def test_get_colunas_reflete_a_query(conn):
    conn.cursor.execute("SELECT nome, email FROM clientes LIMIT 1")
    assert conn.get_colunas() == ["nome", "email"]


# --------------------------------------------------------------------------
# A garantia: o PostgreSQL recusa a escrita, não o Python
# --------------------------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "DELETE FROM pedidos",
    "UPDATE clientes SET nome = 'hackeado'",
    "INSERT INTO clientes (nome, email) VALUES ('x', 'x@x.com')",
    "DROP TABLE clientes",
    "TRUNCATE pedidos",
    "CREATE TABLE invadido (id int)",
    "ALTER TABLE clientes ADD COLUMN backdoor text",
])
def test_escrita_e_recusada_pelo_banco(conn, sql):
    with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
        conn.cursor.execute(sql)


def test_bypass_do_guard_ainda_seria_barrado_pelo_banco(conn):
    """Defesa em profundidade: mesmo que a camada 1 falhasse, a 2 segura.

    Esta é exatamente a query que passava pelo guard antigo.
    """
    with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
        conn.cursor.execute("SELECT 1; DROP TABLE clientes")


def test_tabela_continua_intacta_apos_as_tentativas(conn):
    conn.cursor.execute("SELECT count(*) FROM clientes")
    assert conn.cursor.fetchone()[0] > 0


# --------------------------------------------------------------------------
# statement_timeout
# --------------------------------------------------------------------------

def test_statement_timeout_cancela_query_longa():
    c = PostgresConnection(DSN, statement_timeout_ms=300)
    c.connect()
    try:
        with pytest.raises(psycopg2.errors.QueryCanceled):
            c.cursor.execute("SELECT pg_sleep(5)")
    finally:
        c.close()


def test_statement_timeout_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv("PG_STATEMENT_TIMEOUT_MS", "1234")
    assert PostgresConnection(DSN).statement_timeout_ms == 1234


# --------------------------------------------------------------------------
# Ciclo de vida da conexão
# --------------------------------------------------------------------------

def test_context_manager_fecha_a_conexao():
    with PostgresConnection(DSN) as c:
        c.cursor.execute("SELECT 1")
        assert c.cursor.fetchone()[0] == 1
    assert c.conn.closed


def test_close_e_idempotente():
    c = PostgresConnection(DSN)
    c.connect()
    c.close()
    c.close()  # não pode levantar
