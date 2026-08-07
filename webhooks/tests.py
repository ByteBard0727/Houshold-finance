from unittest.mock import patch

from django.http import JsonResponse
from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class GoogleSheetWebhookAuthenticationTests(SimpleTestCase):
    def setUp(self):
        self.url = reverse("expenses_webhook")

    @override_settings(EXPENSES_WEBHOOK_SHARED_SECRET="")
    def test_fails_closed_when_secret_is_not_configured(self):
        response = self.client.post(
            self.url,
            data="{}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)

    @override_settings(EXPENSES_WEBHOOK_SHARED_SECRET="expected-secret")
    def test_rejects_missing_secret(self):
        response = self.client.post(
            self.url,
            data="{}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    @override_settings(EXPENSES_WEBHOOK_SHARED_SECRET="expected-secret")
    def test_rejects_incorrect_secret(self):
        response = self.client.post(
            self.url,
            data="{}",
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="incorrect-secret",
        )

        self.assertEqual(response.status_code, 401)

    @override_settings(EXPENSES_WEBHOOK_SHARED_SECRET="expected-secret")
    def test_rejects_non_json_request(self):
        response = self.client.post(
            self.url,
            data="trigger=true",
            content_type="application/x-www-form-urlencoded",
            HTTP_X_WEBHOOK_SECRET="expected-secret",
        )

        self.assertEqual(response.status_code, 415)

    @override_settings(EXPENSES_WEBHOOK_SHARED_SECRET="expected-secret")
    @patch(
        "webhooks.views._synchronize_google_sheets",
        return_value=JsonResponse({"status": "success"}),
    )
    def test_accepts_valid_authenticated_request(self, synchronize_google_sheets):
        response = self.client.post(
            self.url,
            data="{}",
            content_type="application/json",
            HTTP_X_WEBHOOK_SECRET="expected-secret",
        )

        self.assertEqual(response.status_code, 200)
        synchronize_google_sheets.assert_called_once_with()

# Create your tests here.
