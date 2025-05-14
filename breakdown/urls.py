from django.urls import path
from . import views

urlpatterns = [
    path("", views.breakdown, name="breakdown")
]