import os
from crewai import Agent, Task, Crew, Process
from crewai_tools import MCPServerAdapter
from dotenv import load_dotenv
from crewai_load_server import CrewaiConnServer

load_dotenv()

class ConversaMCP:
    def __init__(self):
        self.server_params = CrewaiConnServer.get_params("mcp_buscador")
        self.llm = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self._create_crew()

    def _get_mcp_tools(self):
        self.adapter = MCPServerAdapter(self.server_params)
        return self.adapter.tools

    def _create_crew(self):
        tools = self._get_mcp_tools()
        self.conversa_agent = Agent(
            role="Você é um assistente conversacional especializado em resolver as necessidades do usuário usando ferramentas MCP.",
            goal="Entender a necessidade do usuário e utilizar as ferramentas MCP disponíveis para responder ou resolver o problema.",
            backstory="Uma IA de conversa que utiliza scripts locais via MCP para fornecer respostas e soluções contextualizadas.",
            tools=tools,
            reasoning=True,
            verbose=True,
            llm=self.llm
        )
        self.conversa_task = Task(
            description="""Entenda a necessidade do usuário
na chave 'query' = {query}, e utilize as ferramentas MCP disponíveis
para responder ou resolver o problema apresentado.""",
            expected_output="Uma resposta clara, útil e contextualizada para a necessidade do usuário, utilizando as ferramentas MCP quando necessário.",
            agent=self.conversa_agent,
            markdown=True
        )
        self.conversa_crew = Crew(
            agents=[self.conversa_agent],
            tasks=[self.conversa_task],
            verbose=True,
            process=Process.sequential
        )

    def kickoff(self, inputs):
        result = self.conversa_crew.kickoff(inputs=inputs).raw
        return result
