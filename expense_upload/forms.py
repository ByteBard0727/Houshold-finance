from django import forms
from django.conf import settings


class ReceiptUploadForm(forms.Form):
    image = forms.ImageField(
        label="Receipt photo",
        help_text="JPEG or PNG",
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/jpeg,image/png",
                "capture": "environment",
            }
        ),
    )

    def clean_image(self):
        image = self.cleaned_data["image"]
        max_size = settings.RECEIPT_MAX_UPLOAD_SIZE

        if image.size > max_size:
            max_megabytes = max_size // (1024 * 1024)
            raise forms.ValidationError(
                f"The image must be no larger than {max_megabytes} MB."
            )

        if image.image.format not in {"JPEG", "PNG"}:
            raise forms.ValidationError("Upload a JPEG or PNG receipt image.")

        return image
