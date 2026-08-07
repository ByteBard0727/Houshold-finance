#utils.py
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from expense_upload import models

SERVICE_ACCOUNT_FILE = 'secrets/google_service_account.json'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# Authenticate and create a service object

SPREADSHEET_ID = '1Jn04_Hc_XHs3MxAFoCYFlruLIparHOqL8Q_PHUiuZ68'
RANGE_NAME = 'A1:O33'

SHEET_HEADER_ALIASES = {
    "Automatic withdrawal": "Automatic_withdrawal",
    "Automatic withdrawal details": "Automatic_withdrawal_com",
    "SMBC credit card payment": "SMBC_payments",
    "SMBC credit card payment details": "SMBC_card_comments",
    "Utility(Gas, Electricity, Water＆Sewage)": "Utility",
    "Details of utility": "Details_utility",
    "Total amount": "Total_amount",
}


def normalize_sheet_headers(headers):
    """Map the workbook's display headers to the legacy projection fields."""
    normalized_headers = []
    for header in headers:
        normalized_header = " ".join(str(header).split())
        normalized_headers.append(
            SHEET_HEADER_ALIASES.get(normalized_header, normalized_header)
        )
    return normalized_headers

#up until here works 200
def fetch_google_sheet_data(spreadsheet_id):
    global global_google_sheets_data
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    sheets_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

    data_frames = {}
    for sheet in sheets_metadata["sheets"]:
        sheet_title = sheet["properties"]["title"]  # Sheet name
         # works
        range_name = f"{sheet_title}!A1:O33"  # Assuming the same format for all sheets
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )
       #works

        data = result.get("values", [])
        if data:
            headers = normalize_sheet_headers(data[0])
            rows = data[1:]
            df = pd.DataFrame(rows, columns=headers)
            #works

            # Custom date parsing
            def try_parse_date(date_str):
                if pd.isna(date_str) or not date_str.strip():
                    return None
                formats = [
                    "%Y-%m-%d",
                    "%Y/%m/%d",
                    "%d/%m/%Y",
                    "%m/%d/%Y",
                    "%d-%m-%Y",
                ]
                for fmt in formats:
                    try:
                        return pd.to_datetime(date_str, format=fmt)
                    except ValueError:
                        continue
                return None

            df["Date"] = df["Date"].apply(try_parse_date)

        data_frames[sheet_title] = df

    global_google_sheets_data = data_frames  
    print("fetching google sheets data")
    return data_frames


#helper function to cleaning the values allowing empty cells to exist in the sheet transforming empty strings into none
def clean_value(value):
    if isinstance(value, str):
        value = value.strip()  # Remove leading/trailing whitespace
    return None if value == '' else value
