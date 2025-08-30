# docqa/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.main_interface, name='main_interface'),
    path('api/get_documents/', views.get_documents_json, name='get_documents_json'),
    path('agent/', views.agent_view, name='agent_view'),
]

