from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s %(levelname)s [%(name)s] %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
    },
    "root": {"level": "INFO", "handlers": ["console"]},
})

from config import get_settings
from routers.api import router as api_router
from routers.pages import router as pages_router

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (CSS, JS, media)
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Assets (videos)
_ASSETS_DIR = Path(__file__).resolve().parent / "assests"
if _ASSETS_DIR.exists():
    app.mount("/assests", StaticFiles(directory=str(_ASSETS_DIR)), name="assests")

# Routers — pages first so "/" route takes priority
app.include_router(pages_router)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
