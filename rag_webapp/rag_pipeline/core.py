from docling.document_converter import DocumentConverter
from sentence_transformers import SentenceTransformer
from google.generativeai import configure, GenerativeModel
from google.generativeai.types import GenerationConfig
from typing import List, Dict
from sentence_transformers.cross_encoder import CrossEncoder
from neo4j import GraphDatabase
from icecream import ic
ic.configureOutput(prefix=f'Debug | ', includeContext=True)
import os
import json

from .utils import (
        get_llm_model,
        extract_entities_from_text,
        get_docling_converter,
        get_reranker_model,
        get_embedding_model
) 

def generate_answer_with_context(question: str, context_chunks: List[Dict]) -> str:
    """
    Generates an answer to the question using the provided context chunks and Gemini.

    Args:
        question: The user's question
        context_chunks: List of relevant chunks (with 'text' and other metadata)

    Returns:
        The generated answer
    """
    # Initialize the Gemini model
    model = get_llm_model()

    # Prepare the context by combining all relevant chunks
    context = "\n\n".join([f"Source (Page {chunk['page']}, Chunk {chunk['chunkno']}):\n{chunk['text']}"
                          for chunk in context_chunks])

    # Create the prompt
    prompt = f"""You are an expert assistant helping with document analysis.
    Answer the question based only on the provided context also provide the source of your answer. If you don't know the answer,
    say you don't know rather than making something up.

    Context:
    {context}

    Question: {question}

    Answer:"""

    # Generate the response
    response = model.generate_content(prompt)
    
    #print(response)

    return response.text

def query_llm(driver, question: str, filename: str, top_k: int = 4) -> str:
    """
    End-to-end function that:
    1. Retrieves relevant chunks from Neo4j
    2. Generates an answer using Gemini

    Args:
        driver: Neo4j driver instance
        question: The user's question
        filename: The document filename to search within
        top_k: Number of chunks to retrieve

    Returns:
        The generated answer
    """
    # 1. Load the embedding model
    embedding_model = get_embedding_model()

    # 2. Retrieve relevant chunks
    relevant_chunks = query_neo4j_for_chunks(driver, embedding_model, user_query, top_k)

    #for i, chunk in enumerate(relevant_chunks):
    #    print(f"\nResult {i+1} (Score: {chunk['score']:.4f}, Page: {chunk['page']}):")
    #    print(chunk['text'][:])

    if not relevant_chunks:
        return "No relevant information found in the document."

    # 3. Generate answer using Gemini
    answer = generate_answer_with_context(question, relevant_chunks)

    return answer

def process_pdf_with_docling(pdf_path):
    """
    Processes a PDF file using Docling to extract its content into a structured format.

    Args:
        pdf_path (str): The file path to the PDF document.

    Returns:
        A dictionary representing the structured document content, or None if an error occurs.
    """

    # Check if the file exists
    if not os.path.exists(pdf_path):
        print(f"Error: The file '{pdf_path}' was not found.")
        return None

    #print("Initializing DocumentConverter. This may take a moment on the first run...")
    
    try:
        # 1. Initialize the DocumentConverter
        # The first time this runs, it will download the necessary models.
        converter = get_docling_converter()
        
        # 2. Convert the document
        # Docling can take a file path directly.
        #print(f"Processing '{pdf_path}' with Docling...")
        result = converter.convert(pdf_path)
        #print("Conversion complete.")
        
        # 3. Export to a structured format (e.g., a Python dictionary or Markdown)
        # We'll use to_dict() to see the rich structure.
        # For simple text, you could also use export_to_markdown()
        document_dict = result.document.export_to_dict()
        
        return document_dict

    except Exception as e:
        print(f"An error occurred while processing the PDF with Docling: {e}")
        return None

def create_fixed_size_chunks(data, filename, chunk_size=1000, chunk_overlap=150):

    page_chunks = {}
    for text_block in data.get('texts', []):
        if text_block.get('label') == 'text':
            prov = text_block.get('prov', [{}])[0]
            page_number = prov.get('page_no')
            content = text_block.get('text', '')
            if page_number and content:
                page_chunks.setdefault(page_number, []).append(content.strip())

    final_chunks = []
    for page_num, texts in sorted(page_chunks.items()):
        page_content = '\n\n'.join(texts)
        if not page_content:
            continue

        start_index = 0
        while start_index < len(page_content):
            end_index = min(start_index + chunk_size, len(page_content))
            chunk = page_content[start_index:end_index]
            final_chunks.append({
                "page_number": page_num,
                "text": chunk,
                "chunk_on_page": len(final_chunks) + 1,
                "source": filename
            })
            start_index += chunk_size - chunk_overlap

    return final_chunks

def generate_embeddings(chunks):
    """
    Generates embeddings for a list of chunk dictionaries.

    Args:
        chunks (list): The list of chunks from the previous step.

    Returns:
        list: The same list of chunks, with an 'embedding' key added to each.
    """
    # Load a pre-trained sentence transformer model.
    # The first time you run this, it will download the model.
    model = get_embedding_model()

    # It's more efficient to embed all texts at once
    texts_to_embed = [chunk['text'] for chunk in chunks]

    #print("Generating embeddings... This may take a moment.")
    # Generate embeddings
    embeddings = model.encode(texts_to_embed, show_progress_bar=True)

    # Add the generated embedding to its corresponding chunk
    for i, chunk in enumerate(chunks):
        chunk['embedding'] = embeddings[i].tolist()
    return chunks

def create_vector_index(driver):
    """Creates a vector index in Neo4j for the Chunk embeddings."""
    index_query = """
    CREATE VECTOR INDEX `chunk_embeddings` IF NOT EXISTS
    FOR (c:Chunk) ON (c.embedding)
    OPTIONS { indexConfig: {
        `vector.dimensions`: 384,
        `vector.similarity_function`: 'cosine'
    }}
    """
    with driver.session() as session:
        session.run(index_query)
        #print("Vector index created or already exists.")

def ingest_chunks_into_neo4j(driver, filename, chunks_with_embeddings):
    """
    Ingests document and chunk data into Neo4j, ensuring each chunk
    is tagged with its source filename.
    """
    ingest_query = """
    MERGE (d:Document {filename: $filename})
    WITH d
    UNWIND $chunks AS chunk_data
    CREATE (c:Chunk {
        text: chunk_data.text,
        source: chunk_data.source, // <-- The new and important line
        page_number: chunk_data.page_number,
        chunk_on_page: chunk_data.chunk_on_page,
        embedding: chunk_data.embedding
    })
    
    // This part also remains the same: connect the document to its chunk
    CREATE (d)-[:HAS_CHUNK]->(c)
    WITH c, chunk_data
    UNWIND chunk_data.entities AS entity_name
    MERGE (e:Entity {name: entity_name})
    CREATE (c)-[:MENTIONS]->(e)
    """
    
    # The session execution block remains the same
    with driver.session(database="neo4j") as session: # It's good practice to specify the database
        session.run(ingest_query, filename=filename, chunks=chunks_with_embeddings)
        #print(f"Ingested {len(chunks_with_embeddings)} chunks for document '{filename}'.")

def query_neo4j_for_chunks(driver, model, query_text, top_k=3):
    """Finds the most relevant chunks in Neo4j for a given query."""
    # First, create an embedding for the user's query
    query_embedding = model.encode(query_text).tolist()

    query = """
    CALL db.index.vector.queryNodes('chunk_embeddings', $top_k, $embedding) YIELD node, score
    RETURN node.text AS text, node.page_number AS page, node.chunk_on_page AS chunkno, score
    """

    with driver.session() as session:
        results = session.run(query, top_k=top_k, embedding=query_embedding)
        return [{"text": record["text"], "page": record["page"], "chunkno": record["chunkno"], "score": record["score"]} for record in results]

def process_and_ingest_pdf(driver, pdf_filepath):

    """A single function that runs the entire ingestion pipeline for a given PDF."""
    #print(f"--- Starting Ingestion Pipeline for: {pdf_filepath} ---")
    filename = os.path.basename(pdf_filepath)

    docling_output = process_pdf_with_docling(pdf_filepath)

    if not docling_output:
        raise ValueError("Docling failed to process the PDF.")

    chunks = create_fixed_size_chunks(docling_output, filename)

    # Add source filename to each chunk. This is crucial.
    for chunk in chunks:

        chunk['entities'] = extract_entities_from_text(chunk['text'])

        if 'metadata' not in chunk: # Make sure metadata key exists
            chunk['metadata'] = {}
        chunk['metadata']['source'] = filename

    chunks_with_embeddings = generate_embeddings(chunks)

    # Make sure vector index exists before ingesting
    create_vector_index(driver) # Assuming you have this function

    ingest_chunks_into_neo4j(driver, filename, chunks_with_embeddings)

    #print(f"--- Successfully Ingested: {filename} ---")

def rerank_chunks(question, chunks):
    """Re-ranks a list of chunks using a more powerful CrossEncoder model."""
    #model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)

    model = get_reranker_model()

    # The model expects a list of [question, chunk_text] pairs
    pairs = [[question, chunk['text']] for chunk in chunks]

    scores = model.predict(pairs)

    # Combine chunks with their new scores and sort
    for i, chunk in enumerate(chunks):
        chunk['rerank_score'] = scores[i]

    return sorted(chunks, key=lambda x: x['rerank_score'], reverse=True)

def ask_question_to_rag(driver, question, filename, top_k=3):

    """A single function that runs the entire querying pipeline."""
    #print(f"--- Querying {filename} with question: '{question}' ---")

    # This calls the query function you already wrote
    EMBEDDING_MODEL = get_embedding_model()

    #relevant_chunks = query_neo4j_for_chunks(driver, EMBEDDING_MODEL, question, top_k)
    relevant_chunks = hybrid_retrieval(driver, EMBEDDING_MODEL, question, filename)

    if not relevant_chunks:
        return "I could not find any relevant information in the document to answer your question."

    #ic("CANDIDATE chunks from initial retrieval (Top 10):")
    #for i, chunk in enumerate(relevant_chunks):
        #print(f" {i+1}. Page {chunk.get('page', 'N/A')}, '{chunk['text'][:80]}...'")

    reranked_chunks = rerank_chunks(question, relevant_chunks)

    #ic("RE-RANKED chunks (sorted by new score):")
    #for i, chunk in enumerate(reranked_chunks):
        # We print the new rerank_score to see the new order
        #print(f"  {i+1}. Page {chunk.get('page', 'N/A')}, Score: {chunk.get('rerank_score', 0):.4f}, '{chunk['text'][:80]}...'")
    
    relevant_chunks = reranked_chunks[:top_k]

    # This calls the LLM function you already wrote
    answer = generate_answer_with_context(question, relevant_chunks)
    return answer

def extract_entities_from_text(text: str) -> list:
    """Uses the LLM to extract key entities from a text chunk."""
    model = get_llm_model() # Your lazy-loader for Gemini

    prompt = (
        "You are a helpful AI assistant for knowledge graph construction.\n"
        "From the following text, extract the key entities (people, organizations, locations, technical concepts, projects).\n"
        "Return the result as a JSON list of strings. Example: [\"NASA\", \"Aerojet Rocketdyne\", \"bipropellant valve\"]\n\n"
        f"--- TEXT ---\n{text}\n\n"
        "--- ENTITIES (JSON List) ---\n"
    )

    try:
        response = model.generate_content(prompt)
        #ic(response.text)
        # Clean up the response to get a valid JSON list
        json_text = response.text.strip().replace("```json", "").replace("```", "")
        entities = json.loads(json_text)
        return entities
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Could not parse entities from LLM response: {e}")
        return []

def get_list_of_ingested_docs(driver):
    """Queries Neo4j to get a list of all processed document filenames."""
    query = "MATCH (d:Document) RETURN d.filename AS filename ORDER BY d.filename"
    with driver.session(database="neo4j") as session:
        results = session.run(query)
        return [record["filename"] for record in results]

def hybrid_retrieval(driver, model, question, filename, top_k=5):
    """Performs a hybrid search using both vectors and graph entities."""
    
    # 1. Extract entities from the user's question
    question_entities = extract_entities_from_text(question)
    
    # 2. Embed the user's question
    query_embedding = model.encode(question).tolist()

    hybrid_query = """
    // Part 1: Vector Search
    CALL db.index.vector.queryNodes('chunk_embeddings', $top_k, $embedding) YIELD node AS vector_node, score
    WHERE vector_node.source = $filename
    
    // Part 2: Graph Search (find chunks that mention entities from the question)
    // Use OPTIONAL MATCH so we still get results if no entities are found
    WITH vector_node, score
    OPTIONAL MATCH (entity:Entity)<-[:MENTIONS]-(graph_node:Chunk)
    WHERE entity.name IN $question_entities AND graph_node.source = $filename

    // Collect all unique nodes from both searches
    WITH collect(DISTINCT vector_node) + collect(DISTINCT graph_node) AS all_nodes
    UNWIND all_nodes AS node
    
    // Return distinct nodes with their text and page number
    RETURN DISTINCT node.text AS text, node.page_number AS page, node.chunk_on_page AS chunkno
    LIMIT 10 // Return a larger set of candidates for re-ranking
    """
    
    with driver.session(database="neo4j") as session:
        results = session.run(
            hybrid_query, 
            top_k=top_k, 
            embedding=query_embedding, 
            filename=filename, 
            question_entities=question_entities
        )
        return [{"text": record["text"], "page": record["page"], "chunkno": record["chunkno"]} for record in results]

def compare_documents_on_topic(driver, doc1_filename: str, doc2_filename: str, topic: str) -> str:
    """
    Retrieves context about a topic from two different documents and uses an LLM
    to generate a comparative summary.

    Args:
        driver: The active Neo4j driver instance.
        doc1_filename: The filename of the first document.
        doc2_filename: The filename of the second document.
        topic: The topic to find and compare in both documents.

    Returns:
        A string containing the comparative summary.
    """
    print(f"--- [Core Pipeline] Comparing '{doc1_filename}' and '{doc2_filename}' on topic: '{topic}' ---")

    # --- Step 1: Gather Context from Both Documents ---
    # We will reuse our powerful ask_question_to_rag function to get the
    # most relevant, re-ranked context for the topic from each document.
    # The "question" we ask is simply the topic itself.

    print(f"Gathering context from '{doc1_filename}'...")
    context1 = ask_question_to_rag(driver, question=topic, filename=doc1_filename)

    print(f"Gathering context from '{doc2_filename}'...")
    context2 = ask_question_to_rag(driver, question=topic, filename=doc2_filename)

    # --- Step 2: Synthesize a Comparison with the LLM ---
    # Now we build a new, specialized prompt for the comparison task.
    llm = get_llm_model() # Get the lazy-loaded Gemini model

    # It's good practice to check if the context was found before calling the LLM
    if "No relevant information found" in context1 and "No relevant information found" in context2:
        return f"I could not find any information about '{topic}' in either document."

    comparison_prompt = (
        "You are a helpful summarization and analysis assistant.\n"
        "Your task is to compare and contrast the information provided from two different documents about a specific topic.\n"
        "Analyze the context from each document and provide a concise summary of the similarities and differences.\n"
        "If information is only present in one document, state that clearly.\n\n"
        f"--- TOPIC OF COMPARISON ---\n{topic}\n\n"
        f"--- CONTEXT FROM: {doc1_filename} ---\n{context1}\n\n"
        f"--- CONTEXT FROM: {doc2_filename} ---\n{context2}\n\n"
        "--- COMPARATIVE SUMMARY ---\n"
    )

    try:
        # Use a generation config for better control
        generation_config = GenerationConfig(
            temperature=0.2 # Factual and concise
        )
        response = llm.generate_content(comparison_prompt, generation_config=generation_config)
        return response.text
    except Exception as e:
        print(f"An error occurred during LLM comparison: {e}")
        return "There was an error while generating the comparison."
