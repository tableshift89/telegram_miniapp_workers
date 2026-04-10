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

# Мапінг статусів
STATUS_MAPPING = {
    'Вщ': 'Вщ', 'Пр': 'Пр', 'На': 'На', 'Нз': 'Нз', 'В': 'Вщ'
}

# Глобальні змінні
gc = None
sheet = None

def init_google_sheets():
    global gc, sheet
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
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

def get_date_columns():
    """
    Визначає колонки для кожної дати в таблиці (рядок 2)
    Формат: злиті комірки C,D,E - 1 число, F,G,H - 2 число, I,J,K - 3 число, і т.д.
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
        header_row = all_data[1]  # рядок 2 (індекс 1)
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # Пошук дат у злитих комірках
        # Кожна дата займає 3 колонки: TO, Години, КТУ/Статус
        col_idx = 2  # починаємо з колонки C (індекс 2)
        day_num = 1
        
        while col_idx < len(header_row):
            cell_value = str(header_row[col_idx]).strip() if col_idx < len(header_row) else ''
            
            # Перевіряємо чи це число (день місяця)
            if cell_value.isdigit():
                try:
                    date_obj = datetime(current_year, current_month, int(cell_value))
                    date_str = date_obj.strftime("%Y-%m-%d")
                    
                    date_columns[date_str] = {
                        'start_col': col_idx,      # початкова колонка (TO)
                        'hours_col': col_idx + 1,  # колонка з годинами
                        'value_col': col_idx + 2,  # колонка з КТУ/статусом
                        'day': int(cell_value)
                    }
                    logger.info(f"📅 Date {date_str}: start_col={col_idx}")
                    day_num += 1
                    col_idx += 3  # переходимо до наступної дати (3 колонки)
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
    Отримати дані за конкретну дату:
    - список працівників
    - TO (технологічна операція)
    - години
    - КТУ або статус
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
        
        # Отримуємо дані попереднього дня (для пропозиції TO та годин)
        prev_date = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
        prev_date_str = prev_date.strftime("%Y-%m-%d")
        prev_cols = date_columns.get(prev_date_str)
        
        workers = []
        # Починаємо з рядка 5 (індекс 4) - дані працівників
        for row_idx, row in enumerate(all_data[4:], start=5):
            if len(row) < 1 or not row[0]:
                continue
            
            fullname = str(row[0]).strip()
            if not fullname or fullname == 'Аутсорс' or fullname.startswith('Бригадир'):
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
                'suggested_hours': suggested_hours
            })
        
        return {"ok": True, "workers": workers, "columns": cols}
    except Exception as e:
        logger.error(f"Error getting shift data: {e}")
        return {"ok": False, "error": str(e)}

def update_shift_data(date_str: str, workers_data: list):
    """
    Оновлює дані в таблиці за конкретну дату
    workers_data: [{'row': 5, 'to': '601', 'hours': '9', 'status': None, 'ktu': 1.1}, ...]
    """
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
        start_col = cols['start_col']      # колонка з TO
        hours_col = cols['hours_col']      # колонка з годинами
        value_col = cols['value_col']      # колонка з КТУ/статусом
        
        updated = 0
        for worker in workers_data:
            row = worker['row']
            
            # Оновлюємо TO (технологічну операцію)
            if worker.get('to'):
                worksheet.update_cell(row, start_col + 1, worker['to'])
                logger.info(f"✅ Updated TO: row {row}, col {start_col + 1} = {worker['to']}")
            
            # Оновлюємо години
            if worker.get('hours'):
                worksheet.update_cell(row, hours_col + 1, worker['hours'])
                logger.info(f"✅ Updated hours: row {row}, col {hours_col + 1} = {worker['hours']}")
            
            # Оновлюємо КТУ або статус
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
        
        # Зберігаємо в історію
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
            ws.append_row(['Дата', 'Час', 'ПІБ', 'ТО', 'Години', 'КТУ/Статус'])
        
        now = datetime.now()
        for worker in workers_data:
            value = worker.get('status') if worker.get('status') else worker.get('ktu')
            ws.append_row([
                date_str,
                now.strftime("%H:%M:%S"),
                worker['fullname'],
                worker.get('to', ''),
                worker.get('hours', ''),
                value if value else ''
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
