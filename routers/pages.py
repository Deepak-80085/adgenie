from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import get_settings

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(tags=["pages"])


def _ctx(request: Request) -> dict:
    s = get_settings()
    return {
        "supabase_url": s.supabase_url,
        "supabase_anon_key": s.supabase_anon_key,
    }


def _render(request: Request, template: str) -> HTMLResponse:
    # Starlette 1.0 signature: TemplateResponse(request, name, context)
    return templates.TemplateResponse(request, template, _ctx(request))


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return _render(request, "index.html")


@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return _render(request, "login.html")


@router.get("/create", response_class=HTMLResponse)
async def create(request: Request):
    return _render(request, "create.html")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return _render(request, "dashboard.html")


@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return _render(request, "pricing.html")


@router.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    return _render(request, "profile.html")
