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
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
            logger.info(f"✅ Credentials loaded from {creds_path}")
        
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
    """
    Визначає колонки для кожної дати в таблиці (рядок 2)
    Формат: злиті комірки C,D,E - 1 число, F,G,H - 2 число, тощо
    """
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return {}
    
    try:
        worksheet = sheet.get_worksheet(0)
        all_data = worksheet.get_all_values()
        
        if len(all_data) < 2:
            return {}
        
        date_columns = {}
        header_row = all_data[1]
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        col_idx = 2  # починаємо з колонки C (індекс 2)
        
        while col_idx < len(header_row):
            cell_value = str(header_row[col_idx]).strip() if col_idx < len(header_row) else ''
            
            if cell_value.isdigit():
                try:
                    date_obj = datetime(current_year, current_month, int(cell_value))
                    date_str = date_obj.strftime("%Y-%m-%d")
                    
                    date_columns[date_str] = {
                        'start_col': col_idx,
                        'hours_col': col_idx + 1,
                        'value_col': col_idx + 2,
                        'day': int(cell_value)
                    }
                    col_idx += 3
                except ValueError:
                    col_idx += 1
            else:
                col_idx += 1
        
        logger.info(f"📅 Found {len(date_columns)} date columns")
        return date_columns
    except Exception as e:
        logger.error(f"Error getting date columns: {e}")
        return {}

def get_shift_data(date_str: str):
    """
    Отримати дані за конкретну дату (ПІБ з колонки B, індекс 1)
    Визначає аутсорсерів (працівники після рядка "Аутсорс")
    """
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return {"ok": False, "error": "No connection"}
    
    try:
        worksheet = sheet.get_worksheet(0)
        all_data = worksheet.get_all_values()
        
        date_columns = get_date_columns()
        if date_str not in date_columns:
            return {"ok": False, "error": f"Date {date_str} not found"}
        
        cols = date_columns[date_str]
        start_col = cols['start_col']
        hours_col = cols['hours_col']
        value_col = cols['value_col']
        
        # Отримуємо дані попереднього дня
        prev_date = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
        prev_date_str = prev_date.strftime("%Y-%m-%d")
        prev_cols = date_columns.get(prev_date_str)
        
        workers = []
        is_outsourcer_section = False  # Флаг для визначення секції аутсорсерів
        
        # Дані починаються з рядка 5 (індекс 4)
        # ПІБ в колонці B (індекс 1)
        for row_idx, row in enumerate(all_data[4:], start=5):
            if len(row) < 2:
                continue
            
            # Перевіряємо чи це рядок "Аутсорс" (початок секції аутсорсерів)
            first_col = str(row[1]).strip() if len(row) > 1 else ''
            if first_col == 'Аутсорс':
                is_outsourcer_section = True
                logger.info(f"📋 Outsourcer section starts at row {row_idx}")
                continue
            
            if not row[1]:
                continue
            
            fullname = str(row[1]).strip()
            # Пропускаємо пусті рядки та заголовки бригадирів
            if not fullname or fullname.startswith('Бригадир'):
                continue
            
            if start_col >= len(row):
                continue
            
            # Поточні значення
            current_to = str(row[start_col]).strip() if start_col < len(row) else ''
            current_hours = str(row[hours_col]).strip() if hours_col < len(row) else ''
            current_value = str(row[value_col]).strip() if value_col < len(row) else ''
            
            # Пропозиції з попереднього дня
            suggested_to = ''
            suggested_hours = ''
            if prev_cols:
                prev_start_col = prev_cols['start_col']
                prev_hours_col = prev_cols['hours_col']
                if prev_start_col < len(row):
                    suggested_to = str(row[prev_start_col]).strip()
                if prev_hours_col < len(row):
                    suggested_hours = str(row[prev_hours_col]).strip()
            
            # Визначаємо статус або КТУ
            status = None
            ktu = None
            current_value_lower = current_value.lower()
            
            if current_value_lower in ['вщ', 'пр', 'на', 'нз', 'в']:
                if current_value_lower in ['вщ', 'в']:
                    status = 'Вщ'
                elif current_value_lower == 'пр':
                    status = 'Пр'
                elif current_value_lower == 'на':
                    status = 'На'
                elif current_value_lower == 'нз':
                    status = 'Нз'
            else:
                try:
                    ktu = float(current_value.replace(',', '.')) if current_value else None
                except:
                    pass
            
            workers.append({
                'row': row_idx,
                'fullname': fullname,
                'to': current_to if current_to else suggested_to,
                'hours': current_hours if current_hours else suggested_hours,
                'status': status,
                'ktu': ktu,
                'suggested_to': suggested_to,
                'suggested_hours': suggested_hours,
                'isOutsourcer': is_outsourcer_section  # Додаємо прапорець аутсорсера
            })
        
        outsourcer_count = sum(1 for w in workers if w['isOutsourcer'])
        logger.info(f"📋 Loaded {len(workers)} workers for {date_str} (outsourcers: {outsourcer_count})")
        return {"ok": True, "workers": workers, "columns": cols}
    except Exception as e:
        logger.error(f"Error getting shift data: {e}")
        return {"ok": False, "error": str(e)}

def update_shift_data(date_str: str, workers_data: list):
    """Оновлює дані в таблиці за конкретну дату"""
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return {"ok": False, "error": "No connection"}
    
    try:
        worksheet = sheet.get_worksheet(0)
        date_columns = get_date_columns()
        
        if date_str not in date_columns:
            return {"ok": False, "error": f"Date {date_str} not found"}
        
        cols = date_columns[date_str]
        start_col = cols['start_col']
        hours_col = cols['hours_col']
        value_col = cols['value_col']
        
        updated = 0
        for worker in workers_data:
            row = worker['row']
            
            if worker.get('to'):
                worksheet.update_cell(row, start_col + 1, worker['to'])
                logger.info(f"✅ Updated TO: row {row}, col {start_col + 1} = {worker['to']}")
            
            if worker.get('hours'):
                worksheet.update_cell(row, hours_col + 1, worker['hours'])
                logger.info(f"✅ Updated hours: row {row}, col {hours_col + 1} = {worker['hours']}")
            
            if worker.get('status'):
                status_map = {'Вщ': 'вщ', 'Пр': 'пр', 'На': 'на', 'Нз': 'нз'}
                value = status_map.get(worker['status'], 'вщ')
                worksheet.update_cell(row, value_col + 1, value)
                logger.info(f"✅ Updated status: row {row}, col {value_col + 1} = {value}")
            elif worker.get('ktu') is not None:
                value = str(worker['ktu']).replace('.', ',')
                worksheet.update_cell(row, value_col + 1, value)
                logger.info(f"✅ Updated KTU: row {row}, col {value_col + 1} = {value}")
            
            updated += 1
        
        save_to_history(date_str, workers_data)
        return {"ok": True, "updated": updated}
    except Exception as e:
        logger.error(f"Error updating shift data: {e}")
        return {"ok": False, "error": str(e)}

def save_to_history(date_str: str, workers_data: list):
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
            ws.append_row(['Дата', 'Час', 'ПІБ', 'ТО', 'Години', 'КТУ/Статус', 'Аутсорсер'])
        
        now = datetime.now()
        for worker in workers_data:
            value = worker.get('status') if worker.get('status') else worker.get('ktu')
            ws.append_row([
                date_str,
                now.strftime("%H:%M:%S"),
                worker.get('fullname', ''),
                worker.get('to', ''),
                worker.get('hours', ''),
                value if value else '',
                'Так' if worker.get('isOutsourcer') else ''
            ])
        logger.info(f"📝 Saved {len(workers_data)} records to history")
    except Exception as e:
        logger.error(f"Error saving to history: {e}")

def check_connection():
    """Перевіряє підключення до Google Sheets"""
    global sheet
    if sheet is None:
        return init_google_sheets()
    return True

def sync_workers_to_local_db():
    """Синхронізація працівників з Google Sheets в локальну БД"""
    from app.database import add_worker, get_all_workers_by_shop
    
    workers = load_workers_from_sheets()
    if not workers:
        logger.warning("No workers from Google Sheets to sync")
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
                logger.info(f"➕ Added worker: {w['fullname']} ({w['workshop']})")
    
    logger.info(f"✅ Synced {added} new workers from Google Sheets")
    return added > 0

def load_workers_from_sheets():
    """Завантажити працівників для локальної БД (ПІБ з колонки B, індекс 1)"""
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
        
        first_day = min(date_columns.keys())
        first_cols = date_columns[first_day]
        start_col = first_cols['start_col']
        
        workers = []
        is_outsourcer_section = False
        
        for row_idx, row in enumerate(all_data[4:], start=5):
            if len(row) < 2:
                continue
            
            first_col = str(row[1]).strip() if len(row) > 1 else ''
            if first_col == 'Аутсорс':
                is_outsourcer_section = True
                continue
            
            if not row[1]:
                continue
            
            fullname = str(row[1]).strip()
            if not fullname or fullname.startswith('Бригадир'):
                continue
            
            operation_code = str(row[start_col]).strip() if start_col < len(row) else ''
            
            if operation_code not in OPERATION_CODES:
                continue
            
            if operation_code in ['601', '602', '603']:
                workshop = 'DMT'
            else:
                workshop = 'Пакування'
            
            workers.append({
                'id': row_idx,
                'fullname': fullname,
                'workshop': workshop,
                'operation_code': operation_code,
                'default_ktu': 1.0,
                'isOutsourcer': is_outsourcer_section
            })
        
        logger.info(f"📋 Loaded {len(workers)} workers from Google Sheets")
        return workers
    except Exception as e:
        logger.error(f"Error loading workers: {e}")
        return []

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
        row=worker.get('row', 5),
        isOutsourcer=worker.get('isOutsourcer', False)
    )

def mark_worker_in_sheet(worker_name: str, operation_code: str, status: str, ktu: float, hours: int, date_str: str, row: int, isOutsourcer: bool = False):
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
        
        cols = date_columns[date_str]
        start_col = cols['start_col']
        hours_col = cols['hours_col']
        value_col = cols['value_col']
        
        if operation_code:
            worksheet.update_cell(row, start_col + 1, operation_code)
        
        if hours:
            worksheet.update_cell(row, hours_col + 1, hours)
        
        if status and status != 'present':
            status_map = {'Вщ': 'вщ', 'Пр': 'пр', 'На': 'на', 'Нз': 'нз'}
            value = status_map.get(status, 'вщ')
            worksheet.update_cell(row, value_col + 1, value)
        elif ktu:
            value = str(ktu).replace('.', ',')
            worksheet.update_cell(row, value_col + 1, value)
        
        logger.info(f"✅ Marked: {worker_name} at row {row} (outsourcer: {isOutsourcer})")
        return True
    except Exception as e:
        logger.error(f"Error marking worker: {e}")
        return False
