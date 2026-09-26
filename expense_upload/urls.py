from django.urls import path
from . import views

urlpatterns = [
    path("", views.upload_receipt, name="upload_receipt"),
    path("image/<uuid:receipt_id>/", views.receipt_image, name="receipt_image"),
    path("batch/confirm/", views.confirm_receipt_batch, name="confirm_receipt_batch"),
    path(
        "batch/<uuid:receipt_id>/parse/",
        views.parse_receipt_batch_item,
        name="parse_receipt_batch_item",
    ),
    path(
        "batch/<uuid:receipt_id>/sync/",
        views.sync_receipt_batch_item,
        name="sync_receipt_batch_item",
    ),
    path("<uuid:receipt_id>/confirm/", views.confirm_receipt, name="confirm_receipt"),
    path("<uuid:receipt_id>/sync/", views.sync_receipt, name="sync_receipt"),
]
