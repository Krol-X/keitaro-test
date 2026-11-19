from fastapi import FastAPI
from app.routers import campaigns
from app.database import init_db

app = FastAPI(
    title="Keitaro Campaign Management API",
    description="HTTP API для управления кампаниями Keitaro (MVP)",
    version="1.0.0"
)

app.include_router(campaigns.router)

# Инициализация БД при старте
init_db()

@app.get("/health")
def health():
    return {"status": "ok"}
