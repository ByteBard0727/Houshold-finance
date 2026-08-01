from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .forms import ReceiptUploadForm
from .models import Receipt


@require_http_methods(["GET", "POST"])
def upload_receipt(request):
    receipt = None

    if request.method == "POST":
        form = ReceiptUploadForm(request.POST, request.FILES)
        if form.is_valid():
            receipt = Receipt.objects.create(image=form.cleaned_data["image"])
            form = ReceiptUploadForm()
    else:
        form = ReceiptUploadForm()

    return render(
        request,
        "expense_upload/receipt_upload.html",
        {"form": form, "receipt": receipt},
    )
