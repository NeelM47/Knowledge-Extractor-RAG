# docqa/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.main_interface, name='main_interface'),
]

#urlpatterns = [
#    path('admin/', admin.site.urls),
#    path('', views.main_view, name='main_view'),
#    path('', views.main_interface, name='main_interface'),
#    path('', include('docqa.urls')),
#]
