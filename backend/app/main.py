import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.routers import campaigns
from app.database import open_database


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        url = database_url or os.getenv("DATABASE_URL", "sqlite:///./keitaro.db")
        with open_database(url) as app.state.sessions:
            yield

    app = FastAPI(
        title="Keitaro Campaign Management API",
        description="HTTP API для управления кампаниями Keitaro (MVP)",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(campaigns.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
