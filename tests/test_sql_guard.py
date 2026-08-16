"""Testes da barreira de aplicação do text-to-SQL.

O caso que originou este módulo é `test_rejeita_o_bypass_original`: a validação
anterior (`sql.lower().lstrip().startswith("select")`) deixava passar
`SELECT 1; DROP TABLE clientes`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sql_guard import UnsafeSQLError, split_statements, validate_read_only  # noqa: E402


# --------------------------------------------------------------------------
# O bypass que motivou a correção
# --------------------------------------------------------------------------

def test_rejeita_o_bypass_original():
    """`SELECT 1; DROP TABLE clientes` começa com select — e passava."""
    with pytest.raises(UnsafeSQLError, match="apenas um comando"):
        validate_read_only("SELECT 1; DROP TABLE clientes")


@pytest.mark.parametrize("sql", [
    "SELECT 1; DROP TABLE clientes",
    "SELECT * FROM produtos; DELETE FROM pedidos",
    "select 1;update usuarios set admin=true",
    "  \n SELECT 1 ; TRUNCATE clientes ; ",
    "SELECT 1;; DROP TABLE x",
])
def test_rejeita_multiplos_statements(sql):
    with pytest.raises(UnsafeSQLError):
        validate_read_only(sql)


# --------------------------------------------------------------------------
# Comandos de escrita isolados
# --------------------------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "DROP TABLE clientes",
    "DELETE FROM pedidos WHERE id = 1",
    "UPDATE usuarios SET admin = true",
    "INSERT INTO log VALUES (1)",
    "TRUNCATE clientes",
    "ALTER TABLE clientes ADD COLUMN x int",
    "GRANT ALL ON clientes TO publico",
    "COPY clientes TO '/tmp/vazou.csv'",
    "CREATE TABLE t (id int)",
])
def test_rejeita_comando_de_escrita(sql):
    with pytest.raises(UnsafeSQLError):
        validate_read_only(sql)


def test_rejeita_cte_que_escreve():
    """CTE que modifica dados é recurso real do PostgreSQL e começa com WITH."""
    sql = "WITH removidos AS (DELETE FROM pedidos RETURNING *) SELECT * FROM removidos"
    with pytest.raises(UnsafeSQLError, match="DELETE"):
        validate_read_only(sql)


# --------------------------------------------------------------------------
# Comentários não podem esconder comando nem quebrar a contagem
# --------------------------------------------------------------------------

def test_comentario_de_linha_e_removido():
    sql = "SELECT nome -- comentário com DROP TABLE aqui\nFROM clientes"
    assert "DROP" not in validate_read_only(sql).upper()


def test_comentario_de_bloco_e_removido():
    sql = "SELECT /* DELETE FROM pedidos */ nome FROM clientes"
    assert "DELETE" not in validate_read_only(sql).upper()


def test_comentario_de_bloco_aninhado():
    sql = "SELECT /* nivel1 /* nivel2 */ ainda comentário */ nome FROM clientes"
    assert validate_read_only(sql).upper().startswith("SELECT")


def test_ponto_e_virgula_dentro_de_comentario_nao_separa_statement():
    assert len(split_statements("SELECT 1 -- ; DROP TABLE x\n")) == 1


def test_query_so_com_comentario_e_rejeitada():
    with pytest.raises(UnsafeSQLError):
        validate_read_only("-- só um comentário")


# --------------------------------------------------------------------------
# Literais não podem virar comando (nem gerar falso positivo)
# --------------------------------------------------------------------------

def test_palavra_proibida_dentro_de_literal_e_permitida():
    sql = "SELECT * FROM logs WHERE acao = 'DROP TABLE clientes'"
    assert validate_read_only(sql) == sql


def test_ponto_e_virgula_dentro_de_literal_nao_separa_statement():
    assert len(split_statements("SELECT * FROM t WHERE s = 'a;b'")) == 1


def test_aspas_simples_escapadas_por_duplicacao():
    sql = "SELECT * FROM t WHERE nome = 'O''Brien; DROP TABLE x'"
    assert validate_read_only(sql) == sql


def test_identificador_entre_aspas_duplas_nao_vira_comando():
    sql = 'SELECT "update" FROM configuracoes'
    assert validate_read_only(sql) == sql


def test_dollar_quoting_nao_vira_comando():
    sql = "SELECT $$DROP TABLE clientes$$ AS texto"
    assert validate_read_only(sql) == sql


def test_literal_nao_fechado_e_rejeitado():
    with pytest.raises(UnsafeSQLError, match="não foi fechado"):
        validate_read_only("SELECT * FROM t WHERE s = 'aberto")


# --------------------------------------------------------------------------
# Leitura legítima continua passando
# --------------------------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "SELECT * FROM produtos",
    "select nome, preco from produtos order by preco desc limit 3",
    "SELECT p.nome, SUM(i.quantidade) FROM produtos p "
    "JOIN itens_pedido i ON i.produto_id = p.id GROUP BY p.nome",
    "WITH top AS (SELECT * FROM produtos LIMIT 3) SELECT * FROM top",
    "SELECT * FROM pedidos OFFSET 10 LIMIT 5",
    "SELECT count(*) FROM clientes WHERE ativo IS TRUE",
    "VALUES (1), (2)",
    "TABLE produtos",
])
def test_aceita_leitura_legitima(sql):
    assert validate_read_only(sql) == sql.strip()


def test_offset_nao_dispara_falso_positivo_de_set():
    """OFFSET contém 'set' — a busca é por palavra inteira, não substring."""
    assert validate_read_only("SELECT 1 OFFSET 5")


def test_ponto_e_virgula_final_unico_e_aceito():
    assert validate_read_only("SELECT * FROM produtos;") == "SELECT * FROM produtos"


def test_query_vazia_e_rejeitada():
    with pytest.raises(UnsafeSQLError, match="vazia"):
        validate_read_only("   ")
