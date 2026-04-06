from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import logging
import json
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# Глобальна змінна для бота (імпортуємо пізніше)
bot = None
dp = None

@app.on_event("startup")
async def load_bot():
    global bot, dp
    try:
        from app.bot import bot as b, dp as d
        from app.database import init_database
        bot = b
        dp = d
        init_database()
        logger.info("Bot and database initialized")
    except Exception as e:
        logger.error(f"Failed to load bot: {e}")

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    """Обробник вебхуків від Telegram"""
    global bot, dp
    
    if bot is None or dp is None:
        logger.error("Bot not ready")
        return Response("Bot not ready", status_code=500)
    
    try:
        update_data = await request.json()
        logger.info(f"Received update: {update_data.get('update_id')}")
        
        from aiogram.types import Update
        update = Update(**update_data)
        await dp.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(status_code=200, content={"ok": False, "error": str(e)})

@app.get(WEBHOOK_PATH)
async def webhook_get():
    """Перевірка, що ендпоінт існує"""
    return {"message": "Webhook endpoint is active", "bot_ready": bot is not None}

@app.get("/health")
async def health():
    return {"status": "healthy", "webhook_path": WEBHOOK_PATH}

@app.get("/")
async def root():
    return {"message": "Worker Bot is running", "webhook_path": WEBHOOK_PATH}
