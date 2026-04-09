def init_google_sheets():
    """Ініціалізація підключення до Google Sheets"""
    global gc, sheet
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        creds = None
        
        # Спосіб 1: файл credentials.json
        creds_path = 'credentials.json'
        if not os.path.exists(creds_path):
            creds_path = '/opt/render/project/src/credentials.json'
        
        if os.path.exists(creds_path):
            try:
                creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
                logger.info(f"✅ Credentials loaded from {creds_path}")
                
                # Отримуємо email з creds для перевірки
                from oauth2client.client import SignedJwtAssertionCredentials
                if hasattr(creds, 'service_account_email'):
                    logger.info(f"📧 Service account email: {creds.service_account_email}")
            except Exception as e:
                logger.error(f"Failed to load credentials from file: {e}")
        
        # Спосіб 2: змінна середовища
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
        logger.info("✅ Authorization successful, opening spreadsheet...")
        
        sheet = gc.open_by_key(SPREADSHEET_ID)
        logger.info(f"✅ Connected to: {sheet.title}")
        return True
    except gspread.exceptions.SpreadsheetNotFound:
        logger.error(f"❌ Spreadsheet not found. Check SPREADSHEET_ID: {SPREADSHEET_ID}")
        return False
    except gspread.exceptions.APIError as e:
        logger.error(f"❌ Google Sheets API error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        import traceback
        traceback.print_exc()
        return False
