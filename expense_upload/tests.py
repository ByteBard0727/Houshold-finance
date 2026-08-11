import base64
import tempfile
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings
from django.urls import reverse

from .forms import ReceiptUploadForm
from .models import Receipt
from .services.extraction import (
    ReceiptExtractionError,
    GeminiReceiptProvider,
    normalize_extraction,
    process_receipt,
)
from .services.sheet_sync import (
    AppsScriptReceiptProvider,
    ReceiptSyncError,
    process_receipt_sync,
)


PNG_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "AScY42YAAAAASUVORK5CYII="
)


@override_settings(RECEIPT_MAX_UPLOAD_SIZE=10 * 1024 * 1024)
class ReceiptUploadFormTests(SimpleTestCase):
    def test_mpo_encoded_jpeg_is_accepted(self):
        image = Mock(size=1024, image=Mock(format="MPO"))
        form = ReceiptUploadForm()
        form.cleaned_data = {"images": [image]}

        self.assertEqual(form.clean_images(), [image])

    def test_rejection_reports_detected_image_format(self):
        image = Mock(size=1024, image=Mock(format="WEBP"))
        form = ReceiptUploadForm()
        form.cleaned_data = {"images": [image]}

        with self.assertRaisesMessage(ValidationError, "Detected format: WEBP"):
            form.clean_images()


class ReceiptUploadTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            RECEIPT_MAX_UPLOAD_SIZE=10 * 1024 * 1024,
        )
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.media_directory.cleanup()

    def test_upload_page_is_available(self):
        response = self.client.get(reverse("upload_receipt"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload receipts")
        self.assertContains(response, 'id="receipt-upload-form"')
        self.assertContains(response, 'id="receipt-upload-button"')
        self.assertContains(response, 'button.disabled = true')
        self.assertContains(response, 'Uploading and parsing…')

    @patch("expense_upload.views.process_receipt")
    def test_valid_image_starts_receipt_processing(self, process_receipt_mock):
        image = SimpleUploadedFile(
            "household-receipt.png",
            PNG_IMAGE,
            content_type="image/png",
        )

        response = self.client.post(reverse("upload_receipt"), {"images": image})

        receipt = Receipt.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(receipt.status, Receipt.Status.UPLOADED)
        process_receipt_mock.assert_called_once_with(receipt)
        self.assertIsNone(receipt.extracted_json)
        self.assertIsNone(receipt.confirmed_json)
        self.assertContains(response, str(receipt.id))
        self.assertEqual(receipt.image.name, f"receipts/{receipt.id}.png")

    def test_non_image_is_rejected(self):
        upload = SimpleUploadedFile(
            "not-a-receipt.txt",
            b"not an image",
            content_type="text/plain",
        )

        response = self.client.post(reverse("upload_receipt"), {"images": upload})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid image")
        self.assertFalse(Receipt.objects.exists())

    @override_settings(RECEIPT_MAX_UPLOAD_SIZE=10)
    def test_oversized_image_is_rejected(self):
        image = SimpleUploadedFile(
            "large-receipt.png",
            PNG_IMAGE,
            content_type="image/png",
        )

        response = self.client.post(reverse("upload_receipt"), {"images": image})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no larger than 0 MB")
        self.assertFalse(Receipt.objects.exists())

    @patch("expense_upload.views.process_receipt")
    def test_multiple_images_start_review_queue_in_upload_order(self, process_mock):
        def mark_extracted(receipt):
            receipt.status = Receipt.Status.EXTRACTED
            receipt.extracted_json = {
                "store_name": "店",
                "receipt_date": "2026-08-07",
                "total_amount": 100,
                "category": "Stuff",
                "items": [],
            }
            receipt.save(update_fields=["status", "extracted_json"])

        process_mock.side_effect = mark_extracted
        first = SimpleUploadedFile("first.png", PNG_IMAGE, content_type="image/png")
        second = SimpleUploadedFile("second.png", PNG_IMAGE, content_type="image/png")

        response = self.client.post(
            reverse("upload_receipt"),
            {"images": [first, second]},
        )

        receipts = list(Receipt.objects.order_by("created_at"))
        self.assertEqual(len(receipts), 2)
        self.assertRedirects(
            response,
            reverse("confirm_receipt", args=[receipts[0].id]),
        )
        self.assertEqual(
            self.client.session["receipt_review_queue"],
            [str(receipt.id) for receipt in receipts],
        )
        self.assertEqual(process_mock.call_count, 2)


class StubProvider:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.call = None

    def extract(self, image_bytes, mime_type):
        self.call = (image_bytes, mime_type)
        if self.error:
            raise self.error
        return self.result


class ReceiptExtractionTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        image = SimpleUploadedFile("receipt.png", PNG_IMAGE, content_type="image/png")
        self.receipt = Receipt.objects.create(image=image)

    def tearDown(self):
        self.media_override.disable()
        self.media_directory.cleanup()

    def test_success_stores_normalized_extraction(self):
        provider = StubProvider({
            "store_name": "西友",
            "receipt_date": "2026-08-02",
            "total_amount": 3240,
            "category": "Food",
            "items": ["牛乳", " 卵 "],
        })

        succeeded = process_receipt(self.receipt, provider=provider)

        self.receipt.refresh_from_db()
        self.assertTrue(succeeded)
        self.assertEqual(self.receipt.status, Receipt.Status.EXTRACTED)
        self.assertEqual(self.receipt.extracted_json["store_name"], "西友")
        self.assertEqual(self.receipt.extracted_json["items"], ["牛乳", "卵"])
        self.assertEqual(provider.call[1], "image/png")

    def test_provider_failure_is_recorded_without_raising(self):
        provider = StubProvider(error=ReceiptExtractionError("Gemini unavailable."))

        succeeded = process_receipt(self.receipt, provider=provider)

        self.receipt.refresh_from_db()
        self.assertFalse(succeeded)
        self.assertEqual(self.receipt.status, Receipt.Status.EXTRACTION_FAILED)
        self.assertEqual(self.receipt.error_message, "Gemini unavailable.")
        self.assertIsNone(self.receipt.extracted_json)

    def test_invalid_category_defaults_to_stuff(self):
        normalized = normalize_extraction({
            "store_name": "店",
            "receipt_date": "2026-08-02",
            "total_amount": 1000,
            "category": "Unknown",
            "items": [],
        })

        self.assertEqual(normalized["category"], "Stuff")

    def test_invalid_financial_fields_fail_validation(self):
        with self.assertRaises(ReceiptExtractionError):
            normalize_extraction({
                "store_name": "店",
                "receipt_date": "not-a-date",
                "total_amount": 1000,
                "category": "Food",
                "items": [],
            })


class ReceiptConfirmationTests(TestCase):
    extracted_data = {
        "store_name": "西友",
        "receipt_date": "2026-08-02",
        "total_amount": 3240,
        "category": "Food",
        "items": ["牛乳", "卵"],
    }

    def setUp(self):
        self.receipt = Receipt.objects.create(
            image="receipts/test.png",
            status=Receipt.Status.EXTRACTED,
            extracted_json=self.extracted_data.copy(),
        )
        self.url = reverse("confirm_receipt", args=[self.receipt.id])

    def test_confirmation_page_is_prepopulated_from_extraction(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "西友")
        self.assertContains(response, "2026-08-02")
        self.assertContains(response, "3240")
        self.assertContains(response, "牛乳")

    def test_valid_corrections_are_saved_separately_and_confirmed(self):
        original_extraction = self.receipt.extracted_json.copy()

        response = self.client.post(
            self.url,
            {
                "store_name": "ライフ",
                "receipt_date": "2026-08-03",
                "total_amount": "3500",
                "category": "Stuff",
                "items": "ティッシュ\n\n トイレットペーパー ",
            },
        )

        self.assertRedirects(response, self.url)
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, Receipt.Status.CONFIRMED)
        self.assertEqual(self.receipt.extracted_json, original_extraction)
        self.assertEqual(
            self.receipt.confirmed_json,
            {
                "store_name": "ライフ",
                "receipt_date": "2026-08-03",
                "total_amount": 3500,
                "category": "Stuff",
                "items": ["ティッシュ", "トイレットペーパー"],
            },
        )

        result = self.client.get(self.url)
        self.assertContains(result, "Receipt confirmed")
        self.assertContains(result, "Google Sheets has not been updated yet")

    def test_invalid_financial_values_and_category_are_rejected(self):
        response = self.client.post(
            self.url,
            {
                "store_name": "店",
                "receipt_date": "not-a-date",
                "total_amount": "-1",
                "category": "Unknown",
                "items": "品物",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid date")
        self.assertContains(response, "Ensure this value is greater than or equal to 0")
        self.assertContains(response, "Select a valid choice")
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, Receipt.Status.EXTRACTED)
        self.assertIsNone(self.receipt.confirmed_json)

    def test_unknown_receipt_returns_404(self):
        response = self.client.get(
            reverse("confirm_receipt", args=["00000000-0000-0000-0000-000000000000"])
        )

        self.assertEqual(response.status_code, 404)

    def test_receipt_not_ready_for_confirmation_returns_404(self):
        self.receipt.status = Receipt.Status.EXTRACTION_FAILED
        self.receipt.save(update_fields=["status"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_confirmed_receipt_cannot_be_submitted_again(self):
        self.receipt.status = Receipt.Status.CONFIRMED
        self.receipt.confirmed_json = self.extracted_data.copy()
        self.receipt.save(update_fields=["status", "confirmed_json"])

        response = self.client.post(self.url, self.extracted_data)

        self.assertEqual(response.status_code, 404)


class StubSyncProvider:
    def __init__(self, error=None):
        self.error = error
        self.call = None

    def sync(self, receipt_id, confirmed_data):
        self.call = (receipt_id, confirmed_data)
        if self.error:
            raise self.error


class ReceiptSheetSyncTests(TestCase):
    confirmed_data = {
        "store_name": "西友",
        "receipt_date": "2026-08-02",
        "total_amount": 3240,
        "category": "Food",
        "items": ["牛乳"],
    }

    def setUp(self):
        self.receipt = Receipt.objects.create(
            image="receipts/test.png",
            status=Receipt.Status.CONFIRMED,
            extracted_json=self.confirmed_data.copy(),
            confirmed_json=self.confirmed_data.copy(),
        )
        self.sync_url = reverse("sync_receipt", args=[self.receipt.id])

    def test_successful_sync_sets_synced(self):
        provider = StubSyncProvider()

        succeeded = process_receipt_sync(self.receipt, provider=provider)

        self.receipt.refresh_from_db()
        self.assertTrue(succeeded)
        self.assertEqual(self.receipt.status, Receipt.Status.SYNCED)
        self.assertEqual(provider.call[0], self.receipt.id)
        self.assertEqual(provider.call[1], self.confirmed_data)

    def test_sync_failure_is_recorded_without_losing_confirmation(self):
        provider = StubSyncProvider(error=ReceiptSyncError("Apps Script unavailable."))

        succeeded = process_receipt_sync(self.receipt, provider=provider)

        self.receipt.refresh_from_db()
        self.assertFalse(succeeded)
        self.assertEqual(self.receipt.status, Receipt.Status.SYNC_FAILED)
        self.assertEqual(self.receipt.error_message, "Apps Script unavailable.")
        self.assertEqual(self.receipt.confirmed_json, self.confirmed_data)

    @patch("expense_upload.views.process_receipt_sync")
    def test_sync_action_invokes_service_and_redirects(self, sync_mock):
        response = self.client.post(self.sync_url)

        self.assertRedirects(
            response,
            reverse("confirm_receipt", args=[self.receipt.id]),
        )
        sync_mock.assert_called_once()
        self.assertEqual(sync_mock.call_args.args[0].id, self.receipt.id)

    @patch("expense_upload.views.process_receipt_sync", return_value=True)
    def test_successful_batch_sync_advances_to_next_receipt(self, sync_mock):
        next_receipt = Receipt.objects.create(
            image="receipts/next.png",
            status=Receipt.Status.EXTRACTED,
            extracted_json=self.confirmed_data.copy(),
        )
        session = self.client.session
        session["receipt_review_queue"] = [
            str(self.receipt.id),
            str(next_receipt.id),
        ]
        session.save()

        response = self.client.post(self.sync_url)

        self.assertRedirects(
            response,
            reverse("confirm_receipt", args=[next_receipt.id]),
        )
        sync_mock.assert_called_once()

    @patch("expense_upload.views.process_receipt_sync")
    def test_sync_failed_receipt_can_be_retried(self, sync_mock):
        self.receipt.status = Receipt.Status.SYNC_FAILED
        self.receipt.save(update_fields=["status"])

        response = self.client.post(self.sync_url)

        self.assertEqual(response.status_code, 302)
        sync_mock.assert_called_once()

    @patch("expense_upload.views.process_receipt_sync")
    def test_synced_receipt_cannot_be_sent_again(self, sync_mock):
        self.receipt.status = Receipt.Status.SYNCED
        self.receipt.save(update_fields=["status"])

        response = self.client.post(self.sync_url)

        self.assertEqual(response.status_code, 404)
        sync_mock.assert_not_called()

    def test_sync_endpoint_rejects_get(self):
        response = self.client.get(self.sync_url)

        self.assertEqual(response.status_code, 405)


class AppsScriptReceiptProviderTests(TestCase):
    @override_settings(
        APPS_SCRIPT_RECEIPT_URL="https://script.google.test/exec",
        APPS_SCRIPT_RECEIPT_SHARED_SECRET="test-secret",
        APPS_SCRIPT_RECEIPT_TIMEOUT=9,
    )
    @patch("expense_upload.services.sheet_sync.requests.post")
    def test_provider_sends_confirmed_financial_fields(self, post_mock):
        response = Mock()
        response.json.return_value = {"ok": True, "duplicate": False}
        post_mock.return_value = response
        receipt_id = "697492cc-c7ae-4ef9-989d-7617b85ab8be"
        confirmed_data = {
            "store_name": "西友",
            "receipt_date": "2026-08-02",
            "total_amount": 3240,
            "category": "Food",
            "items": ["牛乳"],
        }

        AppsScriptReceiptProvider().sync(receipt_id, confirmed_data)

        call = post_mock.call_args
        self.assertEqual(call.kwargs["timeout"], 9)
        self.assertEqual(
            call.kwargs["json"],
            {
                "type": "receipt_expense",
                "shared_secret": "test-secret",
                "receipt_id": receipt_id,
                "receipt_date": "2026-08-02",
                "total_amount": 3240,
                "category": "Food",
            },
        )

    @override_settings(
        APPS_SCRIPT_RECEIPT_URL="",
        APPS_SCRIPT_RECEIPT_SHARED_SECRET="",
    )
    def test_provider_requires_configuration(self):
        with self.assertRaisesMessage(
            ReceiptSyncError,
            "Google Sheets synchronization is not configured.",
        ):
            AppsScriptReceiptProvider().sync("receipt-id", {})

    @override_settings(
        APPS_SCRIPT_RECEIPT_URL="https://script.google.test/exec",
        APPS_SCRIPT_RECEIPT_SHARED_SECRET="test-secret",
        APPS_SCRIPT_RECEIPT_TIMEOUT=9,
    )
    @patch("expense_upload.services.sheet_sync.requests.post")
    def test_provider_rejects_negative_acknowledgement(self, post_mock):
        response = Mock()
        response.json.return_value = {"ok": False, "error": "rejected"}
        post_mock.return_value = response

        with self.assertRaisesMessage(
            ReceiptSyncError,
            "Google Sheets rejected the receipt update.",
        ):
            AppsScriptReceiptProvider().sync(
                "697492cc-c7ae-4ef9-989d-7617b85ab8be",
                {
                    "receipt_date": "2026-08-02",
                    "total_amount": 3240,
                    "category": "Food",
                },
            )


class GeminiReceiptProviderTests(TestCase):
    @override_settings(
        GEMINI_API_KEY="test-key",
        GEMINI_RECEIPT_MODEL="test-model",
        GEMINI_RECEIPT_TIMEOUT=7,
    )
    @patch("expense_upload.services.extraction.requests.post")
    def test_provider_sends_image_with_timeout_and_parses_json(self, post_mock):
        response = Mock()
        response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": '{"store_name": "西友"}'}]
                }
            }]
        }
        post_mock.return_value = response

        result = GeminiReceiptProvider().extract(PNG_IMAGE, "image/png")

        self.assertEqual(result, {"store_name": "西友"})
        call = post_mock.call_args
        self.assertEqual(call.kwargs["timeout"], 7)
        self.assertEqual(call.kwargs["headers"], {"x-goog-api-key": "test-key"})
        self.assertEqual(
            call.kwargs["json"]["contents"][0]["parts"][1]["inlineData"]["mimeType"],
            "image/png",
        )

    @override_settings(GEMINI_API_KEY="")
    def test_provider_requires_configuration(self):
        with self.assertRaisesMessage(
            ReceiptExtractionError,
            "Gemini extraction is not configured.",
        ):
            GeminiReceiptProvider().extract(PNG_IMAGE, "image/png")
