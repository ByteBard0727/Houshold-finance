from django.db import transaction
from django.forms import formset_factory
import mimetypes

from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import (
    BatchReceiptConfirmationForm,
    ReceiptConfirmationForm,
    ReceiptUploadForm,
)
from .models import Receipt
from .services import process_receipt, process_receipt_sync

REVIEW_QUEUE_SESSION_KEY = "receipt_review_queue"
FAILED_BATCH_SESSION_KEY = "receipt_batch_failed_count"
BATCH_RECEIPTS_SESSION_KEY = "receipt_batch_receipts"
BatchReceiptConfirmationFormSet = formset_factory(
    BatchReceiptConfirmationForm,
    extra=0,
)


@require_http_methods(["GET"])
def receipt_image(request, receipt_id):
    """Serve one stored receipt image without exposing the media directory."""
    receipt = get_object_or_404(Receipt, id=receipt_id)
    try:
        image_file = receipt.image.open("rb")
    except (FileNotFoundError, OSError, ValueError):
        raise Http404("Receipt image is unavailable.")

    content_type = mimetypes.guess_type(receipt.image.name)[0] or "application/octet-stream"
    response = FileResponse(image_file, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    return response


def _queued_receipts(request):
    queue = request.session.get(
        BATCH_RECEIPTS_SESSION_KEY,
        request.session.get(REVIEW_QUEUE_SESSION_KEY, []),
    )
    receipts_by_id = {
        str(receipt.id): receipt
        for receipt in Receipt.objects.filter(id__in=queue)
    }
    return [receipts_by_id[receipt_id] for receipt_id in queue if receipt_id in receipts_by_id]


def _confirmation_initial(receipt):
    extracted = receipt.extracted_json or {}
    return {
        "receipt_id": receipt.id,
        "store_name": extracted.get("store_name", ""),
        "receipt_date": extracted.get("receipt_date", ""),
        "total_amount": extracted.get("total_amount"),
        "category": extracted.get("category", "Stuff"),
        "items": "\n".join(extracted.get("items", [])),
    }


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
                receipts.append(current_receipt)

            # A batch is parsed through one request per image from the review
            # page. This keeps a large batch out of one proxy-sensitive request.
            if len(receipts) > 1:
                receipt_ids = [str(current_receipt.id) for current_receipt in receipts]
                request.session[REVIEW_QUEUE_SESSION_KEY] = receipt_ids
                request.session[BATCH_RECEIPTS_SESSION_KEY] = receipt_ids
                request.session[FAILED_BATCH_SESSION_KEY] = 0
                return redirect(reverse("confirm_receipt_batch"))

            process_receipt(receipts[0])
            receipts[0].refresh_from_db()

            review_queue = [
                str(current_receipt.id)
                for current_receipt in receipts
                if current_receipt.status == Receipt.Status.EXTRACTED
            ]
            request.session[REVIEW_QUEUE_SESSION_KEY] = review_queue
            request.session[BATCH_RECEIPTS_SESSION_KEY] = [
                str(current_receipt.id) for current_receipt in receipts
            ]
            request.session[FAILED_BATCH_SESSION_KEY] = len(receipts) - len(review_queue)

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
def confirm_receipt_batch(request):
    receipts = _queued_receipts(request)
    if not receipts:
        return redirect(reverse("upload_receipt"))

    extracted_receipts = [
        receipt
        for receipt in receipts
        if receipt.status == Receipt.Status.EXTRACTED and receipt.extracted_json
    ]
    parse_receipts = [
        receipt
        for receipt in receipts
        if receipt.status in {
            Receipt.Status.UPLOADED,
            Receipt.Status.EXTRACTION_FAILED,
        }
    ]
    if request.method == "POST":
        formset = BatchReceiptConfirmationFormSet(request.POST)
        if formset.is_valid():
            submitted_ids = [str(form.cleaned_data["receipt_id"]) for form in formset]
            expected_ids = [str(receipt.id) for receipt in extracted_receipts]
            if submitted_ids != expected_ids:
                raise Http404("Receipt batch does not match the upload session.")

            receipts_by_id = {str(receipt.id): receipt for receipt in extracted_receipts}
            with transaction.atomic():
                for form in formset:
                    receipt = receipts_by_id[str(form.cleaned_data["receipt_id"])]
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
            return redirect(reverse("confirm_receipt_batch"))
    else:
        formset = BatchReceiptConfirmationFormSet(
            initial=[_confirmation_initial(receipt) for receipt in extracted_receipts]
        )

    receipts = _queued_receipts(request)
    sync_receipts = [
        receipt for receipt in receipts if receipt.status == Receipt.Status.CONFIRMED
    ]
    completed = not any(
        receipt.status in {Receipt.Status.EXTRACTED, Receipt.Status.CONFIRMED}
        for receipt in receipts
    )
    return render(
        request,
        "expense_upload/receipt_batch_confirmation.html",
        {
            "formset": formset,
            "review_rows": zip(formset, extracted_receipts),
            "receipts": receipts,
            "sync_receipts": sync_receipts,
            "parse_receipts": parse_receipts,
            "parsed_count": sum(
                receipt.status in {
                    Receipt.Status.EXTRACTED,
                    Receipt.Status.CONFIRMED,
                    Receipt.Status.SYNCED,
                    Receipt.Status.SYNC_FAILED,
                }
                for receipt in receipts
            ),
            "reviewing": not parse_receipts and any(
                receipt.status == Receipt.Status.EXTRACTED for receipt in receipts
            ),
            "completed": completed,
            "batch_failed_count": sum(
                receipt.status == Receipt.Status.EXTRACTION_FAILED
                for receipt in receipts
            ),
        },
    )


@require_http_methods(["POST"])
def parse_receipt_batch_item(request, receipt_id):
    queue = request.session.get(BATCH_RECEIPTS_SESSION_KEY, [])
    if str(receipt_id) not in queue:
        raise Http404("Receipt is not part of this upload batch.")

    receipt = get_object_or_404(Receipt, id=receipt_id)
    if receipt.status == Receipt.Status.EXTRACTED:
        return JsonResponse({"ok": True, "status": receipt.status})
    if receipt.status not in {
        Receipt.Status.UPLOADED,
        Receipt.Status.EXTRACTION_FAILED,
    }:
        return JsonResponse(
            {"ok": False, "status": receipt.status, "error": receipt.error_message},
            status=409,
        )

    succeeded = process_receipt(receipt)
    receipt.refresh_from_db()
    return JsonResponse(
        {
            "ok": succeeded,
            "status": receipt.status,
            "error": receipt.error_message,
        },
        status=200 if succeeded else 502,
    )


@require_http_methods(["POST"])
def sync_receipt_batch_item(request, receipt_id):
    queue = request.session.get(REVIEW_QUEUE_SESSION_KEY, [])
    if str(receipt_id) not in queue:
        raise Http404("Receipt is not part of this upload batch.")

    receipt = get_object_or_404(Receipt, id=receipt_id)
    if receipt.status == Receipt.Status.SYNCED:
        return JsonResponse({"ok": True, "status": receipt.status})
    if receipt.status != Receipt.Status.CONFIRMED:
        return JsonResponse(
            {"ok": False, "status": receipt.status, "error": receipt.error_message},
            status=409,
        )

    succeeded = process_receipt_sync(receipt)
    receipt.refresh_from_db()
    return JsonResponse(
        {
            "ok": succeeded,
            "status": receipt.status,
            "error": receipt.error_message,
        },
        status=200 if succeeded else 502,
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
