import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from .database import (
    get_workers_by_workshop,
    add_worker,
    mark_present,
    mark_other,
    get_current_shift,
    get_attendance_report,
    get_all_workers_by_workshop
)

api_app = FastAPI()

# Налаштування шаблонів та статики
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
api_app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Моделі даних
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

# Маршрути
@api_app.get("/workshop/{workshop}", response_class=HTMLResponse)
async def workshop_page(request: Request, workshop: str):
    if workshop not in ["DMT", "Пакування"]:
        workshop = "DMT"
    return templates.TemplateResponse("index.html", {"request": request, "workshop": workshop})

@api_app.get("/api/workers/{workshop}")
async def get_workers(workshop: str):
    workers = get_workers_by_workshop(workshop)
    return {"workers": workers}

@api_app.get("/api/all_workers/{workshop}")
async def get_all_workers(workshop: str):
    workers = get_all_workers_by_workshop(workshop)
    return {"workers": workers}

@api_app.post("/api/worker")
async def create_worker(worker: WorkerCreate):
    success = add_worker(worker.fullname, worker.workshop)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add worker")
    return {"ok": True}

@api_app.post("/api/mark_present")
async def mark_present_route(mark: AttendanceMark):
    success = mark_present(mark.worker_id, mark.shift_hours, mark.ktu)
    return {"ok": success}

@api_app.post("/api/mark_other")
async def mark_other_route(mark: OtherMark):
    success = mark_other(mark.worker_id, mark.status)
    return {"ok": success}

@api_app.get("/api/report")
async def get_report():
    report = get_attendance_report()
    return report

@api_app.get("/api/current_shift")
async def current_shift():
    shift = get_current_shift()
    return {"shift_hours": shift}

@api_app.get("/api/stats")
async def get_stats():
    stats = get_today_statistics()
    return stats

@api_app.get("/")
async def root():
    return {"message": "Worker Management API is running"}

@api_app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
