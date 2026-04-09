import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SPREADSHEET_ID = '1TZMudoqr2GbOZCbfWSWJLqVZ67pZCck766OyDAD11pU'

# Коди операцій
OPERATION_CODES = ['601', '602', '603', '475', '1088', '1256']

# Мапінг статусів для запису в таблицю
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
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
        creds = None
        
        creds_path = 'credentials.json'
        if not os.path.exists(creds_path):
            creds_path = '/opt/render/project/src/credentials.json'
        
        if os.path.exists(creds_path):
            try:
                creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
                logger.info(f"✅ Credentials loaded from {creds_path}")
            except Exception as e:
                logger.error(f"Failed to load credentials from file: {e}")
        
        if not creds:
            creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if creds_json:
                try:
                    import json
                    creds_dict = json.loads(creds_json)
                    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                    logger.info("✅ Credentials loaded from environment variable")
                except Exception as e:
                    logger.error(f"Failed to parse GOOGLE_CREDENTIALS_JSON: {e}")
        
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
    """
    Визначає колонки для кожної дати в таблиці
    Структура: BCD - 1 число, EFG - 2 число, HIJ - 3 число, і т.д.
    """
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
        header_row = all_data[4]  # рядок 5
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # Колонки починаються з B (індекс 1)
        for day_num in range(1, 32):  # до 31 дня
            # Кожен день займає 3 колонки: код, години, КТУ/статус
            col_idx = 1 + (day_num - 1) * 3  # B=1, E=4, H=7, ...
            
            if col_idx < len(header_row):
                # Перевіряємо чи є дата в цій колонці
                cell_value = str(header_row[col_idx]).strip() if col_idx < len(header_row) else ''
                if cell_value == str(day_num) or cell_value == str(day_num):
                    try:
                        date_obj = datetime(current_year, current_month, day_num)
                        date_str = date_obj.strftime("%Y-%m-%d")
                        date_columns[date_str] = {
                            'code_col': col_idx,      # колонка з кодом операції
                            'hours_col': col_idx + 1, # колонка з годинами
                            'value_col': col_idx + 2  # колонка з КТУ/статусом
                        }
                        logger.info(f"📅 Date {date_str}: code_col={col_idx}, value_col={col_idx+2}")
                    except ValueError:
                        pass
        
        logger.info(f"📅 Found {len(date_columns)} date columns")
        return date_columns
    except Exception as e:
        logger.error(f"Error getting date columns: {e}")
        return {}

def get_previous_day_columns(current_date_str: str, date_columns: dict):
    """Отримати колонки попереднього дня (для копіювання коду операції)"""
    current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
    prev_date = current_date - timedelta(days=1)
    prev_date_str = prev_date.strftime("%Y-%m-%d")
    
    if prev_date_str in date_columns:
        return date_columns[prev_date_str]
    return None

def get_workers_for_date(date_str: str, operation_code: str = None):
    """Отримати список працівників для конкретної дати"""
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return []
    
    try:
        worksheet = sheet.get_worksheet(0)
        all_data = worksheet.get_all_values()
        
        date_columns = get_date_columns()
        if date_str not in date_columns:
            logger.warning(f"Date {date_str} not found in sheet")
            return []
        
        current_cols = date_columns[date_str]
        prev_cols = get_previous_day_columns(date_str, date_columns)
        
        workers = []
        for row_idx, row in enumerate(all_data[6:], start=7):
            if len(row) < 1 or not row[0]:
                continue
            
            fullname = str(row[0]).strip()
            if not fullname or fullname == 'Аутсорс' or fullname.startswith('Бригадир'):
                continue
            
            # Беремо код операції з попереднього дня (або поточного, якщо немає попереднього)
            code_col = current_cols['code_col']
            if prev_cols and code_col < len(row):
                # Якщо є попередній день, копіюємо код з нього
                prev_code_col = prev_cols['code_col']
                if prev_code_col < len(row):
                    operation_code = str(row[prev_code_col]).strip()
                else:
                    operation_code = str(row[code_col]).strip() if code_col < len(row) else ''
            else:
                operation_code = str(row[code_col]).strip() if code_col < len(row) else ''
            
            # Перевіряємо чи код операції валідний
            if operation_code not in OPERATION_CODES:
                continue
            
            # Перевіряємо чи вже є відмітка в колонці значень
            value_col = current_cols['value_col']
            already_marked = False
            existing_status = None
            existing_ktu = None
            
            if value_col < len(row):
                value = str(row[value_col]).strip()
                if value:
                    value_lower = value.lower()
                    if value_lower in ['вщ', 'пр', 'на', 'нз', 'в']:
                        already_marked = True
                        if value_lower in ['вщ', 'в']:
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
        
        logger.info(f"📋 Loaded {len(workers)} workers for {date_str}")
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
            logger.error(f"Date {date_str} not found")
            return False
        
        current_cols = date_columns[date_str]
        value_col = current_cols['value_col']
        
        # Визначаємо значення для запису
        if status and status != 'present':
            value = STATUS_TO_SHEET.get(status, 'вщ')
        else:
            hours_str = str(hours) if hours else '9'
            ktu_str = str(ktu).replace('.', ',') if ktu else '1'
            value = f"{hours_str}\n{ktu_str}"
        
        # Оновлюємо комірку з КТУ/статусом
        worksheet.update_cell(row, value_col + 1, value)
        logger.info(f"✅ Updated: row {row}, col {value_col + 1} = {value}")
        
        # Якщо це перший день місяця, також записуємо код операції та години
        # (для наступних днів вони копіюються з попереднього)
        current_date = datetime.strptime(date_str, "%Y-%m-%d")
        if current_date.day == 1:
            code_col = current_cols['code_col']
            hours_col = current_cols['hours_col']
            
            if code_col < 100:
                worksheet.update_cell(row, code_col + 1, operation_code)
                logger.info(f"✅ Updated code: row {row}, col {code_col + 1} = {operation_code}")
            
            if hours_col < 100 and hours:
                worksheet.update_cell(row, hours_col + 1, hours)
                logger.info(f"✅ Updated hours: row {row}, col {hours_col + 1} = {hours}")
        
        save_to_history(date_str, worker_name, operation_code, status, ktu, hours)
        return True
    except Exception as e:
        logger.error(f"Error marking worker: {e}")
        return False

def save_attendance_to_sheets(worker_id: int, status: str, ktu: float, shift_hours: int):
    """Зберігає відмітку в Google Sheets (для сумісності з database.py)"""
    from app.database import get_worker_by_id
    
    worker = get_worker_by_id(worker_id)
    if not worker:
        logger.error(f"Worker {worker_id} not found")
        return False
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    return mark_worker_in_sheet(
        worker_name=worker['fullname'],
        operation_code=worker.get('operation_code', '601'),
        status=status,
        ktu=ktu,
        hours=shift_hours,
        date_str=today,
        row=worker.get('row', 7)
    )

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
        logger.info(f"📝 Saved to history: {worker_name}")
    except Exception as e:
        logger.error(f"Error saving to history: {e}")

def load_workers_from_sheets():
    """Завантажити працівників для локальної БД"""
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return []
    
    try:
        worksheet = sheet.get_worksheet(0)
        all_data = worksheet.get_all_values()
        
        date_columns = get_date_columns()
        if not date_columns:
            return []
        
        # Беремо перший день місяця для визначення кодів операцій
        first_day = min(date_columns.keys())
        first_cols = date_columns[first_day]
        code_col = first_cols['code_col']
        
        workers = []
        for row_idx, row in enumerate(all_data[6:], start=7):
            if len(row) < 1 or not row[0]:
                continue
            fullname = str(row[0]).strip()
            if not fullname or fullname == 'Аутсорс' or fullname.startswith('Бригадир'):
                continue
            
            # Отримуємо код операції з першого дня
            operation_code = str(row[code_col]).strip() if code_col < len(row) else ''
            
            if operation_code not in OPERATION_CODES:
                continue
            
            # Визначаємо цех за кодом
            if operation_code in ['601', '602', '603']:
                workshop = 'DMT'
            else:
                workshop = 'Пакування'
            
            workers.append({
                'id': row_idx,
                'fullname': fullname,
                'workshop': workshop,
                'operation_code': operation_code,
                'default_ktu': 1.0
            })
        
        logger.info(f"📋 Loaded {len(workers)} workers from Google Sheets")
        return workers
    except Exception as e:
        logger.error(f"Error loading workers: {e}")
        return []

def sync_workers_to_local_db():
    """Синхронізація працівників з Google Sheets в локальну БД"""
    from app.database import add_worker_with_code, get_all_workers
    
    workers = load_workers_from_sheets()
    if not workers:
        logger.warning("No workers from Google Sheets to sync")
        return False
    
    existing = {}
    for w in get_all_workers():
        existing[f"{w.get('operation_code', '')}|{w['fullname']}"] = True
    
    added = 0
    for w in workers:
        key = f"{w.get('operation_code', '')}|{w['fullname']}"
        if key not in existing:
            if add_worker_with_code(w['fullname'], w.get('operation_code', '601'), w['workshop']):
                added += 1
                logger.info(f"➕ Added worker: {w['fullname']} ({w['workshop']}, код: {w.get('operation_code', '601')})")
    
    logger.info(f"✅ Synced {added} new workers from Google Sheets")
    return True
