from django.shortcuts import render
from expense_upload.models import Google_Sheets_Data
from channels.layers import get_channel_layer
import json
from django.db.models import Sum
from asgiref.sync import async_to_sync
from django.http import JsonResponse
from datetime import datetime
from .consumers import DashboardConsumer
from django.db.models import Max

# Global variable for caching dashboard data
global_dashboard_data = {}

#####################
# Helper Functions  #
#####################

def get_month_number(sheet_name):
    """Helper function to map sheet name (e.g., Jan2024) to month number."""
    month_map = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }
    month_abbr = sheet_name[:3]
    return month_map.get(month_abbr)

def get_pk_unique(sheet_name):
    """Helper function to get PK_Unique value based on the month name."""
    month_num = get_month_number(sheet_name)
    return 32 * month_num if month_num else None

def dynamic_year_expense():
    nr_of_years = 0
    range_of_pk = 3850

def get_total_spend(sheet_name):
    """Fetches the total spend for the given sheet from the record with the appropriate PK_Unique value."""
    pk_unique_value = get_pk_unique(sheet_name)
    total_entry = Google_Sheets_Data.objects.filter(
        Name_sheet=sheet_name, PK_Unique=pk_unique_value
    ).values("Total_amount").first()
    if not total_entry or total_entry.get("Total_amount") is None:
        raise ValueError(f"No total data found for sheet {sheet_name}")
    return total_entry["Total_amount"]

def _get_monthly_expenses(sheet_name):
    """
    Internal helper function.
    Fetch the total spend for the month from the record with the correct PK_Unique 
    (32 for Jan2024, 64 for Feb2024, etc.) and compute category percentages.
    """
    try:
        total_spend = get_total_spend(sheet_name)  # Get the total spending for the month
        category_totals = get_category_totals(sheet_name)  # Get the category totals for the month
        percentages = calculate_category_percentages(total_spend, category_totals)  # Calculate category percentages
        return percentages
    except Exception as e:
        raise ValueError(f"Error in calculating monthly expenses: {e}")


def get_category_totals(sheet_name):
    """Aggregates the totals for each expense category (up to and including the total row) for the given sheet."""
    pk_unique_value = get_pk_unique(sheet_name)
    categories = ["Food", "Leisure", "Utility", "Automatic_withdrawal", "SMBC_payments", "Stuff"]
    totals = {}
    for category in categories:
        agg_result = Google_Sheets_Data.objects.filter(
            Name_sheet=sheet_name, PK_Unique__lte=pk_unique_value
        ).aggregate(total=Sum(category))
        totals[category] = agg_result["total"] or 0
    return totals

def calculate_category_percentages(total_spend, category_totals):
    """Given the total spend and a dictionary of category totals, calculates the percentage for each category."""
    return {
        category: (amount / total_spend) * 100 if total_spend else 0
        for category, amount in category_totals.items()
    }

def get_last_12_sheets():
    """Fetch the last 12 available sheets using PK_Unique (32 rows per sheet), even across year boundaries."""
    # Get the maximum PK_Unique value (most recent month)
    max_pk_unique = Google_Sheets_Data.objects.aggregate(Max('PK_Unique'))['PK_Unique__max']
    
    # Calculate the starting PK_Unique for the last 12 sheets
    sheet_range = []
    for i in range(12):
        # Calculate the PK_Unique for each sheet, which is decremented by 32 for each previous month
        sheet_range.append(max_pk_unique - (i * 32))
    
    # Query the sheets corresponding to the calculated PK_Unique values
    sheets = Google_Sheets_Data.objects.filter(PK_Unique__in=sheet_range).values('Name_sheet', 'PK_Unique').distinct()
    
    # Sort the sheets by PK_Unique in descending order (most recent sheet first)
    sheet_names = [sheet['Name_sheet'] for sheet in sorted(sheets, key=lambda x: x['PK_Unique'])]
    
    print("Last 12 Sheets:", sheet_names)  # Debugging: Check the sheets fetched
    return sheet_names

def send_websocket_update():
    """Sends a message to WebSocket with updated data."""
    channel_layer = get_channel_layer()
    # Fetch average monthly expenses
    average_monthly_expenses_value = get_average_monthly_expenses()
    # Send the updated data to the WebSocket
    async_to_sync(channel_layer.group_send)(
        "dashboard_group",  # You should ensure the group name is the same across WebSocket consumers
        {
            "type": "send_dashboard_data",  # You will need to handle this in your WebSocket consumer
            "average_monthly_expenses": average_monthly_expenses_value,
        }
    )

#####################
# Dashboard Views   #
#####################

def dashboard(request):
    """Render the main dashboard page and send data over WebSocket."""
    average_monthly_expenses_value = get_average_monthly_expenses()
    get_total_year_exp = get_year_total_expense()
    # Trigger the WebSocket update with the latest data
    send_websocket_update()
    return render(request, 'index.html', {
        'average_monthly_expenses': average_monthly_expenses_value
    })

def get_average_monthly_expenses():
    """Calculate average monthly expenses based on the last 12 sheets in the database."""
    sheet_names = get_last_12_sheets()
    total_expenses = 0
    sheet_count = len(sheet_names)
    

    for sheet_name in sheet_names:
        total_spend = get_total_spend(sheet_name)
        total_expenses += total_spend
    avg_month_exp = total_expenses / sheet_count if sheet_count > 0 else 0
    print("running get_average_monthly_expenses function")
    return (round(avg_month_exp, 2),(total_spend))

def get_year_total_expense():
    sheet_names = get_last_12_sheets()
    total_expenses = 0

    for sheet_name in sheet_names:
        total_spend = get_total_spend(sheet_name)
        total_expenses += total_spend
    print("running the total year expense")
    return total_expenses


# Example logging inside the function
def update_dashboard_data(request=None):
    sheet_names = get_last_12_sheets()
    total_costs = [get_total_spend(sheet_name) for sheet_name in sheet_names]

    dashboard_data = {
        "data": [
            sheet_names,
            total_costs
        ],
        "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # Send the data to the WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "dashboard_group",
        {
            "type": "send_dashboard_data",
            "data": dashboard_data
        }
    )

    if request:
        return JsonResponse({"status": "success", "message": "Data sent to WebSocket"})
    return None


def get_sheets(request):
    """Fetch available sheets (months/years) dynamically."""
    expenses = Google_Sheets_Data.objects.values_list("Date", flat=True)
    sheet_names = list(set(Date.strftime("%b%Y") for Date in expenses if Date))
    sheet_names.sort(key=lambda x: datetime.strptime(x, "%b%Y"), reverse=True)
    formatted_sheets = [{"name": sheet, "value": sheet} for sheet in sheet_names[:12]]
    return JsonResponse({"sheets": formatted_sheets})

def get_monthly_expenses(request):
    """Endpoint: Return monthly expense percentages as JSON."""
    sheet_name = request.GET.get("sheet_name")
    if not sheet_name or sheet_name.strip() == "":
        return JsonResponse({"error": "No sheet name provided"}, status=400)
    try:
        result = _get_monthly_expenses(sheet_name)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def get_sheet_data(request):
    """Fetch detailed categorized expenses for the selected sheet and merge with the monthly breakdown."""
    sheet_name = request.GET.get("sheet_name")
    if not sheet_name or sheet_name.strip() == "":
        return JsonResponse({"error": "No sheet name provided"}, status=400)

    query_results = Google_Sheets_Data.objects.filter(Name_sheet=sheet_name).values(
        "Date", "Food", "Leisure", "Utility", "Automatic_withdrawal", "SMBC_payments", "Stuff"
    )
    data_list = list(query_results)
    if not data_list:
        return JsonResponse({"error": "No data found for selected sheet"}, status=404)

    categorized_data = categorize_expenses(data_list)

    try:
        monthly_expenses = _get_monthly_expenses(sheet_name)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    categorized_data["monthly_expenses"] = monthly_expenses
    return JsonResponse(categorized_data)

def categorize_expenses(data):
    """Build arrays for each expense category from the detailed sheet data."""
    dates = []
    food, leisure, utility, withdrawals, smbc, stuff = [], [], [], [], [], []

    for entry in data:
        dates.append(entry.get("Date", "Unknown"))
        food.append(safe_float(entry.get("Food", 0)))
        leisure.append(safe_float(entry.get("Leisure", 0)))
        utility.append(safe_float(entry.get("Utility", 0)))
        withdrawals.append(safe_float(entry.get("Automatic_withdrawal", 0)))
        smbc.append(safe_float(entry.get("SMBC_payments", 0)))
        stuff.append(safe_float(entry.get("Stuff", 0)))

    return {
        "dates": dates,
        "food": food,
        "leisure": leisure,
        "utility": utility,
        "automatic_withdrawals": withdrawals,
        "smbc_payments": smbc,
        "stuff": stuff,
    }

def safe_float(value):
    """Helper function to safely convert values to float."""
    try:
        return float(value) if value is not None else 0
    except (ValueError, TypeError):
        return 0
