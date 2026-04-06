from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from .database import SessionLocal, get_workers_by_workshop, add_worker, mark_present, mark_other, get_attendance_report, get_current_shift

api_app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
api_app.mount("/static", StaticFiles(directory="app/static"), name="static")

class WorkerCreate(BaseModel):
    fullname: str
    workshop: str

class AttendanceMark(BaseModel):
    worker_id: int
    ktu: float
    shift_hours: int

class OtherMark(BaseModel):
    worker_id: int
    status: str  # Вщ, Пр, На, Нз

@api_app.get("/workshop/{workshop}", response_class=HTMLResponse)
async def workshop_page(request: Request, workshop: str):
    return templates.TemplateResponse("index.html", {"request": request, "workshop": workshop})

@api_app.get("/api/workers/{workshop}")
async def get_workers(workshop: str):
    workers = get_workers_by_workshop(workshop)
    return {"workers": [{"id": w.id, "fullname": w.fullname} for w in workers]}

@api_app.post("/api/worker")
async def create_worker(worker: WorkerCreate):
    add_worker(worker.fullname, worker.workshop)
    return {"ok": True}

@api_app.post("/api/mark_present")
async def mark_present_route(mark: AttendanceMark):
    shift = get_current_shift() or mark.shift_hours
    mark_present(mark.worker_id, shift, mark.ktu)
    return {"ok": True}

@api_app.post("/api/mark_other")
async def mark_other_route(mark: OtherMark):
    mark_other(mark.worker_id, mark.status)
    return {"ok": True}

@api_app.get("/api/report")
async def report():
    return get_attendance_report()
