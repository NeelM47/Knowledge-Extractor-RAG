# rag_pipeline/utils.py

import json
from google.generativeai import configure, GenerativeModel
from google.generativeai.types import GenerationConfig
from sentence_transformers import SentenceTransformer
from sentence_transformers.cross_encoder import CrossEncoder
from docling.document_converter import DocumentConverter
import os

# --- This file is now the home for all lazy-loaded models ---
LLM_MODEL = None
EMBEDDING_MODEL = None
DOCLING_CONVERTER = None
RERANKER_MODEL = None
GEMINI_API_KEY = None

def get_embedding_model():
    """Loads the embedding model if it hasn't been loaded yet."""
    global EMBEDDING_MODEL
    if EMBEDDING_MODEL is None:
        #print("Lazy loading embedding model for the first time...")
        EMBEDDING_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    return EMBEDDING_MODEL

def get_llm_model():
    """Loads the LLM if it hasn't been loaded yet."""
    global LLM_MODEL
    if LLM_MODEL is None:
        #print("Lazy loading Generative Model for the first time...")
        # Ensure your API key is set as an environment variable in your Space
        configure(api_key=os.getenv("GEMINI_API_KEY"))
        LLM_MODEL = GenerativeModel("gemini-2.5-pro")
    return LLM_MODEL

def get_docling_converter():
    """Loads the Docling converter if it hasn't been loaded yet."""
    global DOCLING_CONVERTER
    if DOCLING_CONVERTER is None:
        #print("Lazy loading Docling converter for the first time...")
        DOCLING_CONVERTER = DocumentConverter()
    return DOCLING_CONVERTER

def get_reranker_model():
    """Loads and caches the CrossEncoder re-ranking model."""
    global RERANKER_MODEL
    if RERANKER_MODEL is None:
        print("--- LAZY LOADING: CrossEncoder model ---")
        RERANKER_MODEL = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
    return RERANKER_MODEL

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

    #ic(prompt)

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


