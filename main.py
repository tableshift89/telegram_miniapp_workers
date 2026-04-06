import os
from fastapi import FastAPI, Request
from app.api import api_app
from app.bot import dp, bot
import logging

logging.basicConfig(level=logging.INFO)
app = FastAPI()

# Монтуємо API міні-додатка
app.mount("/", api_app)

WEBHOOK_PATH = f"/webhook/{os.getenv('BOT_TOKEN')}"
WEBHOOK_URL = os.getenv("APP_URL") + WEBHOOK_PATH

@app.on_event("startup")
async def on_startup():
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        logging.info(f"Webhook set to {WEBHOOK_URL}")

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    update_data = await request.json()
    await dp.feed_update(bot, update_data)
    return {"ok": True}

@app.get("/health")
async def health():
    return {"status": "ok"}
