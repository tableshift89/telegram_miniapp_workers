import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api import api_app
from app.database import init_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Створюємо головний FastAPI додаток
app = FastAPI(title="Telegram Worker Bot", description="Worker attendance system")

# Монтуємо API міні-додатка
app.mount("/", api_app)

# Отримуємо токен зі змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# Імпортуємо бота ТІЛЬКИ ПІСЛЯ визначення маршрутів
from app.bot import dp, bot

@app.on_event("startup")
async def on_startup():
    """Ініціалізація при запуску"""
    init_database()
    logger.info("Database initialized")
    
    # Встановлюємо webhook
    webhook_url = os.getenv("APP_URL") + WEBHOOK_PATH
    try:
        await bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

@app.on_event("shutdown")
async def on_shutdown():
    """Очищення при завершенні"""
    try:
        await bot.delete_webhook()
        await bot.close()
        logger.info("Bot session closed")
    except Exception as e:
        logger.error(f"Error closing bot session: {e}")

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Обробник webhook від Telegram"""
    try:
        update_data = await request.json()
        from aiogram.types import Update
        update = Update(**update_data)
        await dp.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(status_code=200, content={"ok": False, "error": str(e)})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "webhook_path": WEBHOOK_PATH,
        "bot_token_configured": bool(BOT_TOKEN)
    }

@app.get("/")
async def root():
    """Кореневий маршрут"""
    return {
        "message": "Telegram Worker Bot is running",
        "docs": "/docs",
        "health": "/health",
        "webhook_path": WEBHOOK_PATH
    }
