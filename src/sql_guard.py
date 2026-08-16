"""Validação de SQL somente-leitura para o servidor text-to-SQL.

Esta é a **camada 1 de duas**. A camada 2 — a que de fato garante — é a transação
read-only aberta em ``PostgresConnection.connect()``; quem recusa a escrita ali é o
próprio PostgreSQL, não código Python.

Esta camada existe para falhar cedo e com mensagem clara, antes de gastar uma ida ao
banco, e para barrar múltiplos statements (que a transação read-only não distingue de
um só).

Por que não basta ``sql.startswith("select")``:

    SELECT 1; DROP TABLE clientes

começa com ``select``, e o psycopg2 executa os dois comandos numa única chamada de
``execute()``. Validar prefixo é validar string; o que precisamos é validar comando.
Como o SQL aqui é gerado por um LLM a partir de texto do usuário, o vetor é prompt
injection.
"""
import re

__all__ = ["UnsafeSQLError", "validate_read_only", "split_statements"]


class UnsafeSQLError(ValueError):
    """A query não passou na validação de somente-leitura."""


# O comando precisa COMEÇAR com um destes (allowlist).
_ALLOWED_START = frozenset({"select", "with", "values", "table"})

# E não pode conter nenhum destes em posição de código (denylist complementar).
# Palavras que são nomes de coluna comuns (comment, security, status...) ficam de fora
# de propósito: falso positivo aqui quebra consulta legítima, e a transação read-only
# já barra a escrita de verdade.
_FORBIDDEN = frozenset("""
insert update delete merge
create drop alter truncate rename
grant revoke
copy vacuum reindex cluster refresh analyze
prepare deallocate execute
begin commit rollback savepoint discard reset
listen notify unlisten lock
""".split())

_WORD = re.compile(r"[a-z_][a-z_0-9]*")
_DOLLAR_TAG = re.compile(r"\$([A-Za-z_][A-Za-z_0-9]*)?\$")


def _scan(sql: str) -> tuple[list[str], list[str]]:
    """Percorre o SQL uma vez, separando código de literal/comentário.

    Retorna duas listas paralelas, uma entrada por statement:

    - ``statements``: o SQL executável, com os comentários removidos;
    - ``skeletons``: o mesmo statement com o *conteúdo* de literais de texto e de
      identificadores entre aspas trocado por vazio.

    A busca por palavras reservadas acontece no esqueleto — assim um dado como
    ``WHERE nome = 'drop table'`` não é confundido com o comando DROP.
    """
    statements: list[str] = []
    skeletons: list[str] = []
    cur: list[str] = []
    skel: list[str] = []
    i, n = 0, len(sql)

    def _close_quoted(open_at: int, quote: str) -> int:
        """Devolve o índice do fechamento, tratando o escape por duplicação ('' / "")."""
        j = open_at + 1
        while j < n:
            if sql[j] == quote:
                if j + 1 < n and sql[j + 1] == quote:
                    j += 2
                    continue
                return j
            j += 1
        raise UnsafeSQLError(f"literal {quote}...{quote} não foi fechado")

    while i < n:
        # -- comentário de linha
        if sql.startswith("--", i):
            quebra = sql.find("\n", i)
            i = n if quebra == -1 else quebra + 1
            cur.append(" ")
            skel.append(" ")
            continue

        # /* comentário de bloco */ — aninhável no PostgreSQL
        if sql.startswith("/*", i):
            profundidade, i = 1, i + 2
            while i < n and profundidade:
                if sql.startswith("/*", i):
                    profundidade += 1
                    i += 2
                elif sql.startswith("*/", i):
                    profundidade -= 1
                    i += 2
                else:
                    i += 1
            if profundidade:
                raise UnsafeSQLError("comentário de bloco não foi fechado")
            cur.append(" ")
            skel.append(" ")
            continue

        ch = sql[i]

        # 'literal de texto' e "identificador"
        if ch in ("'", '"'):
            fim = _close_quoted(i, ch)
            cur.append(sql[i:fim + 1])
            skel.append(f" {ch}{ch} ")
            i = fim + 1
            continue

        # $tag$ corpo $tag$
        if ch == "$":
            marca = _DOLLAR_TAG.match(sql, i)
            if marca:
                tag = marca.group(0)
                fim = sql.find(tag, i + len(tag))
                if fim == -1:
                    raise UnsafeSQLError(f"bloco {tag} não foi fechado")
                cur.append(sql[i:fim + len(tag)])
                skel.append(" '' ")
                i = fim + len(tag)
                continue

        # fim de statement
        if ch == ";":
            statements.append("".join(cur))
            skeletons.append("".join(skel))
            cur, skel = [], []
            i += 1
            continue

        cur.append(ch)
        skel.append(ch)
        i += 1

    statements.append("".join(cur))
    skeletons.append("".join(skel))
    return statements, skeletons


def split_statements(sql: str) -> list[str]:
    """Separa o SQL em statements, ignorando ``;`` dentro de literal ou comentário."""
    statements, _ = _scan(sql)
    return [s for s in (st.strip() for st in statements) if s]


def validate_read_only(sql: str) -> str:
    """Valida que ``sql`` é um único comando de leitura e o devolve normalizado.

    Levanta :class:`UnsafeSQLError` com o motivo quando não for.
    """
    if not sql or not sql.strip():
        raise UnsafeSQLError("query vazia")

    statements, skeletons = _scan(sql)
    pares = [
        (st.strip(), sk)
        for st, sk in zip(statements, skeletons)
        if st.strip()
    ]

    if not pares:
        raise UnsafeSQLError("query vazia (só comentários)")
    if len(pares) > 1:
        raise UnsafeSQLError(
            f"apenas um comando é permitido — foram encontrados {len(pares)}"
        )

    comando, esqueleto = pares[0]
    palavras = _WORD.findall(esqueleto.lower())

    if not palavras:
        raise UnsafeSQLError("nenhum comando SQL reconhecido")

    if palavras[0] not in _ALLOWED_START:
        raise UnsafeSQLError(
            f"comando '{palavras[0].upper()}' não é de leitura — "
            f"esperado um de: {', '.join(sorted(_ALLOWED_START)).upper()}"
        )

    proibidas = sorted({p for p in palavras if p in _FORBIDDEN})
    if proibidas:
        raise UnsafeSQLError(
            f"a query contém comando de escrita: {', '.join(p.upper() for p in proibidas)}"
        )

    return comando
