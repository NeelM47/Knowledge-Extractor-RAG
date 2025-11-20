# In agents/agent_executor.py

import os
from langchain.agents import create_openai_tools_agent, AgentType, AgentExecutor, initialize_agent, create_react_agent, create_structured_chat_agent
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferWindowMemory
from langchain import hub # hub is where we get pre-made prompts
from icecream import ic
ic.configureOutput(prefix=f'Debug | ', includeContext=True)

# Import your tools
from .agent_tools import query_document_tool, list_documents_tool, compare_documents_tool

def create_agent_with_memory():
    """
    Creates a modern, conversational "Tools Agent" with memory that is
    compatible with Google models and supports multi-argument tools.
    """
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables.")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        temperature=0,
        google_api_key=gemini_api_key,
    )

    prompt = hub.pull("hwchase17/structured-chat-agent")

    tools = [query_document_tool, list_documents_tool, compare_documents_tool]

    agent = create_structured_chat_agent(llm, tools, prompt)

    # 4. Set up the memory
    memory = ConversationBufferWindowMemory(
        k=5,
        memory_key="chat_history",
        input_key="input",
        return_messages=True
    )

    # 5. Create the final AgentExecutor.
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        memory=memory
    )

    return agent_executor
