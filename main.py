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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

bot = None
dp = None

# Моделі даних
class WorkerCreate(BaseModel):
    fullname: str
    workshop: str

class AttendanceMark(BaseModel):
    worker_id: int
    ktu: float
    shift_hours: int
    date: Optional[str] = None

class OtherMark(BaseModel):
    worker_id: int
    status: str
    date: Optional[str] = None

class OrderRequest(BaseModel):
    product: str
    product_name: str
    weight: float
    recipe: dict

class GoogleAttendanceMark(BaseModel):
    worker_name: str
    operation_code: str
    status: str
    ktu: float
    hours: int
    date: str
    row: int

templates = Jinja2Templates(directory="app/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot, dp
    logger.info("🚀 Starting application...")
    
    try:
        from app.bot import bot as b, dp as d
        from app.database import init_database
        from app.google_sheets import init_google_sheets, sync_workers_to_local_db
        
        bot = b
        dp = d
        init_database()
        
        logger.info("📊 Connecting to Google Sheets...")
        if init_google_sheets():
            logger.info("✅ Google Sheets connected successfully")
            sync_workers_to_local_db()
        else:
            logger.warning("⚠️ Google Sheets connection failed, continuing with local DB")
        
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

# Створення додатку
app = FastAPI(title="Telegram Worker Bot", lifespan=lifespan)

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

# ==================== API ДЛЯ МІНІ-ДОДАТКУ (WEB APP) ====================

@app.get("/workshop/{workshop}", response_class=HTMLResponse)
async def workshop_page(request: Request, workshop: str):
    if workshop not in ["DMT", "Пакування"]:
        workshop = "DMT"
    return templates.TemplateResponse("index.html", {"request": request, "workshop": workshop})

@app.get("/recipe", response_class=HTMLResponse)
async def recipe_page(request: Request):
    return templates.TemplateResponse("recipe.html", {"request": request})

# ==================== API ДЛЯ РОБОТИ З ТАБЕЛЕМ (GOOGLE SHEETS) ====================

@app.get("/api/shift-data")
async def get_shift_data(date: str):
    """Отримати дані за конкретну дату (працівники, ТО, години, КТУ/статус)"""
    from app.google_sheets import get_shift_data
    result = get_shift_data(date)
    return result

@app.post("/api/sync-shift")
async def sync_shift(request: Request):
    """Синхронізувати дані з таблицею Google Sheets"""
    from app.google_sheets import update_shift_data
    data = await request.json()
    result = update_shift_data(data.get('date'), data.get('workers'))
    return result

@app.get("/api/check-connection")
async def check_connection():
    """Перевірити підключення до Google Sheets"""
    from app.google_sheets import check_connection
    return {"connected": check_connection()}

@app.get("/api/operations")
async def get_operations():
    """Отримати список технологічних операцій"""
    return {"operations": ['601', '602', '603', '475', '1088', '1256']}

@app.post("/api/add-worker")
async def add_worker_endpoint(request: Request):
    """Додати нового працівника в Google Sheets"""
    from app.google_sheets import add_worker_to_sheet
    data = await request.json()
    fullname = data.get('fullname')
    workshop = data.get('workshop')
    is_outsourcer = data.get('isOutsourcer', False)
    
    if not fullname:
        return {"ok": False, "error": "Name is required"}
    
    success = add_worker_to_sheet(fullname, workshop, is_outsourcer)
    return {"ok": success}

# ==================== API ДЛЯ ЛОКАЛЬНОЇ БД (резерв) ====================

@app.get("/api/workers/{workshop}")
async def get_workers(workshop: str, date: str = None):
    from app.database import get_workers_by_workshop, get_workers_by_workshop_date
    if date:
        workers = get_workers_by_workshop_date(workshop, date)
    else:
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
    from app.database import mark_present, mark_present_date, save_to_google_sheets
    
    if mark.date:
        success = mark_present_date(mark.worker_id, mark.shift_hours, mark.ktu, mark.date)
    else:
        success = mark_present(mark.worker_id, mark.shift_hours, mark.ktu)
    
    if success:
        save_to_google_sheets(mark.worker_id, 'present', mark.ktu, mark.shift_hours)
    return {"ok": success}

@app.post("/api/mark_other")
async def mark_other_route(mark: OtherMark):
    from app.database import mark_other, mark_other_date, save_to_google_sheets
    
    if mark.date:
        success = mark_other_date(mark.worker_id, mark.status, mark.date)
    else:
        success = mark_other(mark.worker_id, mark.status)
    
    if success:
        save_to_google_sheets(mark.worker_id, mark.status, 0, 0)
    return {"ok": success}

@app.get("/api/report")
async def get_report(date: str = None):
    from app.database import get_attendance_report, get_attendance_report_date
    
    if date:
        report = get_attendance_report_date(date)
    else:
        report = get_attendance_report()
    return report

@app.get("/api/current_shift")
async def current_shift():
    from app.database import get_current_shift
    return {"shift_hours": get_current_shift()}

# ==================== API ДЛЯ РЕЦЕПТІВ ====================

@app.post("/api/order")
async def create_order(order: OrderRequest):
    order_data = {
        "timestamp": datetime.now().isoformat(),
        "product": order.product,
        "product_name": order.product_name,
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
    orders_file = "orders.json"
    if os.path.exists(orders_file):
        with open(orders_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# ==================== ДІАГНОСТИКА ====================

@app.get("/debug/google")
async def debug_google():
    from app.google_sheets import init_google_sheets, get_date_columns, get_shift_data
    
    result = {
        "connection": False,
        "date_columns": {},
        "workers_today": 0,
        "errors": []
    }
    
    try:
        conn = init_google_sheets()
        result["connection"] = conn
        
        if conn:
            date_columns = get_date_columns()
            result["date_columns"] = {k: v for k, v in date_columns.items()}
            
            today = datetime.now().strftime("%Y-%m-%d")
            shift_data = get_shift_data(today)
            if shift_data.get('ok'):
                result["workers_today"] = len(shift_data.get('workers', []))
    except Exception as e:
        result["errors"].append(str(e))
    
    return result

@app.get("/debug/db")
async def debug_db():
    from app.database import get_all_workers_by_shop
    return {
        "DMT": get_all_workers_by_shop("DMT"),
        "Пакування": get_all_workers_by_shop("Пакування")
    }

@app.post("/api/sync-now")
async def sync_now():
    from app.google_sheets import sync_workers_to_local_db
    success = sync_workers_to_local_db()
    return {"ok": success, "message": "Sync completed" if success else "Sync failed"}

# ==================== СЛУЖБОВІ МАРШРУТИ ====================

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
            "shift_data": "/api/shift-data?date=YYYY-MM-DD",
            "sync_shift": "/api/sync-shift (POST)",
            "add_worker": "/api/add-worker (POST)",
            "operations": "/api/operations",
            "check_connection": "/api/check-connection",
            "debug_google": "/debug/google",
            "debug_db": "/debug/db",
            "sync_now": "/api/sync-now"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
