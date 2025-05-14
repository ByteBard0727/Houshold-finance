import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from expense_upload import models

# Path to the service account JSON key file
SERVICE_ACCOUNT_FILE = '/home/joey5055/Python-projects/household-finance/expenses_site/expense_upload/google_service_account.json'

# Defines the required scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# Authenticate and create a service object


SPREADSHEET_ID = '1Jn04_Hc_XHs3MxAFoCYFlruLIparHOqL8Q_PHUiuZ68'
RANGE_NAME = 'A1:O33'

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
            headers = data[0]
            rows = data[1:]
            df = pd.DataFrame(rows, columns=headers)
            #works

            # Custom date parsing
            def try_parse_date(date_str):
                if pd.isna(date_str) or not date_str.strip():
                    return None
                formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]
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