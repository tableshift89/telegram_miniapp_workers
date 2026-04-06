import os
import logging
from fastapi import FastAPI
from webhook_handler import app as webhook_app

logging.basicConfig(level=logging.INFO)

# Створюємо головний додаток
app = FastAPI()

# Монтуємо обробник вебхуків (це покриває всі маршрути)
app.mount("/", webhook_app)

# Якщо у вас є окремий API для міні-додатка, розмонтуйте його тут:
# from app.api import api_app
# app.mount("/api", api_app)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Service is running"}
