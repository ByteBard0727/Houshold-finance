import base64
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from .models import Receipt


PNG_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "AScY42YAAAAASUVORK5CYII="
)


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
        self.assertContains(response, "Upload a receipt")

    def test_valid_image_creates_uploaded_receipt(self):
        image = SimpleUploadedFile(
            "household-receipt.png",
            PNG_IMAGE,
            content_type="image/png",
        )

        response = self.client.post(reverse("upload_receipt"), {"image": image})

        receipt = Receipt.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(receipt.status, Receipt.Status.UPLOADED)
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

        response = self.client.post(reverse("upload_receipt"), {"image": upload})

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

        response = self.client.post(reverse("upload_receipt"), {"image": image})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no larger than 0 MB")
        self.assertFalse(Receipt.objects.exists())
