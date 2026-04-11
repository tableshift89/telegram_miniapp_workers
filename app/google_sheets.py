import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import logging
from datetime import datetime, timedelta
import time
from functools import lru_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SPREADSHEET_ID = '1TZMudoqr2GbOZCbfWSWJLqVZ67pZCck766OyDAD11pU'

# Назва головного аркуша (ваш основний табель)
MAIN_SHEET = 'Головна'
# Назва аркуша з довідником ТО
REFERENCE_SHEET = 'Довідник ТО'

OPERATION_CODES = ['601', '602', '603', '475', '1088', '1256']

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

# Кеш для довідника ТО
_to_cache = None
_cache_time = None
CACHE_DURATION = 3600  # 1 година

def get_default_to_for_worker(fullname: str):
    """Отримати стандартну ТО для працівника з довідника (з кешем)"""
    global sheet, _to_cache, _cache_time
    
    if sheet is None:
        if not init_google_sheets():
            return None
    
    try:
        # Перевіряємо кеш
        now = time.time()
        if _to_cache is None or _cache_time is None or (now - _cache_time) > CACHE_DURATION:
            # Завантажуємо весь довідник один раз
            worksheet = sheet.worksheet(REFERENCE_SHEET)
            all_data = worksheet.get_all_values()
            
            _to_cache = {}
            for row in all_data[1:]:
                if len(row) >= 2:
                    name = str(row[0]).strip()
                    default_to = str(row[1]).strip()
                    if name and default_to:
                        _to_cache[name] = default_to
            _cache_time = now
            logger.info(f"📋 Loaded {len(_to_cache)} entries from reference sheet")
        
        return _to_cache.get(fullname)
    except Exception as e:
        logger.error(f"Error getting default TO: {e}")
        return None

def get_date_columns():
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return {}
    
    try:
        worksheet = sheet.worksheet(MAIN_SHEET)
        all_data = worksheet.get_all_values()
        
        if len(all_data) < 2:
            return {}
        
        date_columns = {}
        header_row = all_data[1]
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        col_idx = 2
        
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
        
        return date_columns
    except Exception as e:
        logger.error(f"Error getting date columns: {e}")
        return {}

def get_shift_data(date_str: str):
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return {"ok": False, "error": "No connection"}
    
    try:
        worksheet = sheet.worksheet(MAIN_SHEET)
        all_data = worksheet.get_all_values()
        
        date_columns = get_date_columns()
        if date_str not in date_columns:
            return {"ok": False, "error": f"Date {date_str} not found"}
        
        cols = date_columns[date_str]
        start_col = cols['start_col']
        hours_col = cols['hours_col']
        value_col = cols['value_col']
        
        prev_date = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
        prev_date_str = prev_date.strftime("%Y-%m-%d")
        prev_cols = date_columns.get(prev_date_str)
        
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
            
            if start_col >= len(row):
                continue
            
            current_to = str(row[start_col]).strip() if start_col < len(row) else ''
            current_hours = str(row[hours_col]).strip() if hours_col < len(row) else ''
            current_ktu = str(row[value_col]).strip() if value_col < len(row) else ''
            
            default_to = get_default_to_for_worker(fullname)
            
            if not current_to and default_to:
                current_to = default_to
            
            suggested_to = ''
            suggested_hours = ''
            if prev_cols:
                prev_start_col = prev_cols['start_col']
                prev_hours_col = prev_cols['hours_col']
                if prev_start_col < len(row):
                    suggested_to = str(row[prev_start_col]).strip()
                if prev_hours_col < len(row):
                    suggested_hours = str(row[prev_hours_col]).strip()
            
            status = None
            ktu = None
            current_to_lower = current_to.lower()
            
            if current_to_lower in ['вщ', 'пр', 'на', 'нз', 'в']:
                if current_to_lower in ['вщ', 'в']:
                    status = 'Вщ' if current_to_lower == 'вщ' else 'В'
                elif current_to_lower == 'пр':
                    status = 'Пр'
                elif current_to_lower == 'на':
                    status = 'На'
                elif current_to_lower == 'нз':
                    status = 'Нз'
                current_to = ''
            else:
                try:
                    ktu = float(current_ktu.replace(',', '.')) if current_ktu else None
                except:
                    pass
            
            workers.append({
                'row': row_idx,
                'fullname': fullname,
                'to': current_to if current_to else (default_to or suggested_to),
                'hours': current_hours if current_hours else suggested_hours,
                'status': status,
                'ktu': ktu,
                'suggested_to': suggested_to,
                'suggested_hours': suggested_hours,
                'isOutsourcer': is_outsourcer_section,
                'default_to': default_to
            })
        
        return {"ok": True, "workers": workers, "columns": cols}
    except Exception as e:
        logger.error(f"Error getting shift data: {e}")
        return {"ok": False, "error": str(e)}

def update_shift_data(date_str: str, workers_data: list):
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return {"ok": False, "error": "No connection"}
    
    try:
        worksheet = sheet.worksheet(MAIN_SHEET)
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
            
            if worker.get('status'):
                status_map = {'Вщ': 'вщ', 'В': 'в', 'Пр': 'пр', 'На': 'на', 'Нз': 'нз'}
                value = status_map.get(worker['status'], 'вщ')
                worksheet.update_cell(row, start_col + 1, value)
                worksheet.update_cell(row, hours_col + 1, '')
                worksheet.update_cell(row, value_col + 1, '')
            else:
                if worker.get('to'):
                    worksheet.update_cell(row, start_col + 1, worker['to'])
                
                if worker.get('hours'):
                    worksheet.update_cell(row, hours_col + 1, worker['hours'])
                
                if worker.get('ktu') is not None:
                    value = str(worker['ktu']).replace('.', ',')
                    worksheet.update_cell(row, value_col + 1, value)
            
            updated += 1
            time.sleep(0.1)
        
        save_to_history(date_str, workers_data)
        return {"ok": True, "updated": updated}
    except Exception as e:
        logger.error(f"Error updating shift data: {e}")
        return {"ok": False, "error": str(e)}

def add_worker_to_sheet(fullname: str, workshop: str, is_outsourcer: bool = False):
    """Додати нового працівника в Google Sheets"""
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return False
    
    try:
        worksheet = sheet.worksheet(MAIN_SHEET)
        all_data = worksheet.get_all_values()
        
        outsourcer_row = None
        for i, row in enumerate(all_data, start=1):
            if len(row) > 1 and row[1] == 'Аутсорс':
                outsourcer_row = i
                break
        
        if is_outsourcer:
            if outsourcer_row:
                last_outsourcer_row = outsourcer_row
                for i in range(outsourcer_row + 1, len(all_data) + 1):
                    if i >= len(all_data):
                        last_outsourcer_row = i - 1
                        break
                    if len(all_data[i-1]) < 2 or not all_data[i-1][1]:
                        last_outsourcer_row = i - 1
                        break
                    last_outsourcer_row = i
                
                worksheet.insert_row(['', fullname], last_outsourcer_row + 1)
                logger.info(f"✅ Added outsourcer: {fullname} at row {last_outsourcer_row + 1}")
            else:
                worksheet.append_row(['', 'Аутсорс'])
                worksheet.append_row(['', fullname])
                logger.info(f"✅ Added outsourcer section and worker: {fullname}")
        else:
            if outsourcer_row:
                worksheet.insert_row(['', fullname], outsourcer_row)
                logger.info(f"✅ Added official worker: {fullname} before outsourcer section at row {outsourcer_row}")
            else:
                worksheet.append_row(['', fullname])
                logger.info(f"✅ Added official worker: {fullname} at end")
        
        return True
    except Exception as e:
        logger.error(f"Error adding worker: {e}")
        return False

def save_to_history(date_str: str, workers_data: list):
    global sheet
    if sheet is None:
        return
    
    try:
        history_name = "Attendance_History"
        try:
            ws = sheet.worksheet(history_name)
        except:
            ws = sheet.add_worksheet(title=history_name, rows=10000, cols=20)
            ws.append_row(['Дата', 'Час', 'ПІБ', 'ТО/Статус', 'Години', 'КТУ', 'Аутсорсер'])
        
        now = datetime.now()
        for worker in workers_data:
            to_value = worker.get('status') if worker.get('status') else worker.get('to', '')
            ktu_value = worker.get('ktu') if worker.get('ktu') else ''
            ws.append_row([
                date_str,
                now.strftime("%H:%M:%S"),
                worker.get('fullname', ''),
                to_value,
                worker.get('hours', ''),
                ktu_value,
                'Так' if worker.get('isOutsourcer') else ''
            ])
            time.sleep(0.1)
    except Exception as e:
        logger.error(f"Error saving to history: {e}")

def check_connection():
    """Перевіряє підключення до Google Sheets"""
    global sheet
    if sheet is None:
        return init_google_sheets()
    return True

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
    
    return added > 0

def load_workers_from_sheets():
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return []
    
    try:
        worksheet = sheet.worksheet(MAIN_SHEET)
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
            
            if operation_code in ['601', '602', '603']:
                workshop = 'DMT'
            elif operation_code in ['475', '1088', '1256']:
                workshop = 'Пакування'
            else:
                continue
            
            workers.append({
                'id': row_idx,
                'fullname': fullname,
                'workshop': workshop,
                'operation_code': operation_code,
                'default_ktu': 1.0,
                'isOutsourcer': is_outsourcer_section
            })
        
        return workers
    except Exception as e:
        logger.error(f"Error loading workers: {e}")
        return []
