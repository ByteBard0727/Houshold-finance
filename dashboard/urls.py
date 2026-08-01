from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('get_sheet_data/', views.get_sheet_data, name='get_sheet_data'),
    path('get_monthly_expenses/', views.get_monthly_expenses, name='get_monthly_expenses'),
    path('get_sheets/', views.get_sheets, name='get_sheets'),
    path('update_dashboard_data', views.update_dashboard_data, name='update_dashboard_data'),
    path('get_year_total_expense', views.get_year_total_expense, name='get_year_total_expense'),
    
    # Chart view options
    path('get_daily_expenses/', views.get_daily_expenses, name='get_daily_expenses'),
    path('get_weekly_expenses/', views.get_weekly_expenses, name='get_weekly_expenses'),
    path('get_monthly_overview/', views.get_monthly_overview, name='get_monthly_overview'),
    
    # New endpoint for month stats
    path('get_month_stats/', views.get_month_stats, name='get_month_stats'),
]