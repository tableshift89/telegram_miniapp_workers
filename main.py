import asyncio
import uvicorn
from aiogram.types import WebhookInfo
from app.bot import dp, bot
from app.api import api_app
from fastapi import FastAPI
import os

app = FastAPI()
app.mount("/", api_app)

WEBHOOK_PATH = f"/webhook/{os.getenv('BOT_TOKEN')}"
WEBHOOK_URL = os.getenv("APP_URL") + WEBHOOK_PATH

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(uvicorn.run(api_app, host="0.0.0.0", port=int(os.getenv("PORT", 8000))))

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    update = await request.json()
    await dp.process_update(update)
    return {"ok": True}
