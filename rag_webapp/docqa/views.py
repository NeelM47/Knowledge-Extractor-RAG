# docqa/views.py

import os
import json
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse
from neo4j import GraphDatabase
from dotenv import load_dotenv
from django.contrib import messages
from django_q.tasks import async_task
from django.views.decorators.csrf import csrf_exempt
from agent.agent_handler import create_agent_with_memory
from icecream import ic
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

from rag_pipeline.core import ask_question_to_rag, get_list_of_ingested_docs

_driver = None

agent_executor = create_agent_with_memory()

@csrf_exempt
def agent_view(request):
    """A simple API view to interact with the LangChain agent."""
    if request.method == 'POST':
        data = json.loads(request.body)
        user_input = data.get('user_input', '').strip()

        if user_input:
            try:
                result = agent_executor.invoke({
                    "input": user_input
                    })
                return JsonResponse({
                   "input": result["input"],
                   "output": result["output"],
                })

            except Exception as e:
                print(f"Other error: {e}")
                return JsonResponse({"error": "Server error"}, status=500)

        else:
            return JsonResponse({"error": "Invalid request"}, status=400)
                
    else:
        return JsonResponse({"error": "Invalid request"}, status=400)

def get_neo4j_driver():
    """
    This function creates a Neo4j driver instance if one doesn't exist,
    or returns the existing one. This is called a singleton pattern.
    """
    global _driver
    if _driver is None:
        print("--- Initializing Neo4j driver for the first time ---")
        try:
            NEO4J_URI=os.getenv("NEO4J_URI")
            NEO4J_USER="neo4j"
            NEO4J_PASSWORD=os.getenv("NEO4J_PASSWORD")
            GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")

            if not all([NEO4J_URI, NEO4J_PASSWORD]):
                raise ValueError("NEO4J_URI or NEO4J_PASSWORD secrets are not set.")

            _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            _driver.verify_connectivity()
            print("--- Neo4j connection successful ---")
        except Exception as e:
            print(f"--- FAILED to connect to Neo4j: {e} ---")
            raise e
    return _driver

def main_interface(request):
    """
    This single view handles all user interactions:
    - Displaying the main page.
    - Processing PDF uploads.
    - Handling user questions.
    """
    context = {
            'answer': "", 
            'last_question': "",
            'last_doc': "",
            'ingested_docs':[], 
            'show_rag_answer': False
        }
    try:
         
        driver = get_neo4j_driver()

        # Default context variables
        context['ingested_docs'] = get_list_of_ingested_docs(driver)

        if request.method == 'POST':
            # --- Logic for handling PDF upload form ---
            if 'upload_button' in request.POST and request.FILES.get('pdf_file'):
                pdf_file = request.FILES['pdf_file']
                fs = FileSystemStorage()
                filename = fs.save(pdf_file.name, pdf_file)
                uploaded_file_path = fs.path(filename)

                async_task(
                        'docqa.tasks.ingestion_task',
                        uploaded_file_path
                        )

                messages.success(request, f"'{pdf_file.name}' has been submitted for processing. It will be available shortly.")
                
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
                    context['show_rag_answer'] = True

    except Exception as e:
        print(f"A fatal error occurred in the main view: {e}")
        return render(request, 'docqa/error.html', {'error_message': str(e)})

    return render(request, 'docqa/interface.html', context)

def get_documents_json(request):
    """
    An API endpoint that returns the list of ingested documents as JSON.
    This is called by the JavaScript on the front-end to dynamically update the dropdown.
    """
    try:
        driver = get_neo4j_driver()
        doc_list = get_list_of_ingested_docs(driver)
        return JsonResponse({'documents': doc_list})
    except Exception as e:
        # Return an error as JSON if the database connection fails
        return JsonResponse({'error': str(e)}, status=500)

