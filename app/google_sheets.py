import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SPREADSHEET_ID = '1TZMudoqr2GbOZCbfWSWJLqVZ67pZCck766OyDAD11pU'

def init_google_sheets():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        creds_path = 'credentials.json'
        if not os.path.exists(creds_path):
            creds_path = '/opt/render/project/src/credentials.json'
        
        if os.path.exists(creds_path):
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
            logger.info(f"✅ Credentials loaded from {creds_path}")
        else:
            creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if creds_json:
                import json
                creds_dict = json.loads(creds_json)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                logger.info("✅ Credentials loaded from environment")
            else:
                logger.error("❌ No credentials found")
                return False
        
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SPREADSHEET_ID)
        logger.info(f"✅ Connected to: {sheet.title}")
        return True
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

def get_worksheet():
    try:
        from app.google_sheets import init_google_sheets, sheet as global_sheet
        if global_sheet is None:
            if not init_google_sheets():
                return None
            from app.google_sheets import sheet
            global_sheet = sheet
        
        try:
            worksheet = global_sheet.worksheet("workers")
        except:
            worksheet = global_sheet.get_worksheet(0)
        
        return worksheet
    except Exception as e:
        logger.error(f"Failed to get worksheet: {e}")
        return None

def load_workers_from_sheets():
    worksheet = get_worksheet()
    if not worksheet:
        return []
    
    try:
        all_data = worksheet.get_all_values()
        if len(all_data) <= 1:
            return []
        
        workers = []
        for row in all_data[1:]:
            if len(row) < 2:
                continue
            workshop = str(row[0]).strip()
            fullname = str(row[1]).strip()
            if not workshop or not fullname:
                continue
            ktu = 1.0
            if len(row) >= 3 and row[2]:
                try:
                    ktu = float(str(row[2]).replace(',', '.'))
                except:
                    pass
            if workshop in ['DMT', 'Пакування']:
                workers.append({'fullname': fullname, 'workshop': workshop, 'default_ktu': ktu})
        
        logger.info(f"Loaded {len(workers)} workers from Google Sheets")
        return workers
    except Exception as e:
        logger.error(f"Error loading workers: {e}")
        return []

def save_attendance_to_sheets(worker_name, workshop, status, ktu, shift_hours):
    worksheet = get_worksheet()
    if not worksheet:
        return False
    
    try:
        sheet = worksheet.spreadsheet
        result_name = f"Attendance_{datetime.now().strftime('%d.%m.%y')}"
        
        try:
            result_ws = sheet.worksheet(result_name)
        except:
            result_ws = sheet.add_worksheet(title=result_name, rows=10000, cols=10)
            result_ws.append_row(['Дата', 'Час', 'Цех', 'ПІБ', 'Статус', 'КТУ', 'Годин'])
        
        now = datetime.now()
        status_display = {
            'present': '✅ Присутній',
            'Вщ': '🏖️ Вихідний',
            'Пр': '😷 Прогул',
            'На': '📚 Відпустка за свій рахунок',
            'Нз': '❌ Не з\'явився'
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
        
        logger.info(f"Saved: {worker_name} - {status_display}")
        return True
    except Exception as e:
        logger.error(f"Save error: {e}")
        return False

def sync_workers_to_local_db():
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

# Глобальна змінна
sheet = None
