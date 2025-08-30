# agent_tools.py

from langchain_core.tools import tool
from neo4j import GraphDatabase
from icecream import ic
import json
import os

# We import the functions we want to turn into tools
from rag_pipeline.core import ask_question_to_rag, get_list_of_ingested_docs, compare_documents_on_topic
from rag_pipeline.utils import get_llm_model

# --- LAZY-LOADED DRIVER FOR THE AGENT ---
# This ensures the agent's tools get a fresh, reliable connection
# every time they are called.
_agent_driver = None

def get_agent_neo4j_driver():
    """A dedicated, lazy-loaded Neo4j driver for the agent's tools."""
    global _agent_driver
    # We check if the driver is None or if the connection has been closed
    if _agent_driver is None or _agent_driver._closed:
        print("--- [Agent] Initializing or re-initializing Neo4j driver for tools ---")
        NEO4J_URI = os.getenv("NEO4J_URI")
        NEO4J_USER = "neo4j"
        NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
        if not all([NEO4J_URI, NEO4J_PASSWORD]):
            raise ValueError("Agent tools cannot connect: Neo4j secrets are missing.")
        _agent_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        _agent_driver.verify_connectivity()
    return _agent_driver

# --- AGENT TOOLS ---
# Each tool now gets the driver "just-in-time" when it's called.

@tool
def compare_documents_tool(document1: str, document2: str, topic: str) -> str:
    """
    Use this tool to compare and contrast what two different documents say about a specific topic.
    The input is the filename of the first document, the filename of the second document, and the topic to compare.
    For example: compare_documents_tool("report-A.pdf", "whitepaper-B.pdf", "bipropellant valves")
    """
    print(f"--- [Agent Tool] Executing compare_documents_tool on topic: '{topic}' ---")
    driver = get_agent_neo4j_driver()
    return compare_documents_on_topic(driver, document1, document2, topic)

@tool
def query_document_tool(question: str, filename: str) -> str:
    """
    Use this tool to answer a specific question about a specific document.
    The input is a question and the filename of the document to search within.
    For example: query_document_tool("What is the main conclusion?", "research_paper.pdf")
    """
    print(f"--- [Agent Tool] Executing query_document_tool for '{filename}' ---")
    driver = get_agent_neo4j_driver()
    return ask_question_to_rag(driver, question, filename)

@tool
def list_documents_tool() -> str: # Return a string for the LLM
    """
    Use this tool to get a list of all the available document filenames that you can query.
    """
    print("--- [Agent Tool] Executing list_documents_tool ---")
    driver = get_agent_neo4j_driver()
    doc_list = get_list_of_ingested_docs(driver)
    if not doc_list:
        return "No documents are currently available in the database."
    return f"The following documents are available: {', '.join(doc_list)}"
