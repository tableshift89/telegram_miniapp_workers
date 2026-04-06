import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Отримуємо токен зі змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# Глобальні змінні для бота
bot = None
dp = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управління життєвим циклом додатку"""
    global bot, dp
    
    # Ініціалізація при запуску
    logger.info("Starting application...")
    
    # Імпортуємо тут, щоб уникнути циркулярних імпортів
    from app.bot import bot as bot_instance, dp as dp_instance
    from app.database import init_database
    
    bot = bot_instance
    dp = dp_instance
    
    # Ініціалізуємо базу даних
    init_database()
    logger.info("Database initialized")
    
    # Встановлюємо webhook
    webhook_url = f"{APP_URL}{WEBHOOK_PATH}"
    try:
        await bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
    
    yield
    
    # Очищення при завершенні
    logger.info("Shutting down...")
    try:
        await bot.delete_webhook()
        await bot.close()
        logger.info("Bot session closed")
    except Exception as e:
        logger.error(f"Error closing bot session: {e}")

# Створюємо FastAPI додаток з lifespan
app = FastAPI(title="Telegram Worker Bot", description="Worker attendance system", lifespan=lifespan)

# Імпортуємо та монтуємо API міні-додатка
from app.api import api_app
app.mount("/", api_app)

# Маршрут для webhook (ПОВИНЕН БУТИ ДО МОНТУВАННЯ api_app)
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Обробник webhook від Telegram"""
    global bot, dp
    
    if bot is None or dp is None:
        logger.error("Bot or Dispatcher not initialized")
        return JSONResponse(status_code=500, content={"ok": False, "error": "Bot not initialized"})
    
    try:
        update_data = await request.json()
        logger.info(f"Received update: {update_data}")
        
        from aiogram.types import Update
        update = Update(**update_data)
        await dp.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(status_code=200, content={"ok": False, "error": str(e)})

# Додатковий GET маршрут для перевірки webhook
@app.get(WEBHOOK_PATH)
async def webhook_get():
    """GET запит на webhook (для перевірки)"""
    return {"message": "Webhook endpoint is active. Use POST method for Telegram updates."}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "webhook_path": WEBHOOK_PATH,
        "webhook_url": f"{APP_URL}{WEBHOOK_PATH}",
        "bot_token_configured": bool(BOT_TOKEN),
        "app_url_configured": bool(APP_URL)
    }

@app.get("/")
async def root():
    """Кореневий маршрут"""
    return {
        "message": "Telegram Worker Bot is running",
        "health": "/health",
        "webhook_path": WEBHOOK_PATH,
        "documentation": "Use Telegram bot to access the mini-app"
    }
