from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value is not None else default


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_host: str
    app_port: int
    debug: bool
    cors_origins: list[str]
    azure_openai_responses_url: str
    azure_openai_api_key: str
    openai_model: str
    skill_file: Path
    fal_key: str
    fal_mock_mode: bool
    upload_dir: Path
    download_dir: Path
    max_poll_attempts: int
    poll_interval_seconds: int
    mock_completion_seconds: int
    mock_video_url: str
    request_timeout_seconds: float
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_publishable_key: str
    database_url: str


@lru_cache
def get_settings() -> Settings:
    _load_dotenv(BASE_DIR / ".env")

    _raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    cors_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

    settings = Settings(
        app_name=os.getenv("APP_NAME", "Seedance Pipeline"),
        app_host=os.getenv("APP_HOST", "127.0.0.1"),
        app_port=_env_int("APP_PORT", 8000),
        debug=_env_bool("DEBUG", True),
        cors_origins=cors_origins,
        azure_openai_responses_url=os.getenv("AZURE_OPENAI_RESPONSES_URL", ""),
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
        skill_file=Path(os.getenv("SKILL_FILE", str(BASE_DIR / "Seedance_2_Skill.txt"))),
        fal_key=os.getenv("FAL_KEY", ""),
        fal_mock_mode=_env_bool("FAL_MOCK_MODE", True),
        upload_dir=Path(os.getenv("UPLOAD_DIR", "/tmp/uploads" if os.getenv("VERCEL") else str(BASE_DIR / "uploads"))),
        download_dir=Path(os.getenv("DOWNLOAD_DIR", "/tmp/downloads" if os.getenv("VERCEL") else str(BASE_DIR / "downloads"))),
        max_poll_attempts=_env_int("MAX_POLL_ATTEMPTS", 60),
        poll_interval_seconds=_env_int("POLL_INTERVAL_SECONDS", 5),
        mock_completion_seconds=_env_int("MOCK_COMPLETION_SECONDS", 12),
        mock_video_url=os.getenv(
            "MOCK_VIDEO_URL",
            "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
        ),
        request_timeout_seconds=_env_float("REQUEST_TIMEOUT_SECONDS", 60.0),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        supabase_publishable_key=os.getenv("SUPABASE_PUBLISHABLE_KEY", ""),
        database_url=os.getenv("DATABASE_URL", ""),
    )
    def _safe_mkdir(path: Path) -> Path:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError:
            fallback = Path("/tmp") / path.name
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    object.__setattr__(settings, "upload_dir", _safe_mkdir(settings.upload_dir))
    object.__setattr__(settings, "download_dir", _safe_mkdir(settings.download_dir))
    return settings
