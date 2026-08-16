import json
import psycopg2
from fastmcp import FastMCP
from crew_ai_query import SQLQueryCrew
from postgres_connection import PostgresConnection
from postgres_databases import DatabaseDesconhecido, PostgresDatabases
from sql_guard import UnsafeSQLError, validate_read_only

mcp = FastMCP("mcp_buscador")


@mcp.tool(name="buscar_dados_sql")
def buscar_dados_sql(query: str, database_name: str) -> str:
    """Responde uma pergunta em linguagem natural consultando o banco indicado.

    O SQL é gerado a partir do schema, validado como somente-leitura e executado numa
    sessão read-only. Use `listar_databases` para descobrir os valores de `database_name`.
    """
    try:
        try:
            yaml_path = str(PostgresDatabases.get_schema_path(database_name))
        except DatabaseDesconhecido as e:
            return str(e)

        inputs = {'database_type': 'Postgres',
                  'database_name': database_name,
                  'yaml_path': yaml_path,
                  'user_request': query,
                  'json_output': False}

        sql_bruto = SQLQueryCrew().kickoff(inputs)["sql"]

        # Camada 1 — barreira de aplicação: um único comando, e de leitura.
        # Falha cedo, com motivo legível, sem gastar ida ao banco.
        try:
            sql = validate_read_only(sql_bruto)
        except UnsafeSQLError as e:
            return f"Consulta rejeitada ({e}): {sql_bruto[:200]}"

        # Camada 2 — garantia: a sessão é read-only, quem recusa escrita é o PostgreSQL.
        conexao = PostgresDatabases.get_connection_params(database_name)
        with PostgresConnection(conexao) as conn:
            cursor = conn.cursor
            cursor.execute(sql)
            results = cursor.fetchall()
            colunas = conn.get_colunas()
            dados = [dict(zip(colunas, row)) for row in results]
            return json.dumps({"sql": sql, "rows": dados}, ensure_ascii=False, default=str)

    except psycopg2.errors.ReadOnlySqlTransaction:
        return "Consulta rejeitada pelo banco: a sessão é somente-leitura."
    except psycopg2.errors.QueryCanceled:
        return "Consulta cancelada: excedeu o statement_timeout configurado."
    except Exception as e:
        return f"Erro ao buscar dados: {e}"

@mcp.tool(name="listar_databases")
def listar_databases() -> str:
    """Lista os bancos disponíveis para consulta.

    Use antes de `buscar_dados_sql` para descobrir o valor válido de `database_name`.
    """
    return json.dumps({"databases": PostgresDatabases.nomes()}, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run(transport="stdio")
