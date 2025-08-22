# docqa/tasks.py

# Import everything this function needs
import os
from neo4j import GraphDatabase
# You'll need to import your actual pipeline functions from rag_pipeline
from rag_pipeline import (
    process_pdf_with_docling, 
    create_fixed_size_chunks,
    generate_embeddings,
    create_vector_index,
    ingest_chunks_into_neo4j
)

# This is our background task. It's just a regular Python function.
def ingestion_task(pdf_filepath):
    """
    A single function that runs the entire ingestion pipeline for a given PDF.
    This will be executed in the background by Django-Q.
    """
    print(f"--- [Django-Q] Starting Ingestion Task for: {pdf_filepath} ---")
    
    # --- Neo4j Connection (The worker needs its own connection) ---
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    filename = os.path.basename(pdf_filepath)
    
    try:
        docling_output = process_pdf_with_docling(pdf_filepath)
        chunks = create_fixed_size_chunks(docling_output)
        
        for chunk in chunks:
            if 'metadata' not in chunk: chunk['metadata'] = {}
            chunk['metadata']['source'] = filename

        chunks_with_embeddings = generate_embeddings(chunks)
        create_vector_index(driver)
        ingest_chunks_into_neo4j(driver, filename, chunks_with_embeddings)
        print(f"--- [Django-Q] Successfully Ingested: {filename} ---")
    
    except Exception as e:
        print(f"--- [Django-Q] ERROR during ingestion for {filename}: {e} ---")
        # You could add more robust error handling here
    
    finally:
        driver.close()
        # Clean up the temporarily saved file
        if os.path.exists(pdf_filepath):
            os.remove(pdf_filepath)
        print(f"--- [Django-Q] Ingestion Task for {filename} finished. ---")
