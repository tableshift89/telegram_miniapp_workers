import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальний клієнт
gc = None
sheet = None

def init_google_sheets():
    """Ініціалізація підключення до Google Sheets"""
    global gc, sheet
    
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        # Отримуємо credentials з змінної середовища
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if not creds_json:
            logger.error("❌ GOOGLE_CREDENTIALS_JSON environment variable not set")
            return False
        
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        gc = gspread.authorize(creds)
        sheet_id = os.getenv('SPREADSHEET_ID')
        if not sheet_id:
            logger.error("❌ SPREADSHEET_ID environment variable not set")
            return False
        
        sheet = gc.open_by_key(sheet_id)
        logger.info(f"✅ Google Sheets connected successfully: {sheet.title}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to connect to Google Sheets: {e}")
        return False

def load_workers_from_sheets():
    """Завантажити працівників з Google Sheets"""
    global sheet
    
    if sheet is None:
        if not init_google_sheets():
            return []
    
    try:
        # Спробуємо отримати аркуш "workers" або перший аркуш
        try:
            worksheet = sheet.worksheet('workers')
        except:
            # Якщо немає аркуша workers, використовуємо перший аркуш
            worksheet = sheet.get_worksheet(0)
        
        records = worksheet.get_all_records()
        
        workers = []
        for row in records:
            # Підтримуємо різні назви колонок
            workshop = row.get('цех') or row.get('workshop') or row.get('Цех', '').strip()
            fullname = row.get('ПІБ') or row.get('fullname') or row.get('name') or row.get('Прізвище', '').strip()
            default_ktu = float(row.get('КТУ_за_умовчанням') or row.get('default_ktu') or 1.0)
            
            if workshop and fullname:
                workers.append({
                    'fullname': fullname,
                    'workshop': workshop,
                    'default_ktu': default_ktu
                })
        
        logger.info(f"✅ Loaded {len(workers)} workers from Google Sheets")
        return workers
    except Exception as e:
        logger.error(f"❌ Failed to load workers from Google Sheets: {e}")
        return []

def save_attendance_to_sheets(worker_name, workshop, status, ktu, shift_hours):
    """Зберігає відмітку в Google Sheets"""
    global sheet
    
    if sheet is None:
        if not init_google_sheets():
            return False
    
    try:
        # Отримуємо або створюємо аркуш для відміток
        try:
            worksheet = sheet.worksheet('attendance')
        except:
            worksheet = sheet.add_worksheet(title='attendance', rows=1000, cols=10)
            # Додаємо заголовки
            worksheet.append_row(['Дата', 'Час', 'Цех', 'ПІБ', 'Статус', 'КТУ', 'Годин'])
        
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        
        # Мапінг статусів для відображення
        status_display = {
            'present': '✅ Присутній',
            'Вщ': '🏖️ Відпустка',
            'Пр': '😷 Прогул',
            'На': '📚 Навчання',
            'Нз': '❌ Неявка'
        }.get(status, status)
        
        worksheet.append_row([
            date_str,
            time_str,
            workshop,
            worker_name,
            status_display,
            ktu,
            shift_hours
        ])
        
        logger.info(f"✅ Saved to Google Sheets: {worker_name} - {status_display}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to save to Google Sheets: {e}")
        return False

def sync_workers_to_local_db():
    """Синхронізує працівників з Google Sheets в локальну БД"""
    from app.database import add_worker, get_all_workers_by_workshop
    
    workers_from_gs = load_workers_from_sheets()
    if not workers_from_gs:
        return False
    
    # Отримуємо поточних працівників з БД
    existing_workers = {}
    for workshop in ['DMT', 'Пакування']:
        existing = get_all_workers_by_workshop(workshop)
        for w in existing:
            key = f"{w['workshop']}|{w['fullname']}"
            existing_workers[key] = True
    
    # Додаємо нових працівників
    added = 0
    for worker in workers_from_gs:
        key = f"{worker['workshop']}|{worker['fullname']}"
        if key not in existing_workers:
            if add_worker(worker['fullname'], worker['workshop']):
                added += 1
    
    logger.info(f"✅ Synced {added} new workers from Google Sheets")
    return True

def get_worksheet_names():
    """Отримати назви всіх аркушів у таблиці"""
    global sheet
    
    if sheet is None:
        if not init_google_sheets():
            return []
    
    try:
        worksheets = sheet.worksheets()
        return [ws.title for ws in worksheets]
    except Exception as e:
        logger.error(f"Failed to get worksheet names: {e}")
        return []
