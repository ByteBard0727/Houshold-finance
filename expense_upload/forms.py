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


class ReceiptConfirmationForm(forms.Form):
    CATEGORY_CHOICES = [
        ("Food", "Food"),
        ("Stuff", "Stuff"),
        ("Leisure", "Leisure"),
        ("Utility", "Utility"),
    ]

    store_name = forms.CharField(label="Store", max_length=255, required=False)
    receipt_date = forms.DateField(
        label="Receipt date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    total_amount = forms.IntegerField(label="Total amount (yen)", min_value=0)
    category = forms.ChoiceField(choices=CATEGORY_CHOICES)
    items = forms.CharField(
        label="Items",
        help_text="Enter one item per line.",
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
    )

    def confirmed_data(self):
        """Return validated form values in the stable receipt JSON shape."""
        return {
            "store_name": self.cleaned_data["store_name"].strip(),
            "receipt_date": self.cleaned_data["receipt_date"].isoformat(),
            "total_amount": self.cleaned_data["total_amount"],
            "category": self.cleaned_data["category"],
            "items": [
                item.strip()
                for item in self.cleaned_data["items"].splitlines()
                if item.strip()
            ],
        }
