import os

import psycopg2

from postgres_databases import ParametrosConexao


class PostgresConnection:
    """Conexão com PostgreSQL via psycopg2.

    A sessão é aberta em modo **read-only**: quem recusa qualquer escrita é o próprio
    PostgreSQL (erro ``ReadOnlySqlTransaction``), não uma validação em Python. Essa é a
    garantia; o :mod:`sql_guard` é apenas a barreira de aplicação, que falha antes.

    Também aplica um ``statement_timeout`` para que uma query gerada por LLM não prenda
    uma conexão indefinidamente.
    """

    def __init__(
        self,
        conexao: "ParametrosConexao | str",
        statement_timeout_ms: int | None = None,
    ):
        # Uma DSN em texto é aceita por conveniência (testes de integração), mas é
        # convertida na hora: o objeto NUNCA guarda a string com a senha dentro.
        self.conexao = (
            conexao
            if isinstance(conexao, ParametrosConexao)
            else ParametrosConexao.de_dsn(conexao)
        )
        self.statement_timeout_ms = statement_timeout_ms or int(
            os.getenv("PG_STATEMENT_TIMEOUT_MS", "15000")
        )
        self.conn = None
        self.cursor = None

    def connect(self):
        self.conn = psycopg2.connect(**self.conexao.kwargs())
        # Read-only ANTES de qualquer query: vale para toda transação da sessão.
        self.conn.set_session(readonly=True, autocommit=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            f"SET LOCAL statement_timeout = {int(self.statement_timeout_ms)}"
        )
        return self

    def get_colunas(self):
        if self.cursor and self.cursor.description:
            return [col[0] for col in self.cursor.description]
        return []

    def close(self):
        # Encerra a transação read-only aberta antes de devolver a conexão.
        if self.conn and not self.conn.closed:
            try:
                self.conn.rollback()
            except psycopg2.Error:
                pass
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc, tb):
        self.close()
