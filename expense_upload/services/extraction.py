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

        attempts = max(1, settings.GEMINI_RECEIPT_ATTEMPTS)
        last_error = None
        for _ in range(attempts):
            try:
                response = requests.post(
                    self.endpoint.format(model=settings.GEMINI_RECEIPT_MODEL),
                    headers={"x-goog-api-key": api_key},
                    json=payload,
                    timeout=settings.GEMINI_RECEIPT_TIMEOUT,
                )
                response.raise_for_status()
                body = response.json()
                parts = body["candidates"][0]["content"]["parts"]
                for part in parts:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        try:
                            return json.loads(part["text"])
                        except (TypeError, ValueError):
                            continue
                raise ValueError("No JSON text part was returned.")
            except requests.Timeout as exc:
                last_error = exc
                failure = "Gemini receipt extraction timed out"
            except requests.RequestException as exc:
                last_error = exc
                failure = "Gemini receipt extraction request failed"
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                last_error = exc
                failure = "Gemini returned an incomplete receipt response"

        raise ReceiptExtractionError(
            f"{failure} after {attempts} attempts. The image remains stored for retry."
        ) from last_error

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


class OpenAIReceiptProvider:
    """Fallback receipt extraction through the OpenAI Responses API."""

    endpoint = "https://api.openai.com/v1/responses"

    def extract(self, image_bytes, mime_type):
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ReceiptExtractionError("OpenAI fallback extraction is not configured.")

        schema = {
            "type": "object",
            "properties": {
                "store_name": {"type": "string"},
                "receipt_date": {"type": "string"},
                "total_amount": {"type": "integer"},
                "category": {
                    "type": "string",
                    "enum": sorted(SUPPORTED_CATEGORIES),
                },
                "items": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "store_name",
                "receipt_date",
                "total_amount",
                "category",
                "items",
            ],
            "additionalProperties": False,
        }
        payload = {
            "model": settings.OPENAI_RECEIPT_MODEL,
            "store": False,
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": GeminiReceiptProvider._prompt()},
                    {
                        "type": "input_image",
                        "image_url": (
                            f"data:{mime_type};base64,"
                            f"{base64.b64encode(image_bytes).decode('ascii')}"
                        ),
                        "detail": "high",
                    },
                ],
            }],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "receipt_extraction",
                    "strict": True,
                    "schema": schema,
                }
            },
        }

        try:
            response = requests.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=settings.OPENAI_RECEIPT_TIMEOUT,
            )
            response.raise_for_status()
            body = response.json()
            for output in body.get("output", []):
                for content in output.get("content", []):
                    if content.get("type") == "output_text":
                        return json.loads(content["text"])
            raise ValueError("No structured output was returned.")
        except requests.Timeout as exc:
            raise ReceiptExtractionError(
                "OpenAI fallback receipt extraction timed out."
            ) from exc
        except requests.RequestException as exc:
            raise ReceiptExtractionError(
                "OpenAI fallback receipt extraction request failed."
            ) from exc
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ReceiptExtractionError(
                "OpenAI fallback returned an incomplete receipt response."
            ) from exc


class AutomaticReceiptProvider:
    """Use Gemini first and OpenAI automatically when Gemini fails."""

    def extract(self, image_bytes, mime_type):
        try:
            return normalize_extraction(
                GeminiReceiptProvider().extract(image_bytes, mime_type)
            )
        except ReceiptExtractionError as gemini_error:
            if not settings.OPENAI_API_KEY:
                raise gemini_error
            try:
                return normalize_extraction(
                    OpenAIReceiptProvider().extract(image_bytes, mime_type)
                )
            except ReceiptExtractionError as openai_error:
                raise ReceiptExtractionError(
                    f"Gemini failed; {openai_error} The image remains stored for retry."
                ) from openai_error


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
    provider = provider or AutomaticReceiptProvider()

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
