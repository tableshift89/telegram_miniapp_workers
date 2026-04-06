import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json

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

class OrderRequest(BaseModel):
    product: str
    weight: float
    recipe: dict

# Налаштування шаблонів та статики
templates = Jinja2Templates(directory="app/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управління життєвим циклом додатку"""
    global bot, dp
    
    logger.info("🚀 Starting application...")
    
    try:
        from app.bot import bot as b, dp as d
        from app.database import init_database, sync_workers_from_google
        from app.google_sheets import init_google_sheets
        
        bot = b
        dp = d
        init_database()
        
        # Підключення до Google Sheets
        logger.info("📊 Connecting to Google Sheets...")
        init_google_sheets()
        sync_workers_from_google()
        
        from aiogram import Bot
        Bot.set_current(bot)
        bot._current = bot
        
        webhook_url = f"{APP_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url)
        logger.info(f"🔗 Webhook set to {webhook_url}")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
    
    yield
    
    logger.info("🛑 Shutting down...")
    if bot:
        try:
            await bot.delete_webhook()
            await bot.close()
            logger.info("✅ Bot session closed")
        except Exception as e:
            logger.error(f"Error closing bot: {e}")

app = FastAPI(
    title="Telegram Worker Bot",
    description="Worker attendance + Recipe calculator with Google Sheets",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ==================== WEBHOOK ====================

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    global bot, dp
    if bot is None or dp is None:
        return JSONResponse(status_code=500, content={"ok": False})
    
    try:
        update_data = await request.json()
        logger.info(f"📨 Received update: {update_data.get('update_id')}")
        
        from aiogram.types import Update
        update = Update(**update_data)
        from aiogram import Bot
        Bot.set_current(bot)
        await dp.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(status_code=200, content={"ok": False})

@app.get(WEBHOOK_PATH)
async def webhook_get():
    return {"message": "Webhook is active", "bot_ready": bot is not None}

# ==================== API ДЛЯ МІНІ-ДОДАТКУ (ПРАЦІВНИКИ) ====================

@app.get("/workshop/{workshop}", response_class=HTMLResponse)
async def workshop_page(request: Request, workshop: str):
    if workshop not in ["DMT", "Пакування"]:
        workshop = "DMT"
    return templates.TemplateResponse("index.html", {"request": request, "workshop": workshop})

@app.get("/api/workers/{workshop}")
async def get_workers(workshop: str):
    from app.database import get_workers_by_workshop
    workers = get_workers_by_workshop(workshop)
    return {"workers": workers}

@app.get("/api/all_workers/{workshop}")
async def get_all_workers(workshop: str):
    from app.database import get_all_workers_by_shop
    workers = get_all_workers_by_shop(workshop)
    return {"workers": workers}

@app.post("/api/worker")
async def create_worker(worker: WorkerCreate):
    from app.database import add_worker
    success = add_worker(worker.fullname, worker.workshop)
    return {"ok": success}

@app.post("/api/mark_present")
async def mark_present_route(mark: AttendanceMark):
    from app.database import mark_present, save_to_google_sheets
    success = mark_present(mark.worker_id, mark.shift_hours, mark.ktu)
    if success:
        save_to_google_sheets(mark.worker_id, 'present', mark.ktu, mark.shift_hours)
    return {"ok": success}

@app.post("/api/mark_other")
async def mark_other_route(mark: OtherMark):
    from app.database import mark_other, save_to_google_sheets
    success = mark_other(mark.worker_id, mark.status)
    if success:
        save_to_google_sheets(mark.worker_id, mark.status, 0, 0)
    return {"ok": success}

@app.get("/api/report")
async def get_report():
    from app.database import get_attendance_report
    return get_attendance_report()

@app.get("/api/current_shift")
async def current_shift():
    from app.database import get_current_shift
    return {"shift_hours": get_current_shift()}

# ==================== API ДЛЯ РЕЦЕПТУРИ ====================

@app.get("/recipe", response_class=HTMLResponse)
async def recipe_page(request: Request):
    """Сторінка калькулятора рецептури"""
    return templates.TemplateResponse("recipe.html", {"request": request})

@app.post("/api/order")
async def create_order(order: OrderRequest):
    """Обробка замовлення з рецептури"""
    order_data = {
        "timestamp": datetime.now().isoformat(),
        "product": order.product,
        "weight": order.weight,
        "recipe": order.recipe
    }
    
    orders_file = "orders.json"
    try:
        if os.path.exists(orders_file):
            with open(orders_file, 'r', encoding='utf-8') as f:
                orders = json.load(f)
        else:
            orders = []
        
        orders.append(order_data)
        
        with open(orders_file, 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Order saved: {order.product} - {order.weight}kg")
        return {"ok": True, "message": "Order saved"}
    except Exception as e:
        logger.error(f"Failed to save order: {e}")
        return {"ok": False, "message": str(e)}

@app.get("/api/orders")
async def get_orders():
    """Отримати всі замовлення"""
    orders_file = "orders.json"
    if os.path.exists(orders_file):
        with open(orders_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# ==================== ДІАГНОСТИКА ====================

@app.get("/debug/google")
async def debug_google():
    """Діагностика Google Sheets"""
    from app.google_sheets import init_google_sheets, load_workers_from_sheets
    
    result = {
        "connection": False,
        "worksheets": [],
        "workers": [],
        "workers_count": 0,
        "errors": []
    }
    
    try:
        conn = init_google_sheets()
        result["connection"] = conn
        
        if conn:
            from app.google_sheets import sheet
            if sheet:
                worksheets = sheet.worksheets()
                result["worksheets"] = [ws.title for ws in worksheets]
            
            workers = load_workers_from_sheets()
            result["workers_count"] = len(workers)
            result["workers"] = workers[:10]
    except Exception as e:
        result["errors"].append(str(e))
    
    return result

@app.get("/debug/db")
async def debug_db():
    """Діагностика БД"""
    from app.database import get_all_workers_by_shop
    return {
        "DMT": get_all_workers_by_shop("DMT"),
        "Пакування": get_all_workers_by_shop("Пакування")
    }

@app.post("/api/sync-now")
async def sync_now():
    """Примусова синхронізація з Google Sheets"""
    from app.google_sheets import sync_workers_to_local_db
    success = sync_workers_to_local_db()
    return {"ok": success, "message": "Sync completed" if success else "Sync failed"}

# ==================== СЛУЖБОВІ ====================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy" if bot is not None else "degraded",
        "bot_ready": bot is not None,
        "webhook_path": WEBHOOK_PATH
    }

@app.get("/")
async def root():
    return {
        "message": "Telegram Worker Bot is running",
        "version": "2.0.0",
        "endpoints": {
            "health": "/health",
            "workshop": "/workshop/{DMT|Пакування}",
            "recipe": "/recipe",
            "debug_google": "/debug/google",
            "debug_db": "/debug/db"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
