from django.apps import AppConfig
from google.oauth2 import service_account
from googleapiclient.discovery import build
from gspread import Spreadsheet

class ExpenseUploadConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'expense_upload'



    
