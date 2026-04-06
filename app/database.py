import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Шлях до бази даних
DB_PATH = os.path.join(os.path.dirname(__file__), 'workers.db')

def get_db_connection():
    """Отримання з'єднання з БД"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Ініціалізація бази даних (створення таблиць)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Таблиця працівників
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            workshop TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблиця відміток присутності
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            date DATE DEFAULT CURRENT_DATE,
            shift_hours INTEGER DEFAULT 8,
            ktu REAL DEFAULT 1.0,
            status TEXT DEFAULT 'present',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers (id)
        )
    ''')
    
    # Таблиця для збереження поточної зміни
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS current_shift (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_hours INTEGER DEFAULT 8,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Вставляємо зміну за замовчуванням, якщо таблиця порожня
    cursor.execute("SELECT COUNT(*) FROM current_shift")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO current_shift (shift_hours) VALUES (8)")
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized successfully")

# Ініціалізуємо БД при імпорті
init_database()

def add_worker(fullname: str, workshop: str) -> bool:
    """Додати нового працівника"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO workers (fullname, workshop) VALUES (?, ?)",
            (fullname, workshop)
        )
        conn.commit()
        conn.close()
        logger.info(f"✅ Worker added: {fullname} ({workshop})")
        return True
    except Exception as e:
        logger.error(f"❌ Error adding worker: {e}")
        return False

def get_workers_by_workshop(workshop: str) -> List[Dict[str, Any]]:
    """Отримати всіх працівників цеху, які ще не відмічені сьогодні"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT w.id, w.fullname, w.workshop 
            FROM workers w
            WHERE w.workshop = ?
            AND w.id NOT IN (
                SELECT worker_id 
                FROM attendance 
                WHERE date = CURRENT_DATE
            )
            ORDER BY w.fullname
        ''', (workshop,))
        
        workers = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return workers
    except Exception as e:
        logger.error(f"❌ Error getting workers: {e}")
        return []

def get_all_workers_by_shop(workshop: str) -> List[Dict[str, Any]]:
    """Отримати ВСІХ працівників цеху (включно з відміченими)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, fullname, workshop FROM workers WHERE workshop = ? ORDER BY fullname",
            (workshop,)
        )
        workers = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return workers
    except Exception as e:
        logger.error(f"❌ Error getting all workers: {e}")
        return []

def mark_present(worker_id: int, shift_hours: int, ktu: float) -> bool:
    """Відмітити працівника як присутнього"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Перевіряємо, чи не відмічений вже сьогодні
        cursor.execute('''
            SELECT id FROM attendance 
            WHERE worker_id = ? AND date = CURRENT_DATE
        ''', (worker_id,))
        
        if cursor.fetchone():
            conn.close()
            return False
        
        cursor.execute('''
            INSERT INTO attendance (worker_id, shift_hours, ktu, status)
            VALUES (?, ?, ?, 'present')
        ''', (worker_id, shift_hours, ktu))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Worker {worker_id} marked as present with KTU={ktu}")
        return True
    except Exception as e:
        logger.error(f"❌ Error marking present: {e}")
        return False

def mark_other(worker_id: int, status: str) -> bool:
    """Відмітити працівника з іншим статусом"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Перевіряємо, чи не відмічений вже сьогодні
        cursor.execute('''
            SELECT id FROM attendance 
            WHERE worker_id = ? AND date = CURRENT_DATE
        ''', (worker_id,))
        
        if cursor.fetchone():
            conn.close()
            return False
        
        valid_statuses = ['Вщ', 'Пр', 'На', 'Нз']
        if status not in valid_statuses:
            conn.close()
            return False
        
        cursor.execute('''
            INSERT INTO attendance (worker_id, shift_hours, ktu, status)
            VALUES (?, 0, 0, ?)
        ''', (worker_id, status))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Worker {worker_id} marked as {status}")
        return True
    except Exception as e:
        logger.error(f"❌ Error marking other: {e}")
        return False

def get_current_shift() -> int:
    """Отримати поточну зміну (години)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT shift_hours FROM current_shift ORDER BY updated_at DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 8
    except Exception as e:
        logger.error(f"❌ Error getting current shift: {e}")
        return 8

def set_current_shift_db(shift_hours: int) -> bool:
    """Встановити поточну зміну"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO current_shift (shift_hours) VALUES (?)",
            (shift_hours,)
        )
        conn.commit()
        conn.close()
        logger.info(f"✅ Current shift set to {shift_hours} hours")
        return True
    except Exception as e:
        logger.error(f"❌ Error setting current shift: {e}")
        return False

def get_attendance_report() -> List[Dict[str, Any]]:
    """Отримати звіт про відмічання за сьогодні"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                w.fullname,
                w.workshop,
                a.status,
                a.ktu,
                a.shift_hours,
                a.date
            FROM attendance a
            JOIN workers w ON a.worker_id = w.id
            WHERE a.date = CURRENT_DATE
            ORDER BY w.workshop, a.status, w.fullname
        ''')
        
        report = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return report
    except Exception as e:
        logger.error(f"❌ Error getting report: {e}")
        return []

def get_today_statistics() -> Dict[str, Any]:
    """Отримати статистику за сьогодні"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = CURRENT_DATE")
        total_marked = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = CURRENT_DATE AND status = 'present'")
        present_count = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT 
                w.workshop,
                COUNT(*) as total,
                SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present
            FROM attendance a
            JOIN workers w ON a.worker_id = w.id
            WHERE a.date = CURRENT_DATE
            GROUP BY w.workshop
        ''')
        
        workshops_stats = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            'total_marked': total_marked,
            'present_count': present_count,
            'absent_count': total_marked - present_count,
            'workshops': workshops_stats
        }
    except Exception as e:
        logger.error(f"❌ Error getting statistics: {e}")
        return {}

# ==================== GOOGLE SHEETS ФУНКЦІЇ ====================

def sync_workers_from_google():
    """Синхронізація працівників з Google Sheets"""
    try:
        from app.google_sheets import sync_workers_to_local_db
        return sync_workers_to_local_db()
    except Exception as e:
        logger.error(f"❌ Failed to sync from Google: {e}")
        return False

def save_to_google_sheets(worker_id: int, status: str, ktu: float, shift_hours: int) -> bool:
    """Зберігає відмітку в Google Sheets"""
    try:
        from app.google_sheets import save_attendance_to_sheets
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT fullname, workshop FROM workers WHERE id = ?", (worker_id,))
        worker = cursor.fetchone()
        conn.close()
        
        if worker:
            return save_attendance_to_sheets(
                worker['fullname'], 
                worker['workshop'], 
                status, 
                ktu, 
                shift_hours
            )
        return False
    except Exception as e:
        logger.error(f"❌ Failed to save to Google Sheets: {e}")
        return False
