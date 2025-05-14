from django.urls import path
from . import views

urlpatterns = [
    path("", views.display_sheet_data, name="display_sheet_data"),
    path("", views.upload, name="upload"),
    
]