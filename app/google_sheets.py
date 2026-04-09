def init_google_sheets():
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
        
        # Якщо не знайшли файл, пробуємо змінну середовища
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
