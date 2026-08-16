"""Catálogo dos bancos disponíveis para consulta.

Cada banco é um nome (configurável por ambiente) associado ao YAML que descreve seu
schema — é esse YAML que o Crew lê para gerar SQL sem inventar tabela ou coluna.

Os nomes são resolvidos **a cada chamada**, não no import: antes eram atributos de
classe avaliados no carregamento do módulo, então dependiam de o ``load_dotenv()`` de
outro módulo ter rodado antes. Ordem de import não deve alterar configuração.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SCHEMAS_DIR = Path(__file__).resolve().parent


class DatabaseDesconhecido(ValueError):
    """O nome informado não está no catálogo."""


class ConfiguracaoAusente(RuntimeError):
    """Falta variável de ambiente obrigatória para conectar."""


def _obrigatorio(nome: str) -> str:
    """Lê uma variável que NÃO pode ter valor padrão.

    Credencial de banco não tem default. ``PG_USER`` caía em ``postgres`` — o
    superusuário —, o oposto do desenho somente-leitura deste projeto; e
    ``PG_PASSWORD`` caía numa senha conhecida. Nos dois casos a conexão poderia ter
    sucesso com privilégio errado, sem nenhum aviso. Falhar aqui é o comportamento
    correto: erro de configuração deve aparecer na configuração.
    """
    valor = os.getenv(nome)
    if not valor:
        raise ConfiguracaoAusente(
            f"{nome} não está definida. Copie .env.example para .env e preencha — "
            f"não existe valor padrão de propósito."
        )
    return valor


@dataclass(frozen=True)
class ParametrosConexao:
    """Dados de conexão com a senha isolada.

    psycopg2 aceita uma URI pronta (``postgresql://user:senha@host/db``), e era assim
    que este módulo entregava a conexão. O problema não é a URI em si: é que a senha
    passa a viver dentro de uma string comum, que circula por log, por ``repr`` de
    objeto e por traceback. Neste projeto havia um caminho concreto — o servidor MCP
    devolve ``f"Erro ao buscar dados: {e}"`` **para o agente**.

    Aqui a senha sai apenas em :meth:`kwargs`, no instante de conectar. O ``repr``
    gerado pela dataclass a omite (``field(repr=False)``) e o ``__str__`` a mascara.
    """

    host: str
    port: str
    user: str
    password: str = field(repr=False)
    dbname: str

    def kwargs(self) -> dict[str, str]:
        """Argumentos para ``psycopg2.connect`` — único ponto onde a senha aparece."""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "dbname": self.dbname,
        }

    def __str__(self) -> str:
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{self.dbname}"

    @classmethod
    def de_dsn(cls, dsn: str) -> "ParametrosConexao":
        """Constrói a partir de uma DSN — usado pelos testes de integração.

        Importa psycopg2 aqui dentro de propósito: este módulo é um catálogo puro e
        seus testes não devem exigir o driver instalado.
        """
        from psycopg2.extensions import parse_dsn

        p = parse_dsn(dsn)
        return cls(
            host=p.get("host", "localhost"),
            port=str(p.get("port", "5432")),
            user=p.get("user", ""),
            password=p.get("password", ""),
            dbname=p.get("dbname", ""),
        )


class PostgresDatabases:
    # nome padrão -> (variável de ambiente que o renomeia, arquivo de schema)
    _CATALOGO = {
        "ecommerce": ("PG_ECOMMERCE_DB", "schema_ecommerce.yaml"),
        "clinica": ("PG_CLINICA_DB", "schema_clinica.yaml"),
    }

    @classmethod
    def nomes(cls) -> list[str]:
        """Nomes dos bancos disponíveis, já resolvidos pelo ambiente."""
        return [os.getenv(env, padrao) for padrao, (env, _) in cls._CATALOGO.items()]

    @classmethod
    def _schema_de(cls, database_name: str) -> str:
        for padrao, (env, schema) in cls._CATALOGO.items():
            if database_name == os.getenv(env, padrao):
                return schema
        raise DatabaseDesconhecido(
            f"banco '{database_name}' não encontrado — "
            f"disponíveis: {', '.join(cls.nomes())}"
        )

    @classmethod
    def get_schema_path(cls, database_name: str) -> Path:
        """Caminho do YAML de schema do banco, ancorado na pasta do módulo."""
        return SCHEMAS_DIR / cls._schema_de(database_name)

    @classmethod
    def get_connection_params(cls, database_name: str) -> ParametrosConexao:
        """Parâmetros de conexão do banco, lidos do ambiente.

        Substitui o antigo ``get_database_uri``, que devolvia a senha embutida numa
        string — ver :class:`ParametrosConexao`.
        """
        cls._schema_de(database_name)  # valida o nome antes de ler credencial
        # Host e porta têm padrão porque errar neles não muda privilégio: a conexão
        # simplesmente falha. Usuário e senha não têm — ver _obrigatorio().
        return ParametrosConexao(
            host=os.getenv("PG_HOST", "localhost"),
            port=os.getenv("PG_PORT", "5432"),
            user=_obrigatorio("PG_USER"),
            password=_obrigatorio("PG_PASSWORD"),
            dbname=database_name,
        )
