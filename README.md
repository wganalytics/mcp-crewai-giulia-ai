# PRJ-07 — CrewAI + MCP: Text-to-SQL

Sistema **multi-agente CrewAI** + servidor **MCP** que faz **text-to-SQL**: o usuário
conversa (Streamlit), um agente CrewAI usa as tools MCP, o servidor gera **SQL real** a
partir de linguagem natural (com base no schema) e consulta bancos **PostgreSQL** de
demonstração (`ecommerce` e `clinica`). Corresponde ao **Capítulo 8** do livro *Model
Context Protocol* (Sandeco).

Os mocks originais (SQL fixo, `MockCursor`, URI falsa) foram substituídos por: geração de
SQL por um Crew real (`crew_ai_query.py`), conexão `psycopg2` real (`postgres_connection.py`)
e URI a partir de env (`postgres_databases.py`). Consultas são **somente-leitura** — ver
[Segurança](#segurança).

## Multi-provider

Modelo por `LLM_MODEL` (OpenAI/Anthropic/Gemini/OpenRouter) — ver `.env.example`.

## Pré-requisitos: PostgreSQL com massa de teste

```bash
# cria os 2 bancos e popula com os dados demo (ajuste user/host conforme seu .env)
createdb ecommerce && createdb clinica
psql -d ecommerce -f data/seed_ecommerce.sql
psql -d clinica   -f data/seed_clinica.sql
```

Schemas descritos em `src/schema_ecommerce.yaml` e `src/schema_clinica.yaml` (o agente usa
o YAML para gerar SQL correto).

## Uso

```bash
uv sync
cp .env.example .env      # defina LLM_MODEL + chave do provider + credenciais PG
uv run streamlit run src/main.py
```

Fluxo: pergunta em linguagem natural → agente CrewAI chama a tool MCP `buscar_dados_sql`
→ Crew gera o `SELECT` a partir do schema → **validação** → executa no Postgres em sessão
read-only → devolve os dados. Ex.: *"quais os 3 produtos mais vendidos no ecommerce?"*

## Segurança

O SQL é gerado por um LLM a partir de texto do usuário, então o vetor a considerar é
**prompt injection**. A defesa tem duas camadas, e só a segunda é garantia.

### Camada 1 — validação na aplicação (`src/sql_guard.py`)

Falha cedo, com motivo legível, antes de gastar uma ida ao banco:

- **Um único comando.** Múltiplos statements são rejeitados — `psycopg2` executa vários
  comandos separados por `;` numa única chamada de `execute()`.
- **Allowlist de início:** `SELECT`, `WITH`, `VALUES` ou `TABLE`.
- **Denylist complementar** para CTE que escreve (`WITH x AS (DELETE ... RETURNING *)`,
  recurso real do PostgreSQL).
- Comentários (`--`, `/* */` aninhados), literais (`'...'`, `$$...$$`) e identificadores
  (`"..."`) são analisados corretamente: uma palavra reservada dentro de um dado não vira
  comando, e um `;` dentro de um literal não separa statement.

> **Versão anterior:** a validação era `sql.lower().lstrip().startswith("select")`.
> `SELECT 1; DROP TABLE clientes` começa com `select` — e passava. Validar prefixo é
> validar string; o necessário é validar comando. Coberto por
> `tests/test_sql_guard.py::test_rejeita_o_bypass_original`.

### Camada 2 — garantia no banco (`src/postgres_connection.py`)

A sessão é aberta com `set_session(readonly=True)`. Quem recusa a escrita é o próprio
PostgreSQL (`ReadOnlySqlTransaction`), não código Python. Há também um
`statement_timeout` (`PG_STATEMENT_TIMEOUT_MS`, padrão 15s) para que uma query gerada por
LLM não prenda uma conexão indefinidamente.

**Recomendado:** aponte `PG_USER` para um role sem permissão de escrita — defesa em
profundidade, independente da aplicação.

```sql
CREATE ROLE giulia_ro LOGIN PASSWORD 'troque-isto';
GRANT CONNECT ON DATABASE ecommerce TO giulia_ro;
GRANT USAGE ON SCHEMA public TO giulia_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO giulia_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO giulia_ro;
```

## Testes

```bash
uv run pytest                          # 38 testes do sql_guard (lógica pura, sem banco)
```

Os testes da camada 2 exigem um PostgreSQL de verdade — é o único jeito de provar que
quem recusa a escrita é o banco. Sem `PRJ07_TEST_DSN` definido eles são pulados:

```bash
docker run -d --name prj07-mcp-pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 postgres:16-alpine
# crie os bancos e rode os seeds (ver "Pré-requisitos" acima)

export PRJ07_TEST_DSN="postgresql://postgres:postgres@localhost:55432/ecommerce"
uv run pytest                          # 53 testes (38 + 15 de integração)
```

Entre os testes de integração está
`test_bypass_do_guard_ainda_seria_barrado_pelo_banco`: mesmo que a camada 1 falhasse,
`SELECT 1; DROP TABLE clientes` levanta `ReadOnlySqlTransaction`. É a definição de defesa
em profundidade.
