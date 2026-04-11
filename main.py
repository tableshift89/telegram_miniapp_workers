def add_worker_to_sheet(fullname: str, workshop: str, is_outsourcer: bool = False):
    """Додати нового працівника в кінець списку (ГОЛОВНА)"""
    global sheet
    if sheet is None:
        if not init_google_sheets():
            return False
    
    try:
        worksheet = sheet.worksheet(MAIN_SHEET)
        all_data = worksheet.get_all_values()
        
        # Знаходимо останній рядок з даними
        last_row = len(all_data) + 1
        
        # Додаємо працівника
        if is_outsourcer:
            # Знаходимо рядок "Аутсорс"
            outsourcer_row = None
            for i, row in enumerate(all_data, start=1):
                if len(row) > 1 and row[1] == 'Аутсорс':
                    outsourcer_row = i
                    break
            
            if outsourcer_row:
                # Вставляємо новий рядок після "Аутсорс"
                worksheet.insert_row(['', fullname], outsourcer_row + 1)
                logger.info(f"✅ Added outsourcer: {fullname} after row {outsourcer_row}")
            else:
                # Якщо немає рядка "Аутсорс", додаємо в кінець
                worksheet.append_row(['', fullname])
                logger.info(f"✅ Added worker: {fullname} at end")
        else:
            # Додаємо офіційного працівника перед "Аутсорс" або в кінець
            outsourcer_row = None
            for i, row in enumerate(all_data, start=1):
                if len(row) > 1 and row[1] == 'Аутсорс':
                    outsourcer_row = i
                    break
            
            if outsourcer_row:
                worksheet.insert_row(['', fullname], outsourcer_row)
                logger.info(f"✅ Added official worker: {fullname} before outsourcer section")
            else:
                worksheet.append_row(['', fullname])
                logger.info(f"✅ Added worker: {fullname} at end")
        
        return True
    except Exception as e:
        logger.error(f"Error adding worker: {e}")
        return False
