from __future__ import annotations

import pytest
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from config import Settings
from models import PromptPair
from services.download_service import DownloadService
from services.fal_service import FalService
from services.prompt_service import PromptService
from services.upload_service import UploadService


SKILL_TEXT = (
    "You are a JSON API. "
    'Output {"prompts":[{"lang":"en","prompt":"..."},{"lang":"zh","prompt":"..."}]}'
)

MOCK_PROMPT_PAIR = PromptPair(
    en="Wide stabilized tracking shot. Style & Mood: clean studio.",
    zh="广角稳定跟拍。风格与氛围：干净棚拍。",
)

MOCK_AZURE_RESPONSE_BODY = {
    "output": [
        {
            "content": [
                {
                    "text": (
                        '{"prompts":['
                        '{"lang":"en","prompt":"Wide stabilized tracking shot. Style & Mood: clean studio."},'
                        '{"lang":"zh","prompt":"广角稳定跟拍。风格与氛围：干净棚拍。"}'
                        "]}"
                    )
                }
            ]
        }
    ]
}


@pytest.fixture
def skill_file(tmp_path) -> Path:
    f = tmp_path / "skill.txt"
    f.write_text(SKILL_TEXT, encoding="utf-8")
    return f


@pytest.fixture
def mock_settings(tmp_path, skill_file) -> Settings:
    (tmp_path / "uploads").mkdir(exist_ok=True)
    (tmp_path / "downloads").mkdir(exist_ok=True)
    return Settings(
        app_name="Test Pipeline",
        app_host="127.0.0.1",
        app_port=8000,
        debug=False,
        azure_openai_responses_url=(
            "https://test.cognitiveservices.azure.com/openai/responses"
            "?api-version=2025-04-01-preview"
        ),
        azure_openai_api_key="test-azure-key-123",
        openai_model="gpt-4o",
        skill_file=skill_file,
        fal_key="live-fal-key:secret123",
        fal_mock_mode=True,
        upload_dir=tmp_path / "uploads",
        download_dir=tmp_path / "downloads",
        max_poll_attempts=60,
        poll_interval_seconds=5,
        mock_completion_seconds=10,
        mock_video_url="https://example.com/mock-video.mp4",
        request_timeout_seconds=30.0,
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test-anon-key",
        supabase_publishable_key="test-publishable-key",
        database_url="",
    )


@pytest.fixture
def live_settings(mock_settings) -> Settings:
    return replace(mock_settings, fal_mock_mode=False)


@pytest.fixture
def fal_mock(mock_settings) -> FalService:
    return FalService(settings=mock_settings)


@pytest.fixture
def fal_live(live_settings) -> FalService:
    return FalService(settings=live_settings)


@pytest.fixture
def prompt_svc(mock_settings) -> PromptService:
    return PromptService(settings=mock_settings)


@pytest.fixture
def upload_svc(mock_settings) -> UploadService:
    return UploadService(settings=mock_settings)


@pytest.fixture
def download_svc_mock(mock_settings) -> DownloadService:
    return DownloadService(settings=mock_settings)


@pytest.fixture
def download_svc_live(live_settings) -> DownloadService:
    return DownloadService(settings=live_settings)


def make_mock_prompt_service() -> MagicMock:
    svc = MagicMock()
    svc.start_product_analysis = AsyncMock(
        return_value="Story concept: the product radiates understated confidence."
    )
    svc.chat_turn = AsyncMock(
        return_value="Refined: dramatic side lighting that sculpts fabric texture."
    )
    svc.generate_from_conversation = AsyncMock(return_value=MOCK_PROMPT_PAIR)
    svc.generate_bilingual_prompt = AsyncMock(return_value=MOCK_PROMPT_PAIR)
    return svc


class _MockFalService(FalService):
    """FalService with upload_image stubbed to avoid real CDN calls in tests."""

    async def upload_image(self, path: str) -> str:  # type: ignore[override]
        return f"https://cdn.fal.ai/test/{Path(path).name}"


@pytest.fixture
def app_client(mock_settings) -> TestClient:
    from main import app
    from routers.api import (
        chat_session_store,
        get_download_service,
        get_fal_service,
        get_prompt_service,
        get_upload_service,
        job_store,
        preview_store,
    )

    app.dependency_overrides[get_fal_service] = lambda: _MockFalService(settings=mock_settings)
    app.dependency_overrides[get_prompt_service] = make_mock_prompt_service
    app.dependency_overrides[get_upload_service] = lambda: UploadService(settings=mock_settings)
    app.dependency_overrides[get_download_service] = lambda: DownloadService(settings=mock_settings)

    # Reset in-memory stores between tests
    for store in (preview_store, job_store, chat_session_store):
        with store._lock:
            store._items.clear()

    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()
