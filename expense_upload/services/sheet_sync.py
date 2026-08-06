"""Google Apps Script receipt synchronization boundary."""

import requests
from django.conf import settings

from expense_upload.models import Receipt


class ReceiptSyncError(Exception):
    """Raised when a confirmed receipt cannot be safely synchronized."""


class AppsScriptReceiptProvider:
    """Send reviewed receipt fields to the Apps Script write extension."""

    def sync(self, receipt_id, confirmed_data):
        if (
            not settings.APPS_SCRIPT_RECEIPT_URL
            or not settings.APPS_SCRIPT_RECEIPT_SHARED_SECRET
        ):
            raise ReceiptSyncError("Google Sheets synchronization is not configured.")

        payload = {
            "type": "receipt_expense",
            "shared_secret": settings.APPS_SCRIPT_RECEIPT_SHARED_SECRET,
            "receipt_id": str(receipt_id),
            "receipt_date": confirmed_data["receipt_date"],
            "total_amount": confirmed_data["total_amount"],
            "category": confirmed_data["category"],
        }

        try:
            response = requests.post(
                settings.APPS_SCRIPT_RECEIPT_URL,
                json=payload,
                timeout=settings.APPS_SCRIPT_RECEIPT_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("ok") is not True:
                raise ReceiptSyncError("Google Sheets rejected the receipt update.")
        except ReceiptSyncError:
            raise
        except (requests.RequestException, TypeError, ValueError) as exc:
            raise ReceiptSyncError(
                "Google Sheets did not acknowledge the receipt update."
            ) from exc


def process_receipt_sync(receipt, provider=None):
    """Synchronize confirmed data and persist a controlled final state."""
    provider = provider or AppsScriptReceiptProvider()

    try:
        if not receipt.confirmed_json:
            raise ReceiptSyncError("Receipt confirmation data is missing.")
        provider.sync(receipt.id, receipt.confirmed_json)
        receipt.status = Receipt.Status.SYNCED
        receipt.error_message = ""
    except Exception as exc:
        receipt.status = Receipt.Status.SYNC_FAILED
        if isinstance(exc, ReceiptSyncError):
            receipt.error_message = str(exc)
        else:
            receipt.error_message = "Google Sheets synchronization failed."

    receipt.save(update_fields=["status", "error_message", "updated_at"])
    return receipt.status == Receipt.Status.SYNCED
