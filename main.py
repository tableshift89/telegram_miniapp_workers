import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

bot = None
dp = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot, dp
    logger.info("Starting application...")
    
    try:
        from app.bot import bot as b, dp as d
        from app.database import init_database, sync_workers_from_google
        from app.google_sheets import init_google_sheets
        
        bot = b
        dp = d
        init_database()
        
        # Підключення до Google Sheets та синхронізація
        init_google_sheets()
        sync_workers_from_google()
        
        from aiogram import Bot
        Bot.set_current(bot)
        bot._current = bot
        
        webhook_url = f"{APP_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
        
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
    
    yield
    
    if bot:
        await bot.delete_webhook()
        await bot.close()

app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    global bot, dp
    if bot is None or dp is None:
        return JSONResponse(status_code=500, content={"ok": False})
    
    try:
        update_data = await request.json()
        from aiogram.types import Update
        update = Update(**update_data)
        from aiogram import Bot
        Bot.set_current(bot)
        await dp.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(status_code=200, content={"ok": False})

@app.get("/health")
async def health():
    return {"status": "ok", "bot_ready": bot is not None}

@app.get("/")
async def root():
    return {"message": "Worker Bot is running"}

# API для міні-додатка
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.database import get_workers_by_workshop, add_worker, mark_present, mark_other, get_attendance_report, get_current_shift, save_to_google_sheets
from pydantic import BaseModel

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

class WorkerCreate(BaseModel):
    fullname: str
    workshop: str

class AttendanceMark(BaseModel):
    worker_id: int
    ktu: float
    shift_hours: int

class OtherMark(BaseModel):
    worker_id: int
    status: str

@app.get("/workshop/{workshop}")
async def workshop_page(request: Request, workshop: str):
    if workshop not in ["DMT", "Пакування"]:
        workshop = "DMT"
    return templates.TemplateResponse("index.html", {"request": request, "workshop": workshop})

@app.get("/api/workers/{workshop}")
async def get_workers_api(workshop: str):
    return {"workers": get_workers_by_workshop(workshop)}

@app.post("/api/worker")
async def create_worker_api(worker: WorkerCreate):
    return {"ok": add_worker(worker.fullname, worker.workshop)}

@app.post("/api/mark_present")
async def mark_present_api(mark: AttendanceMark):
    success = mark_present(mark.worker_id, mark.shift_hours, mark.ktu)
    if success:
        save_to_google_sheets(mark.worker_id, 'present', mark.ktu, mark.shift_hours)
    return {"ok": success}

@app.post("/api/mark_other")
async def mark_other_api(mark: OtherMark):
    success = mark_other(mark.worker_id, mark.status)
    if success:
        save_to_google_sheets(mark.worker_id, mark.status, 0, 0)
    return {"ok": success}

@app.get("/api/report")
async def get_report_api():
    return get_attendance_report()

@app.get("/api/current_shift")
async def current_shift_api():
    return {"shift_hours": get_current_shift()}
