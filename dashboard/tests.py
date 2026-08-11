import json
from datetime import datetime

from django.test import RequestFactory, TestCase

from expense_upload.models import Google_Sheets_Data

from .views import (
    get_month_stats,
    get_available_years,
    get_pk_unique,
    get_sheets,
    get_total_spend_bulk,
    get_yearly_summary,
    get_yearly_summary_data,
)


class DynamicMonthlyTotalTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def create_row(self, pk, sheet, total=None, date=None, food=None, smbc=None):
        return Google_Sheets_Data.objects.create(
            PK_Unique=pk,
            Name_sheet=sheet,
            Total_amount=total,
            Date=date,
            Food=food,
            SMBC_payments=smbc,
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

    def test_yearly_summary_uses_total_rows_and_includes_empty_months(self):
        self.create_row(1, "Jan2026", total=100, smbc=10)
        self.create_row(32, "Jan2026", total=214297, smbc=1590)
        self.create_row(64, "Feb2026", total=207419, smbc=1590)

        summary = get_yearly_summary(2026)

        self.assertEqual(len(summary["months"]), 12)
        self.assertEqual(summary["months"][0], {
            "label": "January 2026",
            "shared": "214,297",
            "smbc": "1,590",
            "total": "215,887",
        })
        self.assertEqual(summary["months"][2]["total"], "0")
        self.assertEqual(summary["shared_total"], "421,716")
        self.assertEqual(summary["smbc_total"], "3,180")
        self.assertEqual(summary["total"], "424,896")

    def test_available_years_include_workbook_and_current_year(self):
        self.create_row(1, "Jan2024")

        years = get_available_years()

        self.assertIn(2024, years)
        self.assertIn(datetime.now().year, years)
        self.assertEqual(years, sorted(years, reverse=True))

    def test_yearly_summary_endpoint_returns_selected_year(self):
        self.create_row(1, "Jan2024", total=100, smbc=10)

        response = get_yearly_summary_data(
            self.factory.get("/dashboard/get_yearly_summary/", {"year": "2024"})
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["year"], 2024)
        self.assertEqual(payload["months"][0]["total"], "110")


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
