import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api import api_app
from app.bot import dp, bot
from app.database import init_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Створюємо головний FastAPI додаток
app = FastAPI(title="Telegram Worker Bot", description="Worker attendance system")

# Монтуємо API міні-додатка
app.mount("/", api_app)

WEBHOOK_PATH = f"/webhook/{os.getenv('BOT_TOKEN', 'test_token')}"
WEBHOOK_URL = os.getenv("APP_URL", "http://localhost:8000") + WEBHOOK_PATH

@app.on_event("startup")
async def on_startup():
    """Ініціалізація при запуску"""
    # Ініціалізуємо базу даних
    init_database()
    logger.info("Database initialized")
    
    # Встановлюємо webhook для Telegram бота
    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url != WEBHOOK_URL:
            await bot.set_webhook(WEBHOOK_URL)
            logger.info(f"Webhook set to {WEBHOOK_URL}")
        else:
            logger.info("Webhook already configured")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

@app.on_event("shutdown")
async def on_shutdown():
    """Очищення при завершенні"""
    try:
        await bot.session.close()
        logger.info("Bot session closed")
    except Exception as e:
        logger.error(f"Error closing bot session: {e}")

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Обробник webhook від Telegram"""
    try:
        update_data = await request.json()
        await dp.feed_update(bot, update_data)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(status_code=200, content={"ok": False, "error": str(e)})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "webhook_url": WEBHOOK_URL,
        "bot_token_configured": bool(os.getenv("BOT_TOKEN"))
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
