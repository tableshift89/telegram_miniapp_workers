import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'workers.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            workshop TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS current_shift (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_hours INTEGER DEFAULT 8,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM current_shift")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO current_shift (shift_hours) VALUES (8)")
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

init_database()

def add_worker(fullname: str, workshop: str) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO workers (fullname, workshop) VALUES (?, ?)",
            (fullname, workshop)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error adding worker: {e}")
        return False

def get_workers_by_workshop(workshop: str) -> List[Dict[str, Any]]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT w.id, w.fullname, w.workshop 
            FROM workers w
            WHERE w.workshop = ?
            AND w.id NOT IN (
                SELECT worker_id FROM attendance WHERE date = CURRENT_DATE
            )
            ORDER BY w.fullname
        ''', (workshop,))
        workers = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return workers
    except Exception as e:
        logger.error(f"Error getting workers: {e}")
        return []

def get_all_workers_by_workshop(workshop: str) -> List[Dict[str, Any]]:
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
        logger.error(f"Error getting all workers: {e}")
        return []

def mark_present(worker_id: int, shift_hours: int, ktu: float) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
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
        return True
    except Exception as e:
        logger.error(f"Error marking present: {e}")
        return False

def mark_other(worker_id: int, status: str) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
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
        return True
    except Exception as e:
        logger.error(f"Error marking other: {e}")
        return False

def get_current_shift() -> int:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT shift_hours FROM current_shift ORDER BY updated_at DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 8
    except Exception as e:
        logger.error(f"Error getting current shift: {e}")
        return 8

def set_current_shift_db(shift_hours: int) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO current_shift (shift_hours) VALUES (?)", (shift_hours,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error setting current shift: {e}")
        return False

def get_attendance_report() -> List[Dict[str, Any]]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT w.fullname, w.workshop, a.status, a.ktu, a.shift_hours, a.date
            FROM attendance a
            JOIN workers w ON a.worker_id = w.id
            WHERE a.date = CURRENT_DATE
            ORDER BY w.workshop, w.fullname
        ''')
        report = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return report
    except Exception as e:
        logger.error(f"Error getting report: {e}")
        return []

def sync_workers_from_google():
    from app.google_sheets import sync_workers_to_local_db
    return sync_workers_to_local_db()

def save_to_google_sheets(worker_id: int, status: str, ktu: float, shift_hours: int) -> bool:
    from app.google_sheets import save_attendance_to_sheets
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT fullname, workshop FROM workers WHERE id = ?", (worker_id,))
    worker = cursor.fetchone()
    conn.close()
    
    if worker:
        return save_attendance_to_sheets(worker['fullname'], worker['workshop'], status, ktu, shift_hours)
    return False
