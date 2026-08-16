import streamlit as st
from crewai_mcp_client import ConversaMCP
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

st.set_page_config(page_title="CrewAI MCP Chat", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("Chat com Agente CrewAI")

chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if prompt := st.chat_input("Digite sua mensagem para o agente..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with chat_container:
        with st.chat_message("user"):
            st.write(prompt)
            
    with st.spinner("Processando..."):
        conversa_mcp = ConversaMCP()
        response = conversa_mcp.kickoff(inputs={"query": prompt})
        
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    with chat_container:
        with st.chat_message("assistant"):
            st.markdown(response)
