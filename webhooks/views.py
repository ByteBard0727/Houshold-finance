from django.http import JsonResponse
from expenses_site.utils import fetch_google_sheet_data, RANGE_NAME, SPREADSHEET_ID, clean_value
from expense_upload.models import Google_Sheets_Data
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
import pandas as pd
from django.db import transaction
from dashboard.views import update_dashboard_data
from django.db import transaction, connection

# Helper function to parse the date
def parse_date(date_value):
    """
    Parse a date string from Google Sheets into a datetime object.
    If the value is already a datetime object, return it as is.
    If it's a string, try to parse it into a datetime object using multiple formats.
    """
    if isinstance(date_value, datetime):
        return date_value  # Already a datetime object
    elif isinstance(date_value, str):
        # Define possible date formats
        date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']
        for fmt in date_formats:
            try:
                return datetime.strptime(date_value, fmt)
            except ValueError:
                continue
    return None  # Return None if no format matches

# Webhook view that processes the incoming POST request
@transaction.atomic
@csrf_exempt
def google_sheet_webhook(request):
    if request.method == "POST":
        spreadsheet_id = "1Jn04_Hc_XHs3MxAFoCYFlruLIparHOqL8Q_PHUiuZ68"
        
        # Fetch the data from Google Sheets synchronously
        all_sheets_data = fetch_google_sheet_data(spreadsheet_id)

        print("Received webhook data. Processing sheets...")  # Debugging print statement

        # Loop over the sheets and their respective data
        for sheet_name, data_frame in all_sheets_data.items():
            print(f"Processing sheet: {sheet_name}")  # Debugging print statement
            for _, row in data_frame.iterrows():
                parsed_date = parse_date(row['Date'])
                date_str = None if pd.isna(parsed_date) else parsed_date.strftime('%Y-%m-%d')

                # Update or create the database record for each row
                Google_Sheets_Data.objects.update_or_create(
                    PK_Unique=row.get('PK_Unique'),  # Use PK_Unique as the lookup field
                    defaults={
                        'UserID': clean_value(row.get('UserID')),
                        'Username': clean_value(row.get('Username')),
                        'Date': clean_value(date_str),
                        'Food': clean_value(row.get('Food')),
                        'Stuff': clean_value(row.get('Stuff')),
                        'Leisure': clean_value(row.get('Leisure')),
                        'Automatic_withdrawal': clean_value(row.get('Automatic_withdrawal')),
                        'Automatic_withdrawal_com': clean_value(row.get('Automatic_withdrawal_com')),
                        'SMBC_payments': clean_value(row.get('SMBC_payments')),
                        'SMBC_card_comments': clean_value(row.get('SMBC_card_comments')),
                        'Utility': clean_value(row.get('Utility')),
                        'Details_utility': clean_value(row.get('Details_utility')),
                        'Total_amount': clean_value(row.get('Total_amount')),
                        'Name_sheet': sheet_name,
                    }
                )
                print(f"Processed row: {row['PK_Unique']}")  # Debugging print statement
        
        print("Webhook processed successfully.")

        # Update dashboard **after** transaction commits
        update_dashboard_data()

        # Return response **after** all updates
        return JsonResponse({
            "status": "success",
            "message": "Data saved to the database.",
            "rows_processed": sum(len(df) for df in all_sheets_data.values()),
            "sheets_processed": list(all_sheets_data.keys()),
        })

    return JsonResponse({"error": "Invalid request method"}, status=400)