import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SPREADSHEET_ID = '1TZMudoqr2GbOZCbfWSWJLqVZ67pZCck766OyDAD11pU'

def get_worksheet():
    """Отримати робочий аркуш"""
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        # Перевіряємо різні шляхи
        possible_paths = [
            'credentials.json',
            '/opt/render/project/src/credentials.json',
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json'),
            os.path.join(os.getcwd(), 'credentials.json')
        ]
        
        creds = None
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"✅ Found credentials at: {path}")
                creds = ServiceAccountCredentials.from_json_keyfile_name(path, scope)
                break
        
        # Якщо не знайшли, пробуємо змінну середовища
        if not creds:
            creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if creds_json:
                import json
                creds_dict = json.loads(creds_json)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                logger.info("✅ Loaded credentials from environment variable")
        
        if not creds:
            logger.error("❌ No credentials found")
            return None
        
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sheet.get_worksheet(0)
        logger.info(f"✅ Connected to: {sheet.title} / {worksheet.title}")
        return worksheet
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return None

def load_workers_from_sheets():
    """Завантажити працівників з Google Sheets"""
    worksheet = get_worksheet()
    if not worksheet:
        return []
    
    try:
        all_data = worksheet.get_all_values()
        logger.info(f"Total rows: {len(all_data)}")
        
        if len(all_data) <= 1:
            return []
        
        workers = []
        for i, row in enumerate(all_data[1:], start=2):
            if len(row) < 3:
                continue
            
            workshop = str(row[0]).strip()
            fullname = str(row[1]).strip()
            
            if not workshop or not fullname:
                continue
            
            try:
                ktu = float(str(row[2]).replace(',', '.'))
            except:
                ktu = 1.0
            
            if workshop in ['DMT', 'Пакування']:
                workers.append({
                    'fullname': fullname,
                    'workshop': workshop,
                    'default_ktu': ktu
                })
        
        logger.info(f"Loaded {len(workers)} workers")
        return workers
    except Exception as e:
        logger.error(f"Error loading: {e}")
        return []

def save_attendance_to_sheets(worker_name, workshop, status, ktu, shift_hours):
    """Зберегти відмітку в Google Sheets"""
    worksheet = get_worksheet()
    if not worksheet:
        return False
    
    try:
        sheet = worksheet.spreadsheet
        result_name = f"Results_{datetime.now().strftime('%d.%m.%y')}"
        
        try:
            result_ws = sheet.worksheet(result_name)
        except:
            result_ws = sheet.add_worksheet(title=result_name, rows=1000, cols=10)
            result_ws.append_row(['Date', 'Time', 'Workshop', 'Name', 'Status', 'KTU', 'Hours'])
        
        now = datetime.now()
        status_display = {
            'present': 'Present',
            'Вщ': 'Vacation',
            'Пр': 'Truancy',
            'На': 'Study',
            'Нз': 'Absence'
        }.get(status, status)
        
        result_ws.append_row([
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            workshop,
            worker_name,
            status_display,
            ktu,
            shift_hours
        ])
        
        logger.info(f"Saved: {worker_name}")
        return True
    except Exception as e:
        logger.error(f"Save error: {e}")
        return False

def sync_workers_to_local_db():
    """Синхронізація з БД"""
    from app.database import add_worker, get_all_workers_by_shop
    
    workers = load_workers_from_sheets()
    if not workers:
        return False
    
    existing = {}
    for workshop in ['DMT', 'Пакування']:
        for w in get_all_workers_by_shop(workshop):
            existing[f"{w['workshop']}|{w['fullname']}"] = True
    
    added = 0
    for w in workers:
        key = f"{w['workshop']}|{w['fullname']}"
        if key not in existing:
            if add_worker(w['fullname'], w['workshop']):
                added += 1
    
    logger.info(f"Synced {added} new workers")
    return True

def init_google_sheets():
    """Ініціалізація"""
    return get_worksheet() is not None
