import uuid
from pathlib import Path

from django.db import models


def receipt_image_upload_path(instance, filename):
    """Store receipt images under a generated name, never a client filename."""
    extension = Path(filename).suffix.lower()
    return f"receipts/{instance.id}{extension}"


class Receipt(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        EXTRACTED = "extracted", "Extracted"
        EXTRACTION_FAILED = "extraction_failed", "Extraction failed"
        CONFIRMED = "confirmed", "Confirmed"
        SYNCED = "synced", "Synced"
        SYNC_FAILED = "sync_failed", "Sync failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ImageField(upload_to=receipt_image_upload_path)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.UPLOADED,
    )
    extracted_json = models.JSONField(null=True, blank=True)
    confirmed_json = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Receipt {self.id} ({self.status})"


# Create your models here.

class Google_Sheets_Data(models.Model):
    class Meta:
        db_table = "Google_Sheets_Data"
    PK_Unique = models.IntegerField(primary_key=True, unique=True)
    UserID = models.IntegerField(null=True, blank=True)
    Username = models.CharField(null=True, blank=True, max_length=255)
    Date = models.DateTimeField(null=True, blank=True)
    Food = models.FloatField(null=True, blank=True)
    Stuff = models.FloatField(null=True, blank=True)
    Leisure = models.FloatField(null=True, blank=True)
    Automatic_withdrawal = models.FloatField(null=True, blank=True)
    Automatic_withdrawal_com = models.CharField(null=True, blank=True, max_length=255)
    SMBC_payments = models.FloatField(null=True, blank=True)
    SMBC_card_comments = models.CharField(null=True, blank=True, max_length=300)
    Utility = models.FloatField(null=True, blank=True)
    Details_utility = models.CharField(null=True, blank=True, max_length=255)
    Total_amount = models.FloatField(null=True, blank=True)
    Name_sheet = models.CharField(null=True, blank=True, max_length=10)
