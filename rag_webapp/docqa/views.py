# docqa/views.py

from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

# Import our master functions from the refactored pipeline
from rag_pipeline import process_and_ingest_pdf, ask_question_to_rag, get_list_of_ingested_docs

# --- Neo4j Connection ---
NEO4J_URI=os.getenv("NEO4J_URI")
NEO4J_USER="neo4j"
NEO4J_PASSWORD=os.getenv("NEO4J_PASSWORD")
GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")

print(f"DEBUG: NEO4J_URI        = '{NEO4J_URI}' (Type: {type(NEO4J_URI)})")
print(f"DEBUG: NEO4J_PASSWORD   = '...first 3 chars...{str(NEO4J_PASSWORD)[:3]}' (Type: {type(NEO4J_PASSWORD)})")
print(f"DEBUG: GEMINI_API_KEY   = '...first 3 chars...{str(GEMINI_API_KEY)[:3]}' (Type: {type(GEMINI_API_KEY)})")
print("--- END OF DEBUGGING BLOCK ---")
print("="*50)

# This check will now tell us exactly which variable is missing
if not NEO4J_URI or not NEO4J_PASSWORD or not GEMINI_API_KEY:
    raise ValueError(
        "CRITICAL ERROR: One or more required environment variables are not set. "
        "Please check your repository secrets in the Hugging Face Space settings."
    )

_driver = None

def get_neo4j_driver():
    """
    This function creates a Neo4j driver instance if one doesn't exist,
    or returns the existing one. This is called a singleton pattern.
    """
    global _driver
    if _driver is None:
        print("--- Initializing Neo4j driver for the first time ---")
        try:
            _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            _driver.verify_connectivity()
            print("--- Neo4j connection successful ---")
        except Exception as e:
            print(f"--- FAILED to connect to Neo4j: {e} ---")
            raise e
    return _driver

#driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def main_interface(request):
    """
    This single view handles all user interactions:
    - Displaying the main page.
    - Processing PDF uploads.
    - Handling user questions.
    """
    try:
        
        driver = get_neo4j_driver()

        # Default context variables
        context = {
            'answer': "", 'last_question': "",
            'last_doc': "",
            'ingested_docs': get_list_of_ingested_docs(driver) # Get list for dropdown
        }

        if request.method == 'POST':
            # --- Logic for handling PDF upload form ---
            if 'upload_button' in request.POST and request.FILES.get('pdf_file'):
                pdf_file = request.FILES['pdf_file']
                fs = FileSystemStorage()
                filename = fs.save(pdf_file.name, pdf_file)
                uploaded_file_path = fs.path(filename)

                try:
                    # Call our main ingestion function
                    process_and_ingest_pdf(driver, uploaded_file_path)
                except Exception as e:
                    print(f"An error occurred during ingestion: {e}")
                finally:
                    # Clean up the temporarily saved file
                    os.remove(uploaded_file_path)
                
                # Redirect to the same page to show the updated doc list
                return redirect('main_interface')

            # --- Logic for handling question form ---
            if 'query_button' in request.POST:
                question = request.POST.get('question', '')
                document = request.POST.get('document', '')
                
                if question and document:
                    # Call our main query function
                    answer = ask_question_to_rag(driver, question, document)
                    # Update context to display the results
                    context['answer'] = answer
                    context['last_question'] = question
                    context['last_doc'] = document

        return render(request, 'docqa/interface.html', context)

    except Exception as e:
        print(f"A fatal error occurred in the main view: {e}")
        return render(request, 'docqa/error.html', {'error_message': str(e)})


