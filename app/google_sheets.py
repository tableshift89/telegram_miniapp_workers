import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SPREADSHEET_ID = '1TZMudoqr2GbOZCbfWSWJLqVZ67pZCck766OyDAD11pU'

# Коди операцій
OPERATION_CODES = ['601', '602', '603', '475', '1088', '1256']

# Мапінг статусів
STATUS_TO_SHEET = {
    'Вщ': 'вщ',
    'Пр': 'пр',
    'На': 'на',
    'Нз': 'нз'
}

# Глобальні змінні
gc = None
sheet = None

def init_google_sheets():
    """Ініціалізація підключення до Google Sheets"""
    global gc, sheet
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        creds = None
        
        # Перевіряємо різні можливі назви файлу
        possible_names = [
            'credentials.json',
            'gen-lang-client-0963027155-f884e79ef08d.json',
            '/opt/render/project/src/credentials.json',
            '/opt/render/project/src/gen-lang-client-0963027155-f884e79ef08d.json'
        ]
        
        for name in possible_names:
            if os.path.exists(name):
                logger.info(f"✅ Found credentials at: {name}")
                creds = ServiceAccountCredentials.from_json_keyfile_name(name, scope)
                break
        
        if not creds:
            creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if creds_json:
                import json
                creds_dict = json.loads(creds_json)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                logger.info("✅ Credentials loaded from environment variable")
        
        if not creds:
            logger.error("❌ No credentials found")
            return False
        
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SPREADSHEET_ID)
        logger.info(f"✅ Connected to: {sheet.title}")
        return True
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

def get_date_columns():
    """Визначає колонки для кожної дати в таблиці (рядок 5)"""
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return {}
    
    try:
        worksheet = sheet.get_worksheet(0)
        all_data = worksheet.get_all_values()
        
        if len(all_data) < 5:
            return {}
        
        date_columns = {}
        header_row = all_data[4]
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        for col_idx, cell in enumerate(header_row):
            if cell and str(cell).strip().isdigit():
                day_num = int(str(cell).strip())
                try:
                    date_obj = datetime(current_year, current_month, day_num)
                    date_str = date_obj.strftime("%Y-%m-%d")
                    date_columns[date_str] = col_idx
                except ValueError:
                    pass
        
        return date_columns
    except Exception as e:
        logger.error(f"Error getting date columns: {e}")
        return {}

def get_workers_for_date(date_str: str, operation_code: str):
    """Отримати список працівників для конкретної дати та операції"""
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return []
    
    try:
        worksheet = sheet.get_worksheet(0)
        all_data = worksheet.get_all_values()
        
        date_columns = get_date_columns()
        if date_str not in date_columns:
            return []
        
        target_col = date_columns[date_str]
        
        workers = []
        for row_idx, row in enumerate(all_data[6:], start=7):
            if len(row) < 1 or not row[0]:
                continue
            
            fullname = str(row[0]).strip()
            if not fullname or fullname == 'Аутсорс' or fullname.startswith('Бригадир'):
                continue
            
            if target_col >= len(row):
                continue
            
            cell_code = str(row[target_col]).strip()
            if cell_code != operation_code:
                continue
            
            value_col = target_col + 1
            already_marked = False
            existing_status = None
            existing_ktu = None
            
            if value_col < len(row):
                value = str(row[value_col]).strip()
                if value:
                    value_lower = value.lower()
                    if value_lower in ['вщ', 'пр', 'на', 'нз', 'в']:
                        already_marked = True
                        if value_lower == 'вщ' or value_lower == 'в':
                            existing_status = 'Вщ'
                        elif value_lower == 'пр':
                            existing_status = 'Пр'
                        elif value_lower == 'на':
                            existing_status = 'На'
                        elif value_lower == 'нз':
                            existing_status = 'Нз'
                    else:
                        try:
                            val = float(value.replace(',', '.'))
                            if 0.5 <= val <= 2.0:
                                already_marked = True
                                existing_ktu = val
                        except:
                            pass
            
            workers.append({
                'id': row_idx,
                'fullname': fullname,
                'operation_code': operation_code,
                'already_marked': already_marked,
                'existing_status': existing_status,
                'existing_ktu': existing_ktu
            })
        
        return workers
    except Exception as e:
        logger.error(f"Error loading workers: {e}")
        return []

def mark_worker_in_sheet(worker_name: str, operation_code: str, status: str, ktu: float, hours: int, date_str: str, row: int):
    """Записує відмітку в таблицю"""
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return False
    
    try:
        worksheet = sheet.get_worksheet(0)
        date_columns = get_date_columns()
        
        if date_str not in date_columns:
            return False
        
        target_col = date_columns[date_str]
        value_col = target_col + 1
        
        if status and status != 'present':
            value = STATUS_TO_SHEET.get(status, 'вщ')
        else:
            hours_str = str(hours) if hours else '9'
            ktu_str = str(ktu).replace('.', ',') if ktu else '1'
            value = f"{hours_str}\n{ktu_str}"
        
        worksheet.update_cell(row, value_col + 1, value)
        logger.info(f"✅ Updated: row {row}, col {value_col + 1} = {value}")
        
        save_to_history(date_str, worker_name, operation_code, status, ktu, hours)
        return True
    except Exception as e:
        logger.error(f"Error marking worker: {e}")
        return False

def save_to_history(date_str: str, worker_name: str, operation_code: str, status: str, ktu: float, hours: int):
    """Зберігає в аркуш історії"""
    global sheet
    if sheet is None:
        return
    
    try:
        history_name = "Attendance_History"
        try:
            ws = sheet.worksheet(history_name)
        except:
            ws = sheet.add_worksheet(title=history_name, rows=10000, cols=20)
            ws.append_row(['Дата', 'Час', 'ПІБ', 'Код операції', 'Статус', 'КТУ', 'Годин'])
        
        now = datetime.now()
        status_display = {
            'present': 'Присутній',
            'Вщ': 'Вихідний',
            'Пр': 'Прогул',
            'На': 'Відпустка за свій рахунок',
            'Нз': 'Не з\'явився'
        }.get(status, status)
        
        ws.append_row([
            date_str,
            now.strftime("%H:%M:%S"),
            worker_name,
            operation_code,
            status_display,
            ktu if ktu else '',
            hours if hours else ''
        ])
    except Exception as e:
        logger.error(f"Error saving to history: {e}")

def get_all_workers_list():
    """Отримати список всіх працівників"""
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return []
    
    try:
        worksheet = sheet.get_worksheet(0)
        all_data = worksheet.get_all_values()
        
        workers = []
        for row in all_data[6:]:
            if len(row) < 1 or not row[0]:
                continue
            fullname = str(row[0]).strip()
            if fullname and fullname != 'Аутсорс' and not fullname.startswith('Бригадир'):
                workers.append({'fullname': fullname})
        
        return workers
    except Exception as e:
        logger.error(f"Error getting workers list: {e}")
        return []

def load_workers_from_sheets():
    """Завантажити працівників для локальної БД"""
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return []
    
    try:
        worksheet = sheet.get_worksheet(0)
        all_data = worksheet.get_all_values()
        
        workers = []
        for row in all_data[6:]:
            if len(row) < 1 or not row[0]:
                continue
            fullname = str(row[0]).strip()
            if not fullname or fullname == 'Аутсорс' or fullname.startswith('Бригадир'):
                continue
            
            workshop = None
            for col in range(1, min(len(row), 10)):
                cell_value = str(row[col]).strip()
                if cell_value in OPERATION_CODES:
                    if cell_value in ['601', '602', '603']:
                        workshop = 'DMT'
                    else:
                        workshop = 'Пакування'
                    break
            
            if not workshop:
                continue
            
            workers.append({
                'fullname': fullname,
                'workshop': workshop,
                'default_ktu': 1.0
            })
        
        return workers
    except Exception as e:
        logger.error(f"Error loading workers: {e}")
        return []

def sync_workers_to_local_db():
    """Синхронізація з локальною БД"""
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
