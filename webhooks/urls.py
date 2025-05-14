from django.urls import path
from webhooks import views

urlpatterns = [
    path("", views.google_sheet_webhook, name="expenses_webhook"),  # ✅ Webhook URL remains the same
]