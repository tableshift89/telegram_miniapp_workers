from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import logging
import os
import sys

# Додаємо теку `app` до шляху імпорту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# Глобальна змінна для бота
bot = None
dp = None

# Ініціалізуємо бота ПРИ СТАРТІ
try:
    from app.bot import bot as b, dp as d
    from app.database import init_database
    
    bot = b
    dp = d
    init_database()
    logger.info("✅ Bot and database initialized successfully")
    
    # Встановлюємо вебхук автоматично
    import asyncio
    webhook_url = f"{APP_URL}{WEBHOOK_PATH}"
    try:
        asyncio.create_task(bot.set_webhook(webhook_url))
        logger.info(f"🔗 Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        
except Exception as e:
    logger.error(f"❌ CRITICAL: Failed to initialize bot: {e}")

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    """Обробник вебхуків від Telegram"""
    global bot, dp
    
    if bot is None or dp is None:
        logger.error("Bot not ready - initialization failed")
        return Response("Bot not ready", status_code=500)
    
    try:
        update_data = await request.json()
        logger.info(f"📨 Received update: {update_data.get('update_id')}")
        
        # Сумісний спосіб обробки для aiogram 2.x
        from aiogram.types import Update
        update = Update(**update_data)
        await dp.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return JSONResponse(status_code=200, content={"ok": False, "error": str(e)})

@app.get(WEBHOOK_PATH)
async def webhook_get():
    """Перевірка статусу ендпоінту"""
    return {
        "message": "Webhook endpoint is active",
        "bot_ready": bot is not None,
        "bot_token_configured": bool(BOT_TOKEN),
        "app_url_configured": bool(APP_URL)
    }

@app.get("/health")
async def health():
    """Перевірка здоров'я сервісу"""
    return {
        "status": "healthy" if bot is not None else "degraded",
        "bot_ready": bot is not None,
        "webhook_path": WEBHOOK_PATH
    }

@app.get("/")
async def root():
    return {
        "message": "Telegram Worker Bot is running",
        "webhook_path": WEBHOOK_PATH,
        "health": "/health",
        "bot_status": "ready" if bot is not None else "initializing"
    }
