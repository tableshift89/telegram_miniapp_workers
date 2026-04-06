import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

gc = None
sheet = None

# ID вашої Google Таблиці
SPREADSHEET_ID = '1TZMudoqr2GbOZCbfWSWJLqVZ67pZCck766OyDAD11pU'

def init_google_sheets():
    """Ініціалізація підключення до Google Sheets"""
    global gc, sheet
    
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        # Шлях до файлу credentials.json в корені проекту
        creds_path = '/opt/render/project/src/credentials.json'
        
        # Також перевіряємо локальний шлях
        if not os.path.exists(creds_path):
            creds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
        
        if os.path.exists(creds_path):
            logger.info(f"✅ Found credentials at: {creds_path}")
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        else:
            # Перевіряємо змінну середовища
            creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if creds_json:
                import json
                creds_dict = json.loads(creds_json)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                logger.info("✅ Loaded credentials from environment variable")
            else:
                logger.error("❌ No credentials found")
                return False
        
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SPREADSHEET_ID)
        logger.info(f"✅ Connected to Google Sheet: {sheet.title}")
        
        # Виводимо всі аркуші
        worksheets = sheet.worksheets()
        logger.info(f"📋 Available worksheets: {[ws.title for ws in worksheets]}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

def load_workers_from_sheets():
    """Завантажити працівників з Google Sheets"""
    global sheet
    
    if sheet is None:
        if not init_google_sheets():
            return []
    
    try:
        # Беремо перший аркуш
        worksheet = sheet.get_worksheet(0)
        logger.info(f"📄 Using worksheet: {worksheet.title}")
        
        # Отримуємо всі дані
        all_data = worksheet.get_all_values()
        logger.info(f"📊 Total rows: {len(all_data)}")
        
        if len(all_data) < 2:
            logger.warning("No data rows found (need header + at least 1 data row)")
            return []
        
        # Перший рядок - заголовки
        headers = all_data[0]
        logger.info(f"📋 Headers: {headers}")
        
        # Знаходимо індекси колонок (підтримуємо різні назви)
        col_idx = {'workshop': 0, 'fullname': 1, 'ktu': 2}  # за замовчуванням
        
        for idx, header in enumerate(headers):
            header_clean = str(header).strip().lower()
            if 'цех' in header_clean or 'workshop' in header_clean:
                col_idx['workshop'] = idx
            elif 'піб' in header_clean or 'fullname' in header_clean or 'name' in header_clean or 'прізвище' in header_clean:
                col_idx['fullname'] = idx
            elif 'кту' in header_clean or 'ktu' in header_clean:
                col_idx['ktu'] = idx
        
        logger.info(f"🔍 Column mapping: {col_idx}")
        
        workers = []
        for row_idx, row in enumerate(all_data[1:], start=2):
            if len(row) <= max(col_idx.values()):
                logger.warning(f"Row {row_idx} has insufficient columns: {len(row)}")
                continue
            
            workshop = str(row[col_idx['workshop']]).strip()
            fullname = str(row[col_idx['fullname']]).strip()
            
            # Пропускаємо порожні рядки
            if not workshop or not fullname:
                continue
            
            # Отримуємо КТУ
            try:
                ktu_str = row[col_idx['ktu']].strip().replace(',', '.')
                default_ktu = float(ktu_str) if ktu_str else 1.0
            except (ValueError, IndexError):
                default_ktu = 1.0
            
            # Перевіряємо чи цех правильний
            if workshop in ['DMT', 'Пакування']:
                workers.append({
                    'fullname': fullname,
                    'workshop': workshop,
                    'default_ktu': default_ktu
                })
                logger.info(f"✅ Row {row_idx}: {workshop} | {fullname} | KTU: {default_ktu}")
            else:
                logger.warning(f"Row {row_idx}: Unknown workshop '{workshop}'")
        
        logger.info(f"✅ Total workers loaded: {len(workers)}")
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
        # Аркуш для результатів з датою
        result_sheet_name = f"Результати_{datetime.now().strftime('%d.%m.%y')}"
        
        try:
            worksheet = sheet.worksheet(result_sheet_name)
        except:
            worksheet = sheet.add_worksheet(title=result_sheet_name, rows=1000, cols=10)
            worksheet.append_row(['Дата', 'Час', 'Цех', 'ПІБ', 'Статус', 'КТУ', 'Годин'])
            logger.info(f"✅ Created worksheet: {result_sheet_name}")
        
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
        
        logger.info(f"✅ Saved to Google Sheets: {worker_name} - {status_display}")
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
    
    # Отримуємо поточних працівників
    existing_workers = {}
    for workshop in ['DMT', 'Пакування']:
        existing = get_all_workers_by_shop(workshop)
        for w in existing:
            key = f"{w['workshop']}|{w['fullname']}"
            existing_workers[key] = True
    
    # Додаємо нових
    added = 0
    for worker in workers_from_gs:
        key = f"{worker['workshop']}|{worker['fullname']}"
        if key not in existing_workers:
            if add_worker(worker['fullname'], worker['workshop']):
                added += 1
                logger.info(f"➕ Added new worker: {worker['fullname']} ({worker['workshop']})")
    
    logger.info(f"✅ Synced {added} new workers from Google Sheets")
    return True
