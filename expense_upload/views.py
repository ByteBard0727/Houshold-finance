from django.shortcuts import render
# Create your views here.
import pandas as pd
from django.shortcuts import render
from django.contrib import messages
from .forms import FileUploadForm
from .models import Google_Sheets_Data  
from django.http import HttpResponse
from expenses_site.utils import fetch_google_sheet_data


def upload(request):
    return HttpResponse('this will be the upload and data ingestion page')

def display_sheet_data(request):
    spreadsheet_id = '1Jn04_Hc_XHs3MxAFoCYFlruLIparHOqL8Q_PHUiuZ68'
    range_name = 'Jan2024!A1:O33'
    df = fetch_google_sheet_data('Jan2024!', 'A1:O33')
    
    if df.empty:
        context= {'No data mew'}
    else:
        table_html = df.to_html(index=False)
    return render(request, 'upload_page.html', {'table_html': table_html})

#def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            try:
                # Determine file type and read
                if uploaded_file.name.endswith('.csv'):
                    data = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(('.xls', '.xlsx')):
                    data = pd.read_excel(uploaded_file)
                else:
                    messages.error(request, "Unsupported file type.")
                    return render(request, 'upload.html', {'form': form})

                # Ensure the necessary columns are in the uploaded file
                required_columns = {
                    'UserID', 'Username', 'Date', 'Food', 'Stuff', 'Leisure', 
                    'Automatic_withdrawal', 'Automatic_withdrawal_com', 'SMBC_payments', 
                    'SMBC_card_comments', 'Utility', 'Details_utility', 'Total_amount'
                }

                if not required_columns.issubset(set(data.columns)):
                    messages.error(request, "File does not have the required columns.")
                    return render(request, 'upload.html', {'form': form})

                # Process the data and insert into the model
                for _, row in data.iterrows():
                    Google_Sheets_Data.objects.create(
                        UserID=row['UserID'],
                        Username=row['Username'],
                        Date=row['Date'],  # Ensure the Date column is properly formatted
                        Food=row['Food'],
                        Stuff=row['Stuff'],
                        Leisure=row['Leisure'],
                        Automatic_withdrawal=row['Automatic_withdrawal'],
                        Automatic_withdrawal_com=row['Automatic_withdrawal_com'],
                        SMBC_payments=row['SMBC_payments'],
                        SMBC_card_comments=row['SMBC_card_comments'],
                        Utility=row['Utility'],
                        Details_utility=row['Details_utility'],
                        Total_amount=row['Total_amount']
                    )
                messages.success(request, "File uploaded and data saved successfully.")
            except Exception as e:
                messages.error(request, f"Error processing file: {e}")
        else:
            messages.error(request, "Invalid form submission.")
    else:
        form = FileUploadForm()
    
    return render(request, 'upload_page.html', {'form': form})