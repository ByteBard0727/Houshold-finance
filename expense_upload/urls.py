from django.urls import path
from . import views

urlpatterns = [
    path("", views.upload_receipt, name="upload_receipt"),
    path("<uuid:receipt_id>/confirm/", views.confirm_receipt, name="confirm_receipt"),
    path("<uuid:receipt_id>/sync/", views.sync_receipt, name="sync_receipt"),
]
