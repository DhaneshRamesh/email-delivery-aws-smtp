"""FastAPI application instance."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import campaigns, domains, send, subscribers
from src.core.config import settings
from src.db import models
from src.db.session import engine
from src.utils.logger import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover - startup hook
    configure_logging()
    # Ensure tables exist for local development. Alembic should manage in production.
    models.Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(send.router)
app.include_router(campaigns.router)
app.include_router(subscribers.router)
app.include_router(domains.router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Simple uptime check."""

    return {"status": "ok"}
