import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

gc = None
sheet = None

def init_google_sheets():
    """Ініціалізація підключення до Google Sheets"""
    global gc, sheet
    
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        # Шлях до файлу credentials.json
        creds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
        
        if os.path.exists(creds_path):
            logger.info(f"Found credentials file at: {creds_path}")
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        else:
            logger.warning(f"Credentials file not found at: {creds_path}")
            # Або з змінної середовища
            creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if creds_json:
                import json
                creds_dict = json.loads(creds_json)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                logger.info("Loaded credentials from environment variable")
            else:
                logger.error("❌ No credentials found anywhere")
                return False
        
        gc = gspread.authorize(creds)
        sheet_id = '1TZMudoqr2GbOZCbfWSWJLqVZ67pZCck766OyDAD11pU'
        sheet = gc.open_by_key(sheet_id)
        logger.info(f"✅ Google Sheets connected: {sheet.title}")
        
        # Виводимо список всіх аркушів
        worksheets = sheet.worksheets()
        logger.info(f"Available worksheets: {[ws.title for ws in worksheets]}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed to connect: {e}")
        return False

def load_workers_from_sheets():
    """Завантажити працівників з Google Sheets"""
    global sheet
    
    if sheet is None:
        if not init_google_sheets():
            return []
    
    try:
        # Отримуємо назву аркуша = поточна дата (наприклад "07.04.26")
        sheet_name = datetime.now().strftime("%d.%m.%y")
        logger.info(f"Looking for worksheet: {sheet_name}")
        
        try:
            worksheet = sheet.worksheet(sheet_name)
            logger.info(f"✅ Found worksheet: {sheet_name}")
        except Exception as e:
            logger.warning(f"Worksheet '{sheet_name}' not found: {e}")
            # Спробуємо знайти будь-який аркуш з даними
            worksheets = sheet.worksheets()
            if worksheets:
                # Беремо перший аркуш
                worksheet = worksheets[0]
                logger.info(f"Using first available worksheet: {worksheet.title}")
            else:
                logger.error("No worksheets found")
                return []
        
        # Отримуємо всі записи
        records = worksheet.get_all_records()
        logger.info(f"Raw records from sheet: {records}")
        
        workers = []
        for idx, row in enumerate(records):
            # Підтримуємо різні назви колонок
            workshop = str(row.get('Цех', row.get('workshop', ''))).strip()
            fullname = str(row.get('ПІБ', row.get('fullname', row.get('name', '')))).strip()
            default_ktu = float(row.get('КТУ_за_умовчанням', row.get('ktu', 1.0)))
            
            logger.info(f"Row {idx}: workshop='{workshop}', fullname='{fullname}', ktu={default_ktu}")
            
            if workshop and fullname and workshop in ['DMT', 'Пакування']:
                workers.append({
                    'fullname': fullname,
                    'workshop': workshop,
                    'default_ktu': default_ktu
                })
        
        logger.info(f"✅ Loaded {len(workers)} workers from Google Sheets")
        return workers
    except Exception as e:
        logger.error(f"❌ Failed to load workers: {e}")
        import traceback
        traceback.print_exc()
        return []

def save_attendance_to_sheets(worker_name, workshop, status, ktu, shift_hours):
    """Зберігає відмітку в Google Sheets"""
    global sheet
    
    if sheet is None:
        if not init_google_sheets():
            return False
    
    try:
        # Аркуш для результатів
        result_sheet_name = f"Результати_{datetime.now().strftime('%d.%m.%y')}"
        
        try:
            worksheet = sheet.worksheet(result_sheet_name)
        except:
            worksheet = sheet.add_worksheet(title=result_sheet_name, rows=1000, cols=10)
            worksheet.append_row(['Дата', 'Час', 'Цех', 'ПІБ', 'Статус', 'КТУ', 'Годин'])
            logger.info(f"Created new worksheet: {result_sheet_name}")
        
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        
        status_display = {
            'present': '✅ Присутній',
            'Вщ': '🏖️ Відпустка',
            'Пр': '😷 Прогул',
            'На': '📚 Навчання',
            'Нз': '❌ Неявка'
        }.get(status, status)
        
        worksheet.append_row([
            date_str, time_str, workshop, worker_name, status_display, ktu, shift_hours
        ])
        
        logger.info(f"✅ Saved: {worker_name} - {status_display}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to save: {e}")
        return False

def sync_workers_to_local_db():
    """Синхронізує працівників з Google Sheets в локальну БД"""
    from app.database import add_worker, get_all_workers_by_shop
    
    workers_from_gs = load_workers_from_sheets()
    if not workers_from_gs:
        logger.warning("No workers loaded from Google Sheets")
        return False
    
    # Отримуємо поточних працівників з БД
    existing_workers = {}
    for workshop in ['DMT', 'Пакування']:
        existing = get_all_workers_by_shop(workshop)
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
                logger.info(f"Added new worker: {worker['fullname']} ({worker['workshop']})")
    
    logger.info(f"✅ Synced {added} new workers from Google Sheets")
    return True
