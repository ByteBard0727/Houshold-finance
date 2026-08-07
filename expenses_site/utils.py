from datetime import datetime

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


def parse_sheet_date(value):
    """Parse a supported Sheet date into a naive local datetime."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None

    for date_format in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
    ):
        try:
            return datetime.strptime(value.strip(), date_format)
        except ValueError:
            continue
    return None

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
        sheet_rows = []
        if data:
            headers = normalize_sheet_headers(data[0])
            for values in data[1:]:
                row = {
                    header: values[index] if index < len(values) else ""
                    for index, header in enumerate(headers)
                }
                row["Date"] = parse_sheet_date(row.get("Date"))
                sheet_rows.append(row)

        data_frames[sheet_title] = sheet_rows

    global_google_sheets_data = data_frames  
    print("fetching google sheets data")
    return data_frames


#helper function to cleaning the values allowing empty cells to exist in the sheet transforming empty strings into none
def clean_value(value):
    if isinstance(value, str):
        value = value.strip()  # Remove leading/trailing whitespace
    return None if value == '' else value
