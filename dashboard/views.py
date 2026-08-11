from django.shortcuts import render
from expense_upload.models import Google_Sheets_Data
from channels.layers import get_channel_layer
import json
from django.db.models import Sum, Max
from asgiref.sync import async_to_sync
from django.http import JsonResponse
from datetime import datetime
from calendar import month_name
from .consumers import DashboardConsumer

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
    """Return the total row's PK, which is the highest PK in the sheet."""
    return (
        Google_Sheets_Data.objects
        .filter(Name_sheet=sheet_name)
        .aggregate(total_pk=Max("PK_Unique"))["total_pk"]
    )

def get_total_spend(sheet_name):
    """Fetches the total spend for the given sheet from row 32 (the total row)."""
    pk_unique_value = get_pk_unique(sheet_name)
    total_entry = Google_Sheets_Data.objects.filter(
        Name_sheet=sheet_name, PK_Unique=pk_unique_value
    ).values("Total_amount").first()
    if not total_entry:
        raise ValueError(f"No total data found for sheet {sheet_name}")
    return total_entry["Total_amount"] or 0

def get_total_spend_bulk(sheet_names):
    """Get total spend for multiple sheets in ONE query - optimized version."""
    if not sheet_names:
        return {}
    
    # Rows are ordered with each sheet's total row first. Keeping the first row
    # per sheet avoids assuming that January always ends at PK 32, etc.
    rows = (
        Google_Sheets_Data.objects
        .filter(Name_sheet__in=sheet_names)
        .values("Name_sheet", "Total_amount", "PK_Unique")
        .order_by("Name_sheet", "-PK_Unique")
    )
    totals_dict = {}
    for entry in rows:
        totals_dict.setdefault(entry["Name_sheet"], entry["Total_amount"] or 0)

    return totals_dict


def get_yearly_summary(year):
    """Build a twelve-month summary from each worksheet's total row."""
    sheet_names = [datetime(year, month, 1).strftime("%b%Y") for month in range(1, 13)]
    rows = (
        Google_Sheets_Data.objects
        .filter(Name_sheet__in=sheet_names)
        .values("Name_sheet", "Total_amount", "SMBC_payments", "PK_Unique")
        .order_by("Name_sheet", "-PK_Unique")
    )
    total_rows = {}
    for row in rows:
        total_rows.setdefault(row["Name_sheet"], row)

    months = []
    shared_year_total = 0
    smbc_year_total = 0
    year_total = 0

    for month in range(1, 13):
        sheet_name = datetime(year, month, 1).strftime("%b%Y")
        total_row = total_rows.get(sheet_name, {})
        shared = round(float(total_row.get("Total_amount") or 0))
        smbc = round(float(total_row.get("SMBC_payments") or 0))
        total = shared + smbc
        months.append({
            "label": f"{month_name[month]} {year}",
            "shared": f"{shared:,}",
            "smbc": f"{smbc:,}",
            "total": f"{total:,}",
        })
        shared_year_total += shared
        smbc_year_total += smbc
        year_total += total

    return {
        "year": year,
        "months": months,
        "shared_total": f"{shared_year_total:,}",
        "smbc_total": f"{smbc_year_total:,}",
        "total": f"{year_total:,}",
    }


def get_available_years():
    """Return workbook years newest first, always including the current year."""
    current_year = datetime.now().year
    years = {current_year}
    sheet_names = (
        Google_Sheets_Data.objects
        .values_list("Name_sheet", flat=True)
        .distinct()
    )
    for sheet_name in sheet_names:
        try:
            years.add(datetime.strptime(sheet_name, "%b%Y").year)
        except (TypeError, ValueError):
            continue
    return sorted(years, reverse=True)

def _get_monthly_expenses(sheet_name):
    """
    Internal helper function.
    Fetch the total spend for the month from row 32 and compute category percentages.
    """
    try:
        total_spend = get_total_spend(sheet_name)
        category_totals = get_category_totals(sheet_name)
        percentages = calculate_category_percentages(total_spend, category_totals)
        return percentages
    except Exception as e:
        raise ValueError(f"Error in calculating monthly expenses: {e}")

def get_category_totals(sheet_name):
    """Aggregates the totals for each expense category in a SINGLE query - optimized."""
    pk_unique_value = get_pk_unique(sheet_name)
    
    # Single database query that aggregates all categories at once
    result = Google_Sheets_Data.objects.filter(
        Name_sheet=sheet_name, 
        PK_Unique__lt=pk_unique_value  # Rows 1-31, excluding the total row
    ).aggregate(
        Food=Sum('Food'),
        Leisure=Sum('Leisure'),
        Utility=Sum('Utility'),
        Automatic_withdrawal=Sum('Automatic_withdrawal'),
        SMBC_payments=Sum('SMBC_payments'),
        Stuff=Sum('Stuff')
    )
    
    # Convert None to 0
    return {key: value or 0 for key, value in result.items()}

def calculate_category_percentages(total_spend, category_totals):
    """Given the total spend and a dictionary of category totals, calculates the percentage for each category."""
    return {
        category: (amount / total_spend) * 100 if total_spend else 0
        for category, amount in category_totals.items()
    }

def get_last_12_sheets():
    """Fetch the last 12 available sheets efficiently."""
    # Get distinct sheet names ordered by the sheet name itself
    sheet_names = list(
        Google_Sheets_Data.objects
        .values_list('Name_sheet', flat=True)
        .distinct()
        .order_by('-Name_sheet')
    )
    
    print("Last 12 Sheets:", sheet_names)
    return sheet_names

def send_websocket_update():
    """Sends a message to WebSocket with updated data."""
    channel_layer = get_channel_layer()
    average_monthly_expenses_value = get_average_monthly_expenses()
    
    async_to_sync(channel_layer.group_send)(
        "dashboard_group",
        {
            "type": "send_dashboard_data",
            "average_monthly_expenses": average_monthly_expenses_value,
        }
    )

#####################
# Dashboard Views   #
#####################

def dashboard(request):
    """Render the main dashboard page."""
    average_monthly_expenses_value = get_average_monthly_expenses()
    yearly_summary = get_yearly_summary(datetime.now().year)
    
    return render(request, 'index.html', {
        'average_monthly_expenses': average_monthly_expenses_value,
        'yearly_summary': yearly_summary,
        'available_years': get_available_years(),
    })


def get_yearly_summary_data(request):
    """Return a selectable year's summary for the dashboard table."""
    try:
        year = int(request.GET.get("year", ""))
    except (TypeError, ValueError):
        return JsonResponse({"error": "A valid year is required."}, status=400)

    if year not in get_available_years():
        return JsonResponse({"error": "That year is not available."}, status=404)
    return JsonResponse(get_yearly_summary(year))

def get_average_monthly_expenses():
    """Calculate average monthly expenses based on the last 12 sheets - optimized."""
    sheet_names = get_last_12_sheets()
    
    if not sheet_names:
        return (0, 0)
    
    # Get all totals in ONE query
    totals_dict = get_total_spend_bulk(sheet_names)
    
    total_expenses = sum(totals_dict.values())
    avg_month_exp = total_expenses / len(sheet_names) if sheet_names else 0
    
    print("running get_average_monthly_expenses function")
    return (round(avg_month_exp, 2), total_expenses)

def get_year_total_expense():
    """Get total expenses for the last 12 months - optimized."""
    sheet_names = get_last_12_sheets()
    
    if not sheet_names:
        return 0
    
    # Get all totals in ONE query
    totals_dict = get_total_spend_bulk(sheet_names)
    total_expenses = sum(totals_dict.values())
    
    print("running the total year expense")
    return total_expenses

def update_dashboard_data(request=None):
    """Fetch data for the line chart showing monthly trends - optimized."""
    sheet_names = get_last_12_sheets()
    
    # Get all totals in ONE query instead of 12 separate queries
    totals_dict = get_total_spend_bulk(sheet_names)
    
    # Maintain order and convert to list
    total_costs = [totals_dict.get(sheet, 0) for sheet in sheet_names]

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
        return JsonResponse(dashboard_data)
    return None

def get_sheets(request):
    """Fetch available sheets (months/years) dynamically in chronological order."""
    # Get distinct sheet names
    sheet_names = list(
        Google_Sheets_Data.objects
        .values_list('Name_sheet', flat=True)
        .distinct()
    )
    
    # Helper function to convert sheet name to sortable date
    def sheet_to_date(sheet_name):
        try:
            # Parse "Jan2024" format to datetime
            return datetime.strptime(sheet_name, "%b%Y")
        except ValueError:
            return datetime.min  # Put invalid formats at the beginning
    
    # Sort by date (most recent first)
    sheet_names.sort(key=sheet_to_date, reverse=True)

    # Future worksheet templates may already exist. Prefer the actual current
    # month for both dashboard selectors, then retain newest-first ordering for
    # every other available sheet.
    current_sheet = datetime.now().strftime("%b%Y")
    if current_sheet in sheet_names:
        sheet_names.remove(current_sheet)
        sheet_names.insert(0, current_sheet)
    
    # Limit to 12 most recent
    formatted_sheets = [{"name": sheet, "value": sheet} for sheet in sheet_names]
    
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
    """Fetch detailed categorized expenses for the selected sheet."""
    sheet_name = request.GET.get("sheet_name")
    if not sheet_name or sheet_name.strip() == "":
        return JsonResponse({"error": "No sheet name provided"}, status=400)

    # Get daily data (rows 1-31, excluding the total row)
    pk_unique_value = get_pk_unique(sheet_name)
    
    query_results = Google_Sheets_Data.objects.filter(
        Name_sheet=sheet_name,
        PK_Unique__lt=pk_unique_value
    ).values(
        "Date", "Food", "Leisure", "Utility", 
        "Automatic_withdrawal", "SMBC_payments", "Stuff"
    ).order_by('PK_Unique')
    
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

#####################
# Chart View Options#
#####################

def get_daily_expenses(request):
    """Get daily expenses for the selected month."""
    sheet_name = request.GET.get("sheet_name")
    
    if not sheet_name:
        # Default to latest sheet
        sheets = get_last_12_sheets()
        sheet_name = sheets[0] if sheets else None
    
    if not sheet_name:
        return JsonResponse({"error": "No sheet available"}, status=404)
    
    # Get daily data (rows 1-31, excluding total row 32)
    pk_unique_value = get_pk_unique(sheet_name)
    
    daily_data = Google_Sheets_Data.objects.filter(
        Name_sheet=sheet_name,
        PK_Unique__lt=pk_unique_value
    ).values('Date', 'Food', 'Leisure', 'Utility', 
             'Automatic_withdrawal', 'SMBC_payments', 'Stuff').order_by('PK_Unique')
    
    dates = []
    amounts = []
    
    for entry in daily_data:
        if entry['Date']:
            # Calculate daily total from all categories
            daily_total = sum([
                float(entry.get('Food') or 0),
                float(entry.get('Leisure') or 0),
                float(entry.get('Utility') or 0),
                float(entry.get('Automatic_withdrawal') or 0),
                float(entry.get('SMBC_payments') or 0),
                float(entry.get('Stuff') or 0)
            ])
            
            if daily_total > 0:  # Only include days with expenses
                date_obj = entry['Date'] if isinstance(entry['Date'], datetime) else datetime.strptime(str(entry['Date']), '%Y-%m-%d')
                dates.append(date_obj.strftime('%m/%d'))
                amounts.append(daily_total)
    
    return JsonResponse({
        "labels": dates,
        "values": amounts,
        "view_type": "daily"
    })

def get_weekly_expenses(request):
    """Get weekly aggregated expenses for the selected month."""
    sheet_name = request.GET.get("sheet_name")
    
    if not sheet_name:
        sheets = get_last_12_sheets()
        sheet_name = sheets[0] if sheets else None
    
    if not sheet_name:
        return JsonResponse({"error": "No sheet available"}, status=404)
    
    pk_unique_value = get_pk_unique(sheet_name)
    
    # Get daily data
    daily_data = list(Google_Sheets_Data.objects.filter(
        Name_sheet=sheet_name,
        PK_Unique__lt=pk_unique_value
    ).values('Date', 'Food', 'Leisure', 'Utility', 
             'Automatic_withdrawal', 'SMBC_payments', 'Stuff').order_by('PK_Unique'))
    
    # Group by weeks (1-7 = Week 1, 8-14 = Week 2, etc.)
    weeks = {1: 0, 2: 0, 3: 0, 4: 0}  # Initialize 4 weeks
    
    for entry in daily_data:
        if entry['Date']:
            date_obj = entry['Date'] if isinstance(entry['Date'], datetime) else datetime.strptime(str(entry['Date']), '%Y-%m-%d')
            day = date_obj.day
            
            # Calculate week number (1-4 only)
            if day <= 7:
                week_num = 1
            elif day <= 14:
                week_num = 2
            elif day <= 21:
                week_num = 3
            else:
                week_num = 4  # Days 22-31 all go to week 4
            
            # Sum all categories for this day
            daily_total = sum([
                float(entry.get('Food') or 0),
                float(entry.get('Leisure') or 0),
                float(entry.get('Utility') or 0),
                float(entry.get('Automatic_withdrawal') or 0),
                float(entry.get('SMBC_payments') or 0),
                float(entry.get('Stuff') or 0)
            ])
            weeks[week_num] += daily_total
    
    labels = [f"Week {w}" for w in sorted(weeks.keys())]
    values = [weeks[w] for w in sorted(weeks.keys())]
    
    return JsonResponse({
        "labels": labels,
        "values": values,
        "view_type": "weekly",
        "sheet_name": sheet_name
    })


def get_monthly_overview(request):
    # 1️⃣ Get distinct sheet names
    sheet_names = list(
        Google_Sheets_Data.objects
        .values_list('Name_sheet', flat=True)
        .distinct()
    )

    # 2️⃣ Convert to real dates for sorting
    def sheet_to_date(sheet_name):
        try:
            return datetime.strptime(sheet_name, "%b%Y")
        except ValueError:
            return datetime.min

    # Sort oldest → newest (Jan2024 → Jan2025)
    sheet_names.sort(key=sheet_to_date)

    # 3️⃣ Get totals in ONE optimized query
    totals_dict = get_total_spend_bulk(sheet_names)

    # 4️⃣ Maintain correct order
    labels = sheet_names
    values = [totals_dict.get(sheet, 0) for sheet in sheet_names]

    return JsonResponse({
        "labels": labels,
        "values": values
    })



def get_month_stats(request):
    """Get statistics for a specific month."""
    sheet_name = request.GET.get("sheet_name")
    
    if not sheet_name:
        sheets = get_last_12_sheets()
        sheet_name = sheets[0] if sheets else None
    
    if not sheet_name:
        return JsonResponse({"error": "No sheet available"}, status=404)
    
    try:
        # Get total spend for the month
        total_spend = get_total_spend(sheet_name)
        
        # Budget per month (200,000 yen)
        monthly_budget = 200000
        
        # Calculate budget usage percentage
        budget_percentage = (total_spend / monthly_budget) * 100 if monthly_budget > 0 else 0
        
        # Calculate average daily spending
        pk_unique_value = get_pk_unique(sheet_name)
        
        # Get daily data to calculate average
        daily_data = Google_Sheets_Data.objects.filter(
            Name_sheet=sheet_name,
            PK_Unique__lt=pk_unique_value
        ).values('Date', 'Food', 'Leisure', 'Utility', 
                 'Automatic_withdrawal', 'SMBC_payments', 'Stuff')
        
        # Count days with expenses and calculate total
        days_with_expenses = 0
        daily_totals = []
        
        for entry in daily_data:
            if entry['Date']:
                daily_total = sum([
                    float(entry.get('Food') or 0),
                    float(entry.get('Leisure') or 0),
                    float(entry.get('Utility') or 0),
                    float(entry.get('Automatic_withdrawal') or 0),
                    float(entry.get('SMBC_payments') or 0),
                    float(entry.get('Stuff') or 0)
                ])
                if daily_total > 0:
                    daily_totals.append(daily_total)
                    days_with_expenses += 1
        
        # Calculate average daily spending
        avg_daily_spending = sum(daily_totals) / days_with_expenses if days_with_expenses > 0 else 0
        
        return JsonResponse({
            "sheet_name": sheet_name,
            "total_spend": total_spend,
            "budget_percentage": round(budget_percentage, 1),
            "monthly_budget": monthly_budget,
            "avg_daily_spending": round(avg_daily_spending, 2),
            "days_with_expenses": days_with_expenses
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
