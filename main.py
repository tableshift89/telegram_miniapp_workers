import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List, Optional

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Отримуємо змінні середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# Глобальні змінні для бота
bot = None
dp = None

# Моделі даних для API
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

# Налаштування шаблонів та статики
templates = Jinja2Templates(directory="app/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управління життєвим циклом додатку"""
    global bot, dp
    
    logger.info("Starting application...")
    
    # Ініціалізація бота та бази даних
    try:
        from app.bot import bot as b, dp as d
        from app.database import init_database
        
        bot = b
        dp = d
        init_database()
        
        # Встановлюємо контекст для aiogram 2.x
        from aiogram import Bot
        Bot.set_current(bot)
        bot._current = bot
        
        logger.info("✅ Bot and database initialized successfully")
        
        # Встановлюємо webhook
        webhook_url = f"{APP_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url)
        logger.info(f"🔗 Webhook set to {webhook_url}")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize bot: {e}")
        import traceback
        traceback.print_exc()
    
    yield
    
    # Очищення при завершенні
    logger.info("Shutting down...")
    if bot:
        try:
            await bot.delete_webhook()
            await bot.close()
            logger.info("Bot session closed")
        except Exception as e:
            logger.error(f"Error closing bot: {e}")

# Створюємо FastAPI додаток
app = FastAPI(
    title="Telegram Worker Bot",
    description="Worker attendance management system",
    lifespan=lifespan
)

# Монтуємо статичні файли
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ==================== МАРШРУТИ ДЛЯ МІНІ-ЗАСТОСУНКУ ====================

@app.get("/workshop/{workshop}", response_class=HTMLResponse)
async def workshop_page(request: Request, workshop: str):
    """Головна сторінка міні-додатка для цеху"""
    if workshop not in ["DMT", "Пакування"]:
        workshop = "DMT"
    
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "workshop": workshop}
    )

@app.get("/api/workers/{workshop}")
async def get_workers(workshop: str):
    """Отримати список працівників цеху (не відмічених сьогодні)"""
    from app.database import get_workers_by_workshop
    workers = get_workers_by_workshop(workshop)
    return {"workers": workers}

@app.get("/api/all_workers/{workshop}")
async def get_all_workers(workshop: str):
    """Отримати ВСІХ працівників цеху"""
    from app.database import get_all_workers_by_workshop
    workers = get_all_workers_by_workshop(workshop)
    return {"workers": workers}

@app.post("/api/worker")
async def create_worker(worker: WorkerCreate):
    """Додати нового працівника"""
    from app.database import add_worker
    success = add_worker(worker.fullname, worker.workshop)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add worker")
    return {"ok": True, "message": f"Worker {worker.fullname} added"}

@app.post("/api/mark_present")
async def mark_present_route(mark: AttendanceMark):
    """Відмітити присутність працівника"""
    from app.database import mark_present
    success = mark_present(mark.worker_id, mark.shift_hours, mark.ktu)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to mark present")
    return {"ok": True, "message": "Worker marked as present"}

@app.post("/api/mark_other")
async def mark_other_route(mark: OtherMark):
    """Відмітити працівника з іншим статусом"""
    from app.database import mark_other
    success = mark_other(mark.worker_id, mark.status)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to mark other status")
    return {"ok": True, "message": f"Worker marked as {mark.status}"}

@app.get("/api/report")
async def get_report():
    """Отримати звіт за сьогодні"""
    from app.database import get_attendance_report
    report = get_attendance_report()
    return report

@app.get("/api/current_shift")
async def current_shift():
    """Отримати поточну зміну"""
    from app.database import get_current_shift
    shift = get_current_shift()
    return {"shift_hours": shift}

@app.get("/api/stats")
async def get_stats():
    """Отримати статистику за сьогодні"""
    from app.database import get_today_statistics
    stats = get_today_statistics()
    return stats

# ==================== WEBHOOK ДЛЯ TELEGRAM ====================

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Обробник webhook від Telegram"""
    global bot, dp
    
    if bot is None or dp is None:
        logger.error("Bot not ready")
        return JSONResponse(status_code=500, content={"ok": False, "error": "Bot not ready"})
    
    try:
        update_data = await request.json()
        logger.info(f"📨 Received update: {update_data.get('update_id')}")
        
        from aiogram.types import Update
        update = Update(**update_data)
        
        # Встановлюємо контекст перед обробкою
        from aiogram import Bot
        Bot.set_current(bot)
        bot._current = bot
        
        await dp.process_update(update)
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=200, content={"ok": False, "error": str(e)})

@app.get(WEBHOOK_PATH)
async def webhook_get():
    """GET запит на webhook (для перевірки)"""
    return {
        "message": "Webhook endpoint is active",
        "bot_ready": bot is not None,
        "webhook_path": WEBHOOK_PATH
    }

# ==================== СЛУЖБОВІ МАРШРУТИ ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if bot is not None else "degraded",
        "bot_ready": bot is not None,
        "webhook_path": WEBHOOK_PATH,
        "bot_token_configured": bool(BOT_TOKEN),
        "app_url_configured": bool(APP_URL)
    }

@app.get("/")
async def root():
    """Кореневий маршрут"""
    return {
        "message": "Telegram Worker Bot is running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "webhook": WEBHOOK_PATH,
            "workshop": "/workshop/{DMT|Пакування}",
            "api": "/api/workers/{workshop}"
        },
        "bot_status": "ready" if bot is not None else "initializing"
    }

# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
