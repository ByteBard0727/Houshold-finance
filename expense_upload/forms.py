from django import forms
from django.conf import settings


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        clean_file = super().clean
        return [clean_file(receipt, initial) for receipt in files]


class ReceiptUploadForm(forms.Form):
    images = MultipleImageField(
        label="Receipt photos",
        help_text="Select one or more JPEG or PNG receipts.",
        widget=MultipleFileInput(
            attrs={
                "accept": "image/jpeg,image/png",
                "multiple": True,
            }
        ),
    )

    def clean_images(self):
        images = self.cleaned_data["images"]
        max_size = settings.RECEIPT_MAX_UPLOAD_SIZE

        for image in images:
            if image.size > max_size:
                max_megabytes = max_size // (1024 * 1024)
                raise forms.ValidationError(
                    f"Each image must be no larger than {max_megabytes} MB."
                )

            if image.image.format not in {"JPEG", "PNG"}:
                raise forms.ValidationError("Upload only JPEG or PNG receipt images.")

        return images


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
