"""Create validated monthly ledger tabs through the Google Sheets API."""

import calendar
from datetime import date, datetime

from django.conf import settings
from google.oauth2 import service_account
from googleapiclient.discovery import build

from expenses_site.utils import SPREADSHEET_ID, normalize_sheet_headers


WRITE_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
MONTH_FORMAT = "%b%Y"
EXPECTED_HEADERS = [
    "UserID",
    "Username",
    "Date",
    "Food",
    "Stuff",
    "Leisure",
    "Automatic_withdrawal",
    "Automatic_withdrawal_com",
    "SMBC_payments",
    "SMBC_card_comments",
    "Utility",
    "Details_utility",
    "Total_amount",
    "Name_sheet",
    "PK_Unique",
]


class MonthlySheetError(Exception):
    """Raised when a monthly tab cannot be created without breaking invariants."""


def _parse_month(title):
    try:
        return datetime.strptime(title, MONTH_FORMAT).date().replace(day=1)
    except (TypeError, ValueError):
        return None


def _next_month(month):
    if month.month == 12:
        return date(month.year + 1, 1, 1)
    return date(month.year, month.month + 1, 1)


def _sheet_serial(value):
    return (value - date(1899, 12, 30)).days


def _is_formula(value):
    return isinstance(value, str) and value.startswith("=")


def _prepare_rows(template_rows, target_month, first_pk, target_title):
    """Clear copied transactions while retaining formulas and structural cells."""
    padded = [list(row) + [""] * (15 - len(row)) for row in template_rows]
    if len(padded) != 32:
        raise MonthlySheetError("The template must contain exactly 32 ledger rows.")

    days_in_month = calendar.monthrange(target_month.year, target_month.month)[1]
    prepared = []
    for index, row in enumerate(padded):
        is_total_row = index == 31
        if not is_total_row:
            row[1] = row[1] if _is_formula(row[1]) else ""
            row[2] = (
                _sheet_serial(date(target_month.year, target_month.month, index + 1))
                if index < days_in_month
                else ""
            )
            for column in range(3, 12):
                if not _is_formula(row[column]):
                    row[column] = ""
            if not _is_formula(row[12]):
                row[12] = ""
        else:
            row[2] = "合計"

        row[13] = target_title if row[13] else ""
        row[14] = first_pk + index
        prepared.append(row)
    return prepared


def _service():
    credentials = service_account.Credentials.from_service_account_file(
        settings.BASE_DIR / "secrets/google_service_account.json",
        scopes=[WRITE_SCOPE],
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def create_next_month_sheet(service=None):
    """Clone, reset, and validate the next chronological monthly worksheet."""
    service = service or _service()
    metadata = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    monthly_tabs = []
    properties_by_title = {}
    for sheet in metadata.get("sheets", []):
        properties = sheet["properties"]
        title = properties["title"]
        parsed = _parse_month(title)
        if parsed:
            monthly_tabs.append((parsed, title))
            properties_by_title[title] = properties
    if not monthly_tabs:
        raise MonthlySheetError("No monthly worksheet is available as a template.")

    monthly_tabs.sort()
    latest_month, _ = monthly_tabs[-1]
    target_month = _next_month(latest_month)
    target_title = target_month.strftime(MONTH_FORMAT)
    if target_title in properties_by_title:
        raise MonthlySheetError(f"{target_title} already exists.")

    prior_year_title = target_month.replace(year=target_month.year - 1).strftime(
        MONTH_FORMAT
    )
    template_title = (
        prior_year_title
        if prior_year_title in properties_by_title
        else monthly_tabs[-1][1]
    )
    template_id = properties_by_title[template_title]["sheetId"]

    template_values = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{template_title}'!A1:O33",
        valueRenderOption="FORMULA",
    ).execute().get("values", [])
    if len(template_values) != 33:
        raise MonthlySheetError("The template must contain one header and 32 rows.")
    if normalize_sheet_headers(template_values[0]) != EXPECTED_HEADERS:
        raise MonthlySheetError("The template headers do not match the dashboard schema.")

    pk_ranges = [f"'{title}'!O2:O33" for _, title in monthly_tabs]
    all_pk_values = service.spreadsheets().values().batchGet(
        spreadsheetId=SPREADSHEET_ID,
        ranges=pk_ranges,
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute().get("valueRanges", [])
    pk_values = []
    for value_range in all_pk_values:
        for row in value_range.get("values", []):
            if not row:
                continue
            try:
                pk_values.append(int(row[0]))
            except (TypeError, ValueError):
                pass
    first_pk = max(pk_values, default=0) + 1
    prepared_rows = _prepare_rows(
        template_values[1:], target_month, first_pk, target_title
    )

    copied_sheet_id = None
    try:
        copied = service.spreadsheets().sheets().copyTo(
            spreadsheetId=SPREADSHEET_ID,
            sheetId=template_id,
            body={"destinationSpreadsheetId": SPREADSHEET_ID},
        ).execute()
        copied_sheet_id = copied["sheetId"]
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "requests": [{
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": copied_sheet_id,
                            "title": target_title,
                        },
                        "fields": "title",
                    }
                }]
            },
        ).execute()
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{target_title}'!A2:O33",
            valueInputOption="USER_ENTERED",
            body={"values": prepared_rows},
        ).execute()

        verification = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{target_title}'!A1:O33",
            valueRenderOption="FORMULA",
        ).execute().get("values", [])
        if len(verification) != 33:
            raise MonthlySheetError("Created worksheet has an invalid row count.")
        if normalize_sheet_headers(verification[0]) != EXPECTED_HEADERS:
            raise MonthlySheetError("Created worksheet has invalid headers.")
        actual_pks = [int(row[14]) for row in verification[1:] if len(row) > 14]
        if actual_pks != list(range(first_pk, first_pk + 32)):
            raise MonthlySheetError("Created worksheet has invalid PK_Unique values.")
    except Exception as error:
        if copied_sheet_id is not None:
            try:
                service.spreadsheets().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={"requests": [{"deleteSheet": {"sheetId": copied_sheet_id}}]},
                ).execute()
            except Exception:
                pass
        if isinstance(error, MonthlySheetError):
            raise
        raise MonthlySheetError("Google Sheets could not create the next month.") from error

    return {
        "title": target_title,
        "template": template_title,
        "first_pk": first_pk,
        "last_pk": first_pk + 31,
    }
