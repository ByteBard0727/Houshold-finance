from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import ReceiptConfirmationForm, ReceiptUploadForm
from .models import Receipt
from .services import process_receipt, process_receipt_sync

REVIEW_QUEUE_SESSION_KEY = "receipt_review_queue"
FAILED_BATCH_SESSION_KEY = "receipt_batch_failed_count"


def _review_queue_context(request, receipt):
    queue = request.session.get(REVIEW_QUEUE_SESSION_KEY, [])
    receipt_id = str(receipt.id)
    if receipt_id not in queue:
        return {}

    position = queue.index(receipt_id)
    next_id = queue[position + 1] if position + 1 < len(queue) else None
    return {
        "batch_position": position + 1,
        "batch_total": len(queue),
        "next_receipt_id": next_id,
        "batch_failed_count": request.session.get(FAILED_BATCH_SESSION_KEY, 0),
    }


@require_http_methods(["GET", "POST"])
def upload_receipt(request):
    receipt = None
    receipts = []

    if request.method == "POST":
        form = ReceiptUploadForm(request.POST, request.FILES)
        if form.is_valid():
            for image in form.cleaned_data["images"]:
                current_receipt = Receipt.objects.create(image=image)
                process_receipt(current_receipt)
                current_receipt.refresh_from_db()
                receipts.append(current_receipt)

            review_queue = [
                str(current_receipt.id)
                for current_receipt in receipts
                if current_receipt.status == Receipt.Status.EXTRACTED
            ]
            request.session[REVIEW_QUEUE_SESSION_KEY] = review_queue
            request.session[FAILED_BATCH_SESSION_KEY] = len(receipts) - len(review_queue)

            if len(receipts) > 1 and review_queue:
                return redirect(reverse("confirm_receipt", args=[review_queue[0]]))

            receipt = receipts[0]
            form = ReceiptUploadForm()
    else:
        form = ReceiptUploadForm()

    return render(
        request,
        "expense_upload/receipt_upload.html",
        {"form": form, "receipt": receipt, "receipts": receipts},
    )


@require_http_methods(["GET", "POST"])
def confirm_receipt(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)

    review_complete_statuses = {
        Receipt.Status.CONFIRMED,
        Receipt.Status.SYNCED,
        Receipt.Status.SYNC_FAILED,
    }
    if request.method == "GET" and receipt.status in review_complete_statuses:
        context = {"receipt": receipt, "confirmed": True}
        context.update(_review_queue_context(request, receipt))
        return render(
            request,
            "expense_upload/receipt_confirmation.html",
            context,
        )

    if receipt.status != Receipt.Status.EXTRACTED or not receipt.extracted_json:
        raise Http404("Receipt is not ready for confirmation.")

    if request.method == "POST":
        form = ReceiptConfirmationForm(request.POST)
        if form.is_valid():
            receipt.confirmed_json = form.confirmed_data()
            receipt.status = Receipt.Status.CONFIRMED
            receipt.error_message = ""
            receipt.save(
                update_fields=[
                    "confirmed_json",
                    "status",
                    "error_message",
                    "updated_at",
                ]
            )
            return redirect(reverse("confirm_receipt", args=[receipt.id]))
    else:
        extracted = receipt.extracted_json
        form = ReceiptConfirmationForm(
            initial={
                "store_name": extracted.get("store_name", ""),
                "receipt_date": extracted.get("receipt_date", ""),
                "total_amount": extracted.get("total_amount"),
                "category": extracted.get("category", "Stuff"),
                "items": "\n".join(extracted.get("items", [])),
            }
        )

    context = {"form": form, "receipt": receipt, "confirmed": False}
    context.update(_review_queue_context(request, receipt))
    return render(
        request,
        "expense_upload/receipt_confirmation.html",
        context,
    )


@require_http_methods(["POST"])
def sync_receipt(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    if receipt.status not in {Receipt.Status.CONFIRMED, Receipt.Status.SYNC_FAILED}:
        raise Http404("Receipt is not ready for synchronization.")

    succeeded = process_receipt_sync(receipt)
    if succeeded:
        queue_context = _review_queue_context(request, receipt)
        next_receipt_id = queue_context.get("next_receipt_id")
        if next_receipt_id:
            return redirect(reverse("confirm_receipt", args=[next_receipt_id]))

        request.session.pop(REVIEW_QUEUE_SESSION_KEY, None)
        request.session.pop(FAILED_BATCH_SESSION_KEY, None)
    return redirect(reverse("confirm_receipt", args=[receipt.id]))
