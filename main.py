import os
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Імпортуємо наш обробник вебхуків
from webhook_handler import app as webhook_app

# Імпортуємо API міні-додатка
from app.api import api_app

# Створюємо головний додаток
app = FastAPI()

# Монтуємо вебхук обробник
app.mount("/", webhook_app)

# Монтуємо API міні-додатка (якщо потрібно)
app.mount("/app", api_app)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {
        "message": "Telegram Worker Bot is running",
        "webhook_path": f"/webhook/{os.getenv('BOT_TOKEN', '')}",
        "health": "/health"
    }
