import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
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
    
    logger.info("🚀 Starting application...")
    
    # Ініціалізація бота та бази даних
    try:
        from app.bot import bot as b, dp as d
        from app.database import init_database, sync_workers_from_google
        from app.google_sheets import init_google_sheets
        
        bot = b
        dp = d
        init_database()
        
        # Підключення до Google Sheets та синхронізація
        logger.info("📊 Connecting to Google Sheets...")
        init_google_sheets()
        sync_workers_from_google()
        
        # Встановлюємо контекст для aiogram 2.x
        from aiogram import Bot
        Bot.set_current(bot)
        bot._current = bot
        
        # Встановлюємо webhook
        webhook_url = f"{APP_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url)
        logger.info(f"🔗 Webhook set to {webhook_url}")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
    
    yield
    
    # Очищення при завершенні
    logger.info("🛑 Shutting down...")
    if bot:
        try:
            await bot.delete_webhook()
            await bot.close()
            logger.info("✅ Bot session closed")
        except Exception as e:
            logger.error(f"Error closing bot: {e}")

# Створюємо FastAPI додаток
app = FastAPI(
    title="Telegram Worker Bot",
    description="Worker attendance management system with Google Sheets integration",
    lifespan=lifespan
)

# Монтуємо статичні файли
app.mount("/static", StaticFiles(directory="app/static"), name="static")

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
        return JSONResponse(status_code=200, content={"ok": False, "error": str(e)})

@app.get(WEBHOOK_PATH)
async def webhook_get():
    """GET запит на webhook (для перевірки)"""
    return {
        "message": "Webhook endpoint is active",
        "bot_ready": bot is not None,
        "webhook_path": WEBHOOK_PATH
    }

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
    from app.database import get_all_workers_by_shop
    workers = get_all_workers_by_shop(workshop)
    return {"workers": workers}

@app.post("/api/worker")
async def create_worker(worker: WorkerCreate):
    """Додати нового працівника"""
    from app.database import add_worker
    success = add_worker(worker.fullname, worker.workshop)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add worker")
    return {"ok": True}

@app.post("/api/mark_present")
async def mark_present_route(mark: AttendanceMark):
    """Відмітити присутність працівника"""
    from app.database import mark_present, save_to_google_sheets
    success = mark_present(mark.worker_id, mark.shift_hours, mark.ktu)
    if success:
        save_to_google_sheets(mark.worker_id, 'present', mark.ktu, mark.shift_hours)
    return {"ok": success}

@app.post("/api/mark_other")
async def mark_other_route(mark: OtherMark):
    """Відмітити працівника з іншим статусом"""
    from app.database import mark_other, save_to_google_sheets
    success = mark_other(mark.worker_id, mark.status)
    if success:
        save_to_google_sheets(mark.worker_id, mark.status, 0, 0)
    return {"ok": success}

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

# ==================== ДІАГНОСТИЧНІ МАРШРУТИ ====================

@app.get("/debug/google-sheets")
async def debug_google_sheets():
    """Діагностика підключення до Google Sheets"""
    from app.google_sheets import init_google_sheets, load_workers_from_sheets
    
    result = {
        "status": "checking",
        "connection": False,
        "worksheets": [],
        "workers": [],
        "workers_count": 0,
        "errors": []
    }
    
    try:
        # Перевіряємо підключення
        conn_success = init_google_sheets()
        result["connection"] = conn_success
        
        if conn_success:
            # Отримуємо список аркушів
            from app.google_sheets import sheet
            if sheet:
                worksheets = sheet.worksheets()
                result["worksheets"] = [ws.title for ws in worksheets]
            
            # Спроба завантажити працівників
            workers = load_workers_from_sheets()
            result["workers"] = workers[:5]  # Показуємо перших 5
            result["workers_count"] = len(workers)
        
        result["status"] = "ok"
    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e))
    
    return result

@app.get("/debug/db-workers")
async def debug_db_workers():
    """Діагностика працівників в БД"""
    from app.database import get_all_workers_by_shop
    
    result = {
        "DMT": get_all_workers_by_shop("DMT"),
        "Пакування": get_all_workers_by_shop("Пакування")
    }
    return result

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
        "version": "2.0.0",
        "features": [
            "Google Sheets integration",
            "Worker attendance tracking",
            "KTU selection (0.9, 1.0, 1.1, 1.2, 1.3)",
            "Absence reasons (Вщ, Пр, На, Нз)"
        ],
        "endpoints": {
            "health": "/health",
            "webhook": WEBHOOK_PATH,
            "workshop": "/workshop/{DMT|Пакування}",
            "api": "/api/workers/{workshop}",
            "debug_google": "/debug/google-sheets",
            "debug_db": "/debug/db-workers"
        },
        "bot_status": "ready" if bot is not None else "initializing"
    }

# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
