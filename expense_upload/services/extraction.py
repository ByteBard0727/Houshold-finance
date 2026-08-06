"""Gemini-backed receipt extraction with persistence-safe failure handling."""

import base64
import json
from datetime import date

import requests
from django.conf import settings

from expense_upload.models import Receipt


SUPPORTED_CATEGORIES = {"Food", "Stuff", "Leisure", "Utility"}


class ReceiptExtractionError(Exception):
    """Raised when a provider cannot return usable receipt data."""


class GeminiReceiptProvider:
    """Send a receipt image directly to Gemini and request strict JSON."""

    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def extract(self, image_bytes, mime_type):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ReceiptExtractionError("Gemini extraction is not configured.")

        payload = {
            "contents": [{
                "parts": [
                    {"text": self._prompt()},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    },
                ]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": self._response_schema(),
                "temperature": 0,
            },
        }

        try:
            response = requests.post(
                self.endpoint.format(model=settings.GEMINI_RECEIPT_MODEL),
                headers={"x-goog-api-key": api_key},
                json=payload,
                timeout=settings.GEMINI_RECEIPT_TIMEOUT,
            )
            response.raise_for_status()
            body = response.json()
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ReceiptExtractionError("Gemini did not return usable receipt data.") from exc

    @staticmethod
    def _prompt():
        return (
            "Extract this Japanese receipt. Return the merchant name, purchase date in "
            "YYYY-MM-DD format using Japan local time, integer total amount in yen, the "
            "best matching category, and best-effort item descriptions. Category must be "
            "Food, Stuff, Leisure, or Utility; use Stuff when uncertain. Do not invent "
            "missing values."
        )

    @staticmethod
    def _response_schema():
        return {
            "type": "OBJECT",
            "properties": {
                "store_name": {"type": "STRING"},
                "receipt_date": {"type": "STRING"},
                "total_amount": {"type": "INTEGER"},
                "category": {
                    "type": "STRING",
                    "enum": sorted(SUPPORTED_CATEGORIES),
                },
                "items": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": [
                "store_name",
                "receipt_date",
                "total_amount",
                "category",
                "items",
            ],
        }


def normalize_extraction(data):
    """Validate required financial fields and normalize safe fallbacks."""
    if not isinstance(data, dict):
        raise ReceiptExtractionError("Gemini returned an invalid result.")

    store_name = str(data.get("store_name", "")).strip()
    receipt_date = str(data.get("receipt_date", "")).strip()
    try:
        date.fromisoformat(receipt_date)
    except ValueError as exc:
        raise ReceiptExtractionError("Gemini could not determine a valid receipt date.") from exc

    total_amount = data.get("total_amount")
    if isinstance(total_amount, bool) or not isinstance(total_amount, int) or total_amount < 0:
        raise ReceiptExtractionError("Gemini could not determine a valid receipt total.")

    category = data.get("category")
    if category not in SUPPORTED_CATEGORIES:
        category = "Stuff"

    items = data.get("items", [])
    if not isinstance(items, list):
        items = []

    return {
        "store_name": store_name,
        "receipt_date": receipt_date,
        "total_amount": total_amount,
        "category": category,
        "items": [str(item).strip() for item in items if str(item).strip()],
    }


def process_receipt(receipt, provider=None):
    """Extract one receipt synchronously and always persist its final state."""
    receipt.status = Receipt.Status.PROCESSING
    receipt.error_message = ""
    receipt.save(update_fields=["status", "error_message", "updated_at"])
    provider = provider or GeminiReceiptProvider()

    try:
        with receipt.image.open("rb") as image_file:
            result = provider.extract(image_file.read(), _mime_type(receipt.image.name))
        receipt.extracted_json = normalize_extraction(result)
        receipt.status = Receipt.Status.EXTRACTED
        receipt.error_message = ""
    except Exception as exc:  # An external failure must never lose the upload.
        receipt.status = Receipt.Status.EXTRACTION_FAILED
        receipt.extracted_json = None
        if isinstance(exc, ReceiptExtractionError):
            receipt.error_message = str(exc)
        else:
            receipt.error_message = "Receipt extraction failed. Please try again later."

    receipt.save(
        update_fields=["status", "extracted_json", "error_message", "updated_at"]
    )
    return receipt.status == Receipt.Status.EXTRACTED


def _mime_type(image_name):
    return "image/png" if image_name.lower().endswith(".png") else "image/jpeg"
