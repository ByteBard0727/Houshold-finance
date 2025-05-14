from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('get_sheet_data/', views.get_sheet_data, name='get_sheet_data'),
    path('get_monthly_expenses/', views.get_monthly_expenses, name='get_monthly_expenses'),
    path('get_sheets/', views.get_sheets, name='get_sheets'),
    path('update_dashboard_data', views.update_dashboard_data, name='update_dashboard_data'),
    path('get_year_total_expense', views.update_dashboard_data, name='get_year_total_expense'),
]