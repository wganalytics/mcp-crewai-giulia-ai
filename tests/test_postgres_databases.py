"""Testes do catálogo de bancos — sem tocar o PostgreSQL."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from postgres_databases import (  # noqa: E402
    ConfiguracaoAusente,
    DatabaseDesconhecido,
    ParametrosConexao,
    PostgresDatabases,
)


def test_nomes_padrao():
    assert PostgresDatabases.nomes() == ["ecommerce", "clinica"]


def test_nome_pode_ser_renomeado_por_ambiente(monkeypatch):
    monkeypatch.setenv("PG_ECOMMERCE_DB", "loja_prod")
    assert "loja_prod" in PostgresDatabases.nomes()


def test_ambiente_e_lido_a_cada_chamada(monkeypatch):
    """Antes era atributo de classe, resolvido no import — dependia da ordem."""
    monkeypatch.setenv("PG_CLINICA_DB", "primeiro")
    assert "primeiro" in PostgresDatabases.nomes()
    monkeypatch.setenv("PG_CLINICA_DB", "segundo")
    assert "segundo" in PostgresDatabases.nomes()


@pytest.mark.parametrize("nome,arquivo", [
    ("ecommerce", "schema_ecommerce.yaml"),
    ("clinica", "schema_clinica.yaml"),
])
def test_schema_path_aponta_para_arquivo_existente(nome, arquivo):
    caminho = PostgresDatabases.get_schema_path(nome)
    assert caminho.name == arquivo
    assert caminho.is_file(), "o YAML de schema precisa existir no repositório"


def test_schema_path_independe_do_diretorio_de_execucao(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert PostgresDatabases.get_schema_path("ecommerce").is_file()


def test_banco_desconhecido_levanta_com_lista_de_opcoes():
    with pytest.raises(DatabaseDesconhecido, match="ecommerce, clinica"):
        PostgresDatabases.get_schema_path("financeiro")


def test_uri_valida_o_nome_antes_de_montar():
    with pytest.raises(DatabaseDesconhecido):
        PostgresDatabases.get_connection_params("inexistente")


def test_uri_usa_credenciais_do_ambiente(monkeypatch):
    monkeypatch.setenv("PG_HOST", "db.interno")
    monkeypatch.setenv("PG_PORT", "6543")
    monkeypatch.setenv("PG_USER", "giulia_ro")
    monkeypatch.setenv("PG_PASSWORD", "s3nh4")
    p = PostgresDatabases.get_connection_params("ecommerce")
    assert p.kwargs() == {
        "host": "db.interno",
        "port": "6543",
        "user": "giulia_ro",
        "password": "s3nh4",
        "dbname": "ecommerce",
    }


# --------------------------------------------------------------------------
# Credencial não tem valor padrão
#
# Antes: PG_USER caía em "postgres" (superusuário) e PG_PASSWORD numa senha
# conhecida. A conexão podia ter sucesso com privilégio errado, em silêncio —
# o oposto do desenho somente-leitura do projeto.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("faltando", ["PG_USER", "PG_PASSWORD"])
def test_credencial_sem_valor_padrao_falha_explicitamente(monkeypatch, faltando):
    monkeypatch.setenv("PG_USER", "giulia_ro")
    monkeypatch.setenv("PG_PASSWORD", "s3nh4")
    monkeypatch.delenv(faltando, raising=False)
    with pytest.raises(ConfiguracaoAusente, match=faltando):
        PostgresDatabases.get_connection_params("ecommerce")


@pytest.mark.parametrize("vazia", ["PG_USER", "PG_PASSWORD"])
def test_credencial_vazia_conta_como_ausente(monkeypatch, vazia):
    """PG_PASSWORD= no .env é engano de preenchimento, não senha vazia."""
    monkeypatch.setenv("PG_USER", "giulia_ro")
    monkeypatch.setenv("PG_PASSWORD", "s3nh4")
    monkeypatch.setenv(vazia, "")
    with pytest.raises(ConfiguracaoAusente):
        PostgresDatabases.get_connection_params("ecommerce")


def test_erro_de_configuracao_nao_vaza_a_senha(monkeypatch):
    monkeypatch.setenv("PG_PASSWORD", "s3nh4-secreta")
    monkeypatch.delenv("PG_USER", raising=False)
    with pytest.raises(ConfiguracaoAusente) as e:
        PostgresDatabases.get_connection_params("ecommerce")
    assert "s3nh4-secreta" not in str(e.value)


def test_host_e_porta_seguem_com_padrao(monkeypatch):
    """Errar host/porta não muda privilégio — a conexão só falha."""
    monkeypatch.delenv("PG_HOST", raising=False)
    monkeypatch.delenv("PG_PORT", raising=False)
    monkeypatch.setenv("PG_USER", "giulia_ro")
    monkeypatch.setenv("PG_PASSWORD", "s3nh4")
    p = PostgresDatabases.get_connection_params("ecommerce")
    assert (p.host, p.port) == ("localhost", "5432")


# --------------------------------------------------------------------------
# A senha não circula em string
#
# Antes: get_database_uri devolvia "postgresql://user:SENHA@host/db". O servidor
# MCP devolve `f"Erro ao buscar dados: {e}"` PARA O AGENTE — bastava um traceback
# carregando essa URI para a senha sair do processo.
# --------------------------------------------------------------------------


@pytest.fixture
def params(monkeypatch):
    monkeypatch.setenv("PG_HOST", "db.interno")
    monkeypatch.setenv("PG_PORT", "6543")
    monkeypatch.setenv("PG_USER", "giulia_ro")
    monkeypatch.setenv("PG_PASSWORD", "s3nh4-secreta")
    return PostgresDatabases.get_connection_params("ecommerce")


def test_repr_nao_contem_a_senha(params):
    assert "s3nh4-secreta" not in repr(params)


def test_str_mascara_a_senha(params):
    assert str(params) == "postgresql://giulia_ro:***@db.interno:6543/ecommerce"
    assert "s3nh4-secreta" not in str(params)


def test_interpolacao_em_mensagem_de_erro_nao_vaza(params):
    """É exatamente o formato que o servidor MCP devolve ao agente."""
    assert "s3nh4-secreta" not in f"Erro ao buscar dados: {params}"


def test_a_senha_sai_apenas_em_kwargs(params):
    assert params.kwargs()["password"] == "s3nh4-secreta"


def test_de_dsn_reconstroi_os_campos():
    p = ParametrosConexao.de_dsn("postgresql://u:pw@h:5433/banco")
    assert (p.host, p.port, p.user, p.dbname) == ("h", "5433", "u", "banco")
    assert p.kwargs()["password"] == "pw"
    assert "pw" not in repr(p)
