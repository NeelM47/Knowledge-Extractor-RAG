# docqa/views.py

from django.http import HttpResponse

# This view has NO external dependencies. It only uses Django.
# It does not connect to Neo4j or load any models.
def main_interface(request):
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Debug Test</title></head>
    <body>
        <h1>Test Successful!</h1>
        <p>If you can see this page, the core Django/Gunicorn/Docker setup is working correctly.</p>
        <p>The startup crash must be caused by the code we removed (the RAG pipeline logic).</p>
    </body>
    </html>
    """
    return HttpResponse(html_content)
