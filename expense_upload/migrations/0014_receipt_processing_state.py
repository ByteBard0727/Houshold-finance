# Generated manually to preserve the surviving legacy migration graph.

import expense_upload.models
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("expense_upload", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Receipt",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        upload_to=expense_upload.models.receipt_image_upload_path
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("uploaded", "Uploaded"),
                            ("processing", "Processing"),
                            ("extracted", "Extracted"),
                            ("extraction_failed", "Extraction failed"),
                            ("confirmed", "Confirmed"),
                            ("synced", "Synced"),
                            ("sync_failed", "Sync failed"),
                        ],
                        default="uploaded",
                        max_length=32,
                    ),
                ),
                ("extracted_json", models.JSONField(blank=True, null=True)),
                ("confirmed_json", models.JSONField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
