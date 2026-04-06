import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

def get_google_sheet():
    """Підключення до Google Sheets"""
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    
    # Отримуємо credentials з змінної середовища
    creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Або з файлу
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    
    client = gspread.authorize(creds)
    sheet_id = os.getenv('SPREADSHEET_ID')
    return client.open_by_key(sheet_id)

def save_attendance_to_sheets(worker_name, status, ktu, shift_hours, workshop):
    """Зберігає відмітку в Google Sheets"""
    try:
        sheet = get_google_sheet()
        worksheet = sheet.worksheet('Відмітки')
        
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        worksheet.append_row([
            now, workshop, worker_name, status, ktu, shift_hours
        ])
        return True
    except Exception as e:
        print(f"Google Sheets error: {e}")
        return False
