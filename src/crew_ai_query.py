import os
import re
from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv

load_dotenv()


class SQLQueryCrew:
    """Crew CrewAI que gera SQL PostgreSQL (somente-leitura) a partir de linguagem
    natural + o schema do banco (YAML). Multi-provider via LLM_MODEL."""

    def __init__(self):
        self.llm = os.getenv("LLM_MODEL", "gpt-4o-mini")

    @staticmethod
    def _extract_sql(text: str) -> str:
        """Extrai a query de dentro de cercas ```sql ... ``` ou texto puro."""
        match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        sql = (match.group(1) if match else text).strip()
        return sql.rstrip(";").strip()

    def kickoff(self, inputs: dict) -> dict:
        yaml_path = inputs["yaml_path"]
        user_request = inputs["user_request"]
        database_name = inputs.get("database_name", "")

        with open(yaml_path, "r", encoding="utf-8") as f:
            schema = f.read()

        engenheiro = Agent(
            role="Engenheiro de Dados PostgreSQL",
            goal="Escrever UMA query SQL PostgreSQL correta e SOMENTE-LEITURA (SELECT) "
                 "que atenda ao pedido do usuário usando exatamente o schema fornecido.",
            backstory="Especialista em SQL que traduz pedidos em linguagem natural para "
                      "consultas precisas, sem inventar tabelas ou colunas fora do schema.",
            llm=self.llm,
            verbose=False,
        )

        task = Task(
            description=(
                f"Banco: {database_name} (PostgreSQL)\n"
                f"Schema disponível:\n{schema}\n\n"
                f"Pedido do usuário: {user_request}\n\n"
                "Escreva UMA única query SQL SELECT que atenda ao pedido. "
                "Use apenas tabelas/colunas do schema. NÃO gere INSERT/UPDATE/DELETE/DROP. "
                "Responda APENAS com a query, sem explicações e sem cercas de código."
            ),
            expected_output="Uma única query SQL SELECT válida para PostgreSQL.",
            agent=engenheiro,
        )

        crew = Crew(agents=[engenheiro], tasks=[task], process=Process.sequential)
        raw = crew.kickoff(inputs=inputs).raw
        return {"sql": self._extract_sql(raw)}
