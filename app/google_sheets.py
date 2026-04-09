def init_google_sheets():
    global gc, sheet
    try:
        # Правильний scope
        scope = ['https://www.googleapis.com/auth/spreadsheets', 
                 'https://www.googleapis.com/auth/drive']
        
        # Шлях до файлу
        creds_path = 'credentials.json'
        if not os.path.exists(creds_path):
            creds_path = '/opt/render/project/src/credentials.json'
        
        if os.path.exists(creds_path):
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
            logger.info(f"✅ Credentials loaded from {creds_path}")
        else:
            logger.error("❌ credentials.json not found")
            return False
        
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SPREADSHEET_ID)
        logger.info(f"✅ Connected to: {sheet.title}")
        return True
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False
