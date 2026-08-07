import json
from datetime import datetime

from django.test import RequestFactory, TestCase

from expense_upload.models import Google_Sheets_Data

from .views import get_month_stats, get_pk_unique, get_sheets, get_total_spend_bulk


class DynamicMonthlyTotalTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def create_row(self, pk, sheet, total=None, date=None, food=None):
        return Google_Sheets_Data.objects.create(
            PK_Unique=pk,
            Name_sheet=sheet,
            Total_amount=total,
            Date=date,
            Food=food,
        )

    def test_total_row_uses_highest_pk_within_sheet(self):
        self.create_row(385, "Jan2027", date=datetime(2027, 1, 1), food=100)
        self.create_row(416, "Jan2027", total=100)

        self.assertEqual(get_pk_unique("Jan2027"), 416)
        self.assertEqual(get_total_spend_bulk(["Jan2027"]), {"Jan2027": 100})

    def test_empty_future_month_returns_zero_stats(self):
        self.create_row(289, "Oct2026", date=datetime(2026, 10, 1))
        self.create_row(320, "Oct2026", total=None)

        response = get_month_stats(
            self.factory.get(
                "/dashboard/get_month_stats/", {"sheet_name": "Oct2026"}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "sheet_name": "Oct2026",
                "total_spend": 0,
                "budget_percentage": 0.0,
                "monthly_budget": 200000,
                "avg_daily_spending": 0,
                "days_with_expenses": 0,
            },
        )

    def test_current_month_is_first_even_when_future_sheets_exist(self):
        current_sheet = datetime.now().strftime("%b%Y")
        self.create_row(1, current_sheet)
        self.create_row(2, "Jan2099")

        response = get_sheets(self.factory.get("/dashboard/get_sheets/"))

        payload = json.loads(response.content)
        self.assertEqual(payload["sheets"][0]["value"], current_sheet)


class SheetHeaderNormalizationTests(TestCase):
    def test_real_workbook_headers_map_to_projection_fields(self):
        from expenses_site.utils import normalize_sheet_headers

        headers = normalize_sheet_headers([
            "Automatic withdrawal ",
            "Automatic withdrawal  details",
            "SMBC credit card payment",
            "SMBC credit card payment details",
            "Utility(Gas, Electricity, Water＆Sewage)",
            "Details of utility",
            "Total amount",
        ])

        self.assertEqual(headers, [
            "Automatic_withdrawal",
            "Automatic_withdrawal_com",
            "SMBC_payments",
            "SMBC_card_comments",
            "Utility",
            "Details_utility",
            "Total_amount",
        ])

    def test_sheet_date_parser_supports_current_workbook_format(self):
        from expenses_site.utils import parse_sheet_date

        self.assertEqual(
            parse_sheet_date("2026/2/12"),
            datetime(2026, 2, 12),
        )
        self.assertIsNone(parse_sheet_date(""))
        self.assertIsNone(parse_sheet_date("合計"))
