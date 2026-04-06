def sync_workers_from_google():
    """Синхронізація працівників з Google Sheets"""
    from app.google_sheets import sync_workers_to_local_db
    return sync_workers_to_local_db()

def save_to_google_sheets(worker_id: int, status: str, ktu: float, shift_hours: int) -> bool:
    """Зберігає відмітку в Google Sheets"""
    from app.google_sheets import save_attendance_to_sheets
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT w.fullname, w.workshop 
        FROM workers w 
        WHERE w.id = ?
    """, (worker_id,))
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
