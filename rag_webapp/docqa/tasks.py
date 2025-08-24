# docqa/tasks.py

# Import everything this function needs
import os
from neo4j import GraphDatabase

# You'll need to import your actual pipeline functions from rag_pipeline
from rag_pipeline.core import process_and_ingest_pdf

# This is our background task. It's just a regular Python function.

def ingestion_task(pdf_filepath):
    """
    A single function that runs the entire ingestion pipeline for a given PDF.
    This will be executed in the background by Django-Q.
    """
    #print(f"--- [Django-Q] Starting Ingestion Task for: {pdf_filepath} ---")
    
    # --- Neo4j Connection (The worker needs its own connection) ---
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

    #driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    driver = None
    
    filename = os.path.basename(pdf_filepath)
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        process_and_ingest_pdf(driver, pdf_filepath)
        filename = os.path.basename(pdf_filepath)
        print(f"--- [Django-Q] Successfully Ingested: {filename} ---")
    
    except Exception as e:
        filename = os.path.basename(pdf_filepath)
        print(f"--- [Django-Q] ERROR during ingestion for {filename}: {e} ---")
        # You could add more robust error handling here
    
    finally:
        if driver:
            driver.close()
        # Clean up the temporarily saved file
        if os.path.exists(pdf_filepath):
            print(f"--- [Django-Q] Cleaning up temporary file: {pdf_filepath} ---")
            os.remove(pdf_filepath)

        print(f"--- [Django-Q] Ingestion Task for {filename} finished. ---")
