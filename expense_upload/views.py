from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import ReceiptConfirmationForm, ReceiptUploadForm
from .models import Receipt
from .services import process_receipt, process_receipt_sync


@require_http_methods(["GET", "POST"])
def upload_receipt(request):
    receipt = None

    if request.method == "POST":
        form = ReceiptUploadForm(request.POST, request.FILES)
        if form.is_valid():
            receipt = Receipt.objects.create(image=form.cleaned_data["image"])
            process_receipt(receipt)
            form = ReceiptUploadForm()
    else:
        form = ReceiptUploadForm()

    return render(
        request,
        "expense_upload/receipt_upload.html",
        {"form": form, "receipt": receipt},
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
        return render(
            request,
            "expense_upload/receipt_confirmation.html",
            {"receipt": receipt, "confirmed": True},
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

    return render(
        request,
        "expense_upload/receipt_confirmation.html",
        {"form": form, "receipt": receipt, "confirmed": False},
    )


@require_http_methods(["POST"])
def sync_receipt(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    if receipt.status not in {Receipt.Status.CONFIRMED, Receipt.Status.SYNC_FAILED}:
        raise Http404("Receipt is not ready for synchronization.")

    process_receipt_sync(receipt)
    return redirect(reverse("confirm_receipt", args=[receipt.id]))
