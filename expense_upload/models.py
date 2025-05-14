from django.db import models
# Create your models here.

class Google_Sheets_Data(models.Model):
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