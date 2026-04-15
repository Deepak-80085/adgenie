from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import PromptPair


# ── helpers ───────────────────────────────────────────────────────────────────

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _multipart_form(brief: str, image_bytes: bytes | None = None):
    files = [("brief", (None, brief))]
    if image_bytes:
        files.append(("product_images", ("product.png", io.BytesIO(image_bytes), "image/png")))
    return files


# ── GET / ─────────────────────────────────────────────────────────────────────

def test_home_returns_html(app_client):
    resp = app_client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


# ── POST /api/chat/start ──────────────────────────────────────────────────────

def test_chat_start_missing_brief_returns_422(app_client):
    resp = app_client.post("/api/chat/start", data={})
    assert resp.status_code == 422


def test_chat_start_returns_session_and_message(app_client):
    resp = app_client.post(
        "/api/chat/start",
        files=_multipart_form("Dark brown oversized tee, 360 orbit view"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "session_id" in body
    assert "message" in body
    assert body["image_count"] == 0


def test_chat_start_with_image_upload(app_client):
    resp = app_client.post(
        "/api/chat/start",
        files=_multipart_form("Chocolate tee product", TINY_PNG),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["image_count"] == 1


# ── POST /api/chat/message ────────────────────────────────────────────────────

def test_chat_message_unknown_session_returns_404(app_client):
    resp = app_client.post(
        "/api/chat/message",
        json={"session_id": "ghost-session-id", "message": "More dramatic please."},
    )
    assert resp.status_code == 404


def test_chat_message_success(app_client):
    # Create session first
    start = app_client.post(
        "/api/chat/start",
        files=_multipart_form("Dark tee product"),
    )
    session_id = start.json()["session_id"]

    resp = app_client.post(
        "/api/chat/message",
        json={"session_id": session_id, "message": "Make the lighting more dramatic."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == session_id
    assert "message" in body


def test_chat_message_multiple_turns(app_client):
    start = app_client.post(
        "/api/chat/start",
        files=_multipart_form("Product brief"),
    )
    session_id = start.json()["session_id"]

    for msg in ["More contrast", "Add rain", "Sunrise backdrop"]:
        resp = app_client.post(
            "/api/chat/message",
            json={"session_id": session_id, "message": msg},
        )
        assert resp.status_code == 200


# ── POST /api/chat/confirm ────────────────────────────────────────────────────

def test_chat_confirm_unknown_session_returns_404(app_client):
    resp = app_client.post(
        "/api/chat/confirm",
        json={"session_id": "ghost-id"},
    )
    assert resp.status_code == 404


def test_chat_confirm_empty_session_returns_400(app_client):
    from routers.api import chat_session_store
    from models import ChatSession

    empty = ChatSession()
    with chat_session_store._lock:
        chat_session_store._items[empty.session_id] = empty

    resp = app_client.post(
        "/api/chat/confirm",
        json={"session_id": empty.session_id},
    )
    assert resp.status_code == 400


def test_chat_confirm_returns_preview(app_client):
    start = app_client.post(
        "/api/chat/start",
        files=_multipart_form("Dark tee product"),
    )
    session_id = start.json()["session_id"]

    resp = app_client.post(
        "/api/chat/confirm",
        json={"session_id": session_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "preview_id" in body
    assert "generated_prompt" in body
    assert body["generated_prompt"]["en"]
    assert body["generated_prompt"]["zh"]


def test_chat_confirm_with_video_settings(app_client):
    start = app_client.post(
        "/api/chat/start",
        files=_multipart_form("Product brief"),
    )
    session_id = start.json()["session_id"]

    resp = app_client.post(
        "/api/chat/confirm",
        json={
            "session_id": session_id,
            "mode": "text-to-video",
            "resolution": "480p",
            "duration": "5",
            "aspect_ratio": "1:1",
            "generate_audio": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["request"]["resolution"] == "480p"


# ── POST /api/prompt-preview ──────────────────────────────────────────────────

def test_prompt_preview_json_body(app_client):
    resp = app_client.post(
        "/api/prompt-preview",
        json={"user_prompt": "Dark chocolate tee orbits slowly."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "preview_id" in body
    assert "generated_prompt" in body


def test_prompt_preview_multipart_text_only(app_client):
    # Send as multipart/form-data (no file attachment)
    resp = app_client.post(
        "/api/prompt-preview",
        files=[("user_prompt", (None, "Dark tee product video."))],
    )
    assert resp.status_code == 200


def test_prompt_preview_multipart_with_image(app_client):
    resp = app_client.post(
        "/api/prompt-preview",
        data={"user_prompt": "Product orbit shot."},
        files={"product_images": ("tee.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert resp.status_code == 200


def test_prompt_preview_unsupported_content_type_returns_415(app_client):
    resp = app_client.post(
        "/api/prompt-preview",
        content=b"raw bytes",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 415


def test_prompt_preview_empty_prompt_returns_error(app_client):
    resp = app_client.post(
        "/api/prompt-preview",
        json={"user_prompt": ""},
    )
    assert resp.status_code == 422


# ── POST /api/generate ────────────────────────────────────────────────────────

def _create_preview(client) -> str:
    resp = client.post(
        "/api/prompt-preview",
        json={"user_prompt": "Dark tee orbit shot."},
    )
    return resp.json()["preview_id"]


def test_generate_preview_not_found_returns_404(app_client):
    resp = app_client.post(
        "/api/generate",
        json={"preview_id": "does-not-exist"},
    )
    assert resp.status_code == 404


def test_generate_mock_mode_returns_mock_prompt_only(app_client):
    preview_id = _create_preview(app_client)
    resp = app_client.post(
        "/api/generate",
        json={"preview_id": preview_id},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "MOCK_PROMPT_ONLY"
    assert "job_id" in body


def test_generate_mock_mode_stores_job(app_client):
    preview_id = _create_preview(app_client)
    gen_resp = app_client.post("/api/generate", json={"preview_id": preview_id})
    job_id = gen_resp.json()["job_id"]

    jobs_resp = app_client.get("/api/jobs")
    jobs = jobs_resp.json()["jobs"]
    assert any(j["job_id"] == job_id for j in jobs)


def test_generate_with_resolution_override(app_client):
    preview_id = _create_preview(app_client)
    resp = app_client.post(
        "/api/generate",
        json={"preview_id": preview_id, "resolution": "480p", "generate_audio": False},
    )
    assert resp.status_code == 202


def test_generate_image_to_video_without_image_returns_400(app_client):
    # Create a preview with text-to-video mode (no uploaded images)
    preview_id = _create_preview(app_client)
    resp = app_client.post(
        "/api/generate",
        json={"preview_id": preview_id, "mode": "image-to-video"},
    )
    assert resp.status_code == 400
    assert "image" in resp.json()["detail"].lower()


def test_generate_live_mode_submits_to_fal(app_client, live_settings, mock_settings):
    from dataclasses import replace
    from main import app
    from routers.api import get_fal_service
    from services.fal_service import FalService

    # Switch to live fal service that returns a mock fal response
    live_fal = FalService(settings=replace(mock_settings, fal_mock_mode=False))

    async def fake_submit(**kwargs):
        return "fal-req-xyz", "bytedance/seedance-2.0/text-to-video", "IN_QUEUE", "https://q/status", "https://q/result"

    live_fal.submit_generation = fake_submit

    app.dependency_overrides[get_fal_service] = lambda: live_fal

    try:
        preview_id = _create_preview(app_client)
        resp = app_client.post("/api/generate", json={"preview_id": preview_id})
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "queued"
    finally:
        from routers.api import get_fal_service as _gfs
        app.dependency_overrides.pop(get_fal_service, None)


# ── GET /api/status/{job_id} ──────────────────────────────────────────────────

def test_status_unknown_job_returns_404(app_client):
    resp = app_client.get("/api/status/ghost-job")
    assert resp.status_code == 404


def test_status_mock_prompt_only_is_terminal(app_client):
    preview_id = _create_preview(app_client)
    gen = app_client.post("/api/generate", json={"preview_id": preview_id})
    job_id = gen.json()["job_id"]

    resp = app_client.get(f"/api/status/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "MOCK_PROMPT_ONLY"


def test_status_live_job_polls_fal_and_updates(app_client, mock_settings):
    from dataclasses import replace
    from main import app
    from routers.api import get_fal_service
    from services.fal_service import FalService

    live_fal = FalService(settings=replace(mock_settings, fal_mock_mode=False))

    async def fake_submit(**kwargs):
        return "fal-req-poll", "bytedance/seedance-2.0/text-to-video", "IN_QUEUE", "https://q/status", "https://q/result"

    async def fake_get_status(*, endpoint, request_id, status_url=None):
        return {"status": "IN_PROGRESS"}

    live_fal.submit_generation = fake_submit
    live_fal.get_status = fake_get_status

    app.dependency_overrides[get_fal_service] = lambda: live_fal

    try:
        preview_id = _create_preview(app_client)
        gen = app_client.post("/api/generate", json={"preview_id": preview_id})
        job_id = gen.json()["job_id"]

        status_resp = app_client.get(f"/api/status/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "IN_PROGRESS"
    finally:
        app.dependency_overrides.pop(get_fal_service, None)


def test_status_completed_job_fetches_result(app_client, mock_settings):
    from dataclasses import replace
    from main import app
    from routers.api import get_fal_service, get_download_service
    from services.fal_service import FalService
    from services.download_service import DownloadService

    live_fal = FalService(settings=replace(mock_settings, fal_mock_mode=False))
    live_dl = DownloadService(settings=replace(mock_settings, fal_mock_mode=False))

    async def fake_submit(**kwargs):
        return "fal-req-done", "bytedance/seedance-2.0/text-to-video", "IN_QUEUE", "https://q/status", "https://q/result"

    async def fake_get_status(*, endpoint, request_id, status_url=None):
        return {"status": "COMPLETED"}

    async def fake_get_result(*, endpoint, request_id, response_url=None):
        return {"video": {"url": "https://cdn.fal.ai/output.mp4", "file_name": "out.mp4"}, "seed": 42}

    async def fake_download(*, job_id, video_url):
        # Don't actually download
        return None

    live_fal.submit_generation = fake_submit
    live_fal.get_status = fake_get_status
    live_fal.get_result = fake_get_result
    live_dl.download_video = fake_download

    app.dependency_overrides[get_fal_service] = lambda: live_fal
    app.dependency_overrides[get_download_service] = lambda: live_dl

    try:
        preview_id = _create_preview(app_client)
        gen = app_client.post("/api/generate", json={"preview_id": preview_id})
        job_id = gen.json()["job_id"]

        status_resp = app_client.get(f"/api/status/{job_id}")
        assert status_resp.status_code == 200
        body = status_resp.json()
        assert body["status"] == "COMPLETED"
        assert body["video_url"] == "https://cdn.fal.ai/output.mp4"
        assert body["seed"] == 42
    finally:
        app.dependency_overrides.pop(get_fal_service, None)
        app.dependency_overrides.pop(get_download_service, None)


def test_status_failed_job_stores_error(app_client, mock_settings):
    from dataclasses import replace
    from main import app
    from routers.api import get_fal_service
    from services.fal_service import FalService

    live_fal = FalService(settings=replace(mock_settings, fal_mock_mode=False))

    async def fake_submit(**kwargs):
        return "fal-req-fail", "bytedance/seedance-2.0/text-to-video", "IN_QUEUE", "https://q/status", "https://q/result"

    async def fake_get_status(*, endpoint, request_id, status_url=None):
        return {"status": "FAILED"}

    async def fake_get_result(*, endpoint, request_id, response_url=None):
        return {"error": "Prompt safety filter triggered"}

    live_fal.submit_generation = fake_submit
    live_fal.get_status = fake_get_status
    live_fal.get_result = fake_get_result

    app.dependency_overrides[get_fal_service] = lambda: live_fal

    try:
        preview_id = _create_preview(app_client)
        gen = app_client.post("/api/generate", json={"preview_id": preview_id})
        job_id = gen.json()["job_id"]

        status_resp = app_client.get(f"/api/status/{job_id}")
        assert status_resp.status_code == 200
        body = status_resp.json()
        assert body["status"] == "FAILED"
        assert "safety" in body["error"].lower()
    finally:
        app.dependency_overrides.pop(get_fal_service, None)


def test_status_content_policy_violation_marks_job_failed(app_client, mock_settings):
    """When get_result raises a 502 due to content_policy_violation the job must be
    marked FAILED immediately — the browser should stop polling instead of looping."""
    from dataclasses import replace
    from fastapi import HTTPException
    from main import app
    from routers.api import get_fal_service, get_download_service
    from services.fal_service import FalService
    from services.download_service import DownloadService

    live_fal = FalService(settings=replace(mock_settings, fal_mock_mode=False))
    live_dl = DownloadService(settings=replace(mock_settings, fal_mock_mode=False))

    async def fake_submit(**kwargs):
        return "fal-req-cpv", "bytedance/seedance-2.0/text-to-video", "IN_QUEUE", "https://q/status", "https://q/result"

    async def fake_get_status(*, endpoint, request_id, status_url=None):
        return {"status": "COMPLETED"}

    async def fake_get_result(*, endpoint, request_id, response_url=None):
        raise HTTPException(
            status_code=502,
            detail='fal.ai result error [422]: {"detail":[{"type":"content_policy_violation","msg":"Output audio has sensitive content."}]}',
        )

    async def fake_download(*, job_id, video_url):
        return None

    live_fal.submit_generation = fake_submit
    live_fal.get_status = fake_get_status
    live_fal.get_result = fake_get_result
    live_dl.download_video = fake_download

    app.dependency_overrides[get_fal_service] = lambda: live_fal
    app.dependency_overrides[get_download_service] = lambda: live_dl

    try:
        preview_id = _create_preview(app_client)
        gen = app_client.post("/api/generate", json={"preview_id": preview_id})
        job_id = gen.json()["job_id"]

        # First poll: status=COMPLETED, get_result raises → job must be FAILED (not 502)
        status_resp = app_client.get(f"/api/status/{job_id}")
        assert status_resp.status_code == 200, status_resp.text
        body = status_resp.json()
        assert body["status"] == "FAILED"
        assert "audio" in body["error"].lower()
        assert "content policy" in body["error"].lower()

        # Second poll: job is now terminal — must return FAILED immediately, no more fal calls
        status_resp2 = app_client.get(f"/api/status/{job_id}")
        assert status_resp2.status_code == 200
        assert status_resp2.json()["status"] == "FAILED"
    finally:
        app.dependency_overrides.pop(get_fal_service, None)
        app.dependency_overrides.pop(get_download_service, None)


# ── GET /api/jobs ─────────────────────────────────────────────────────────────

def test_list_jobs_empty(app_client):
    resp = app_client.get("/api/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["jobs"] == []


def test_list_jobs_returns_created_jobs(app_client):
    for i in range(3):
        preview_id = _create_preview(app_client)
        app_client.post("/api/generate", json={"preview_id": preview_id})

    resp = app_client.get("/api/jobs")
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


def test_list_jobs_pagination_limit(app_client):
    for _ in range(5):
        preview_id = _create_preview(app_client)
        app_client.post("/api/generate", json={"preview_id": preview_id})

    resp = app_client.get("/api/jobs?limit=2")
    assert len(resp.json()["jobs"]) == 2


def test_list_jobs_pagination_offset(app_client):
    for _ in range(4):
        preview_id = _create_preview(app_client)
        app_client.post("/api/generate", json={"preview_id": preview_id})

    all_jobs = app_client.get("/api/jobs").json()["jobs"]
    offset_jobs = app_client.get("/api/jobs?offset=2").json()["jobs"]

    assert len(offset_jobs) == 2
    # Offset jobs should not appear in first 2 jobs
    all_ids = [j["job_id"] for j in all_jobs[:2]]
    assert not any(j["job_id"] in all_ids for j in offset_jobs)


def test_list_jobs_ordered_newest_first(app_client):
    ids = []
    for i in range(3):
        preview_id = _create_preview(app_client)
        r = app_client.post("/api/generate", json={"preview_id": preview_id})
        ids.append(r.json()["job_id"])

    jobs = app_client.get("/api/jobs").json()["jobs"]
    returned_ids = [j["job_id"] for j in jobs]
    # Most recently created should appear first
    assert returned_ids[0] == ids[-1]


# ── GET /api/download/{job_id} ────────────────────────────────────────────────

def test_download_unknown_job_returns_404(app_client):
    resp = app_client.get("/api/download/ghost-job", follow_redirects=False)
    assert resp.status_code == 404


def test_download_job_with_no_video_returns_404(app_client):
    preview_id = _create_preview(app_client)
    gen = app_client.post("/api/generate", json={"preview_id": preview_id})
    job_id = gen.json()["job_id"]

    resp = app_client.get(f"/api/download/{job_id}", follow_redirects=False)
    assert resp.status_code == 404


def test_download_job_with_video_url_redirects(app_client, mock_settings):
    from dataclasses import replace
    from main import app
    from routers.api import get_fal_service, job_store
    from services.fal_service import FalService

    live_fal = FalService(settings=replace(mock_settings, fal_mock_mode=False))

    async def fake_submit(**kwargs):
        return "fal-req-dl", "bytedance/seedance-2.0/text-to-video", "IN_QUEUE", "https://q/status", "https://q/result"

    async def fake_get_status(*, endpoint, request_id, status_url=None):
        return {"status": "COMPLETED"}

    async def fake_get_result(*, endpoint, request_id, response_url=None):
        return {"video": {"url": "https://cdn.fal.ai/out.mp4"}, "seed": 1}

    live_fal.submit_generation = fake_submit
    live_fal.get_status = fake_get_status
    live_fal.get_result = fake_get_result

    app.dependency_overrides[get_fal_service] = lambda: live_fal

    try:
        preview_id = _create_preview(app_client)
        gen = app_client.post("/api/generate", json={"preview_id": preview_id})
        job_id = gen.json()["job_id"]
        app_client.get(f"/api/status/{job_id}")  # Trigger COMPLETED state

        resp = app_client.get(f"/api/download/{job_id}", follow_redirects=False)
        assert resp.status_code == 307
        assert "cdn.fal.ai" in resp.headers["location"]
    finally:
        app.dependency_overrides.pop(get_fal_service, None)


def test_download_job_with_local_file(app_client, mock_settings, tmp_path):
    from routers.api import job_store, preview_store
    from models import PromptPreviewRequest, PromptPreviewRecord, JobRecord, PromptPair, utc_now_iso

    video_path = tmp_path / "downloads" / "test-job.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"fake-video-content")

    preview_req = PromptPreviewRequest(user_prompt="Test.")
    preview = PromptPreviewRecord(
        preview_id="test-prev",
        request=preview_req,
        generated_prompt=PromptPair(en="EN", zh="ZH"),
        created_at=utc_now_iso(),
    )
    with preview_store._lock:
        preview_store._items["test-prev"] = preview

    job = JobRecord(
        job_id="test-local-job",
        preview_id="test-prev",
        status="COMPLETED",
        mode="text-to-video",
        resolution="720p",
        duration="5",
        aspect_ratio="16:9",
        generate_audio=True,
        user_prompt="Test.",
        generated_prompt=PromptPair(en="EN", zh="ZH"),
        submitted_prompt="EN",
        submitted_prompt_language="en",
        video_url="https://cdn.fal.ai/out.mp4",
        local_path=str(video_path),
        created_at=utc_now_iso(),
        completed_at=utc_now_iso(),
    )
    with job_store._lock:
        job_store._items["test-local-job"] = job

    resp = app_client.get("/api/download/test-local-job", follow_redirects=False)
    assert resp.status_code == 200
    assert resp.content == b"fake-video-content"


# ── GET /api/test-openai ──────────────────────────────────────────────────────

def test_test_openai_placeholder_url_returns_not_ok(app_client, mock_settings):
    from dataclasses import replace
    from main import app
    from config import get_settings

    bad_settings = replace(
        mock_settings,
        azure_openai_responses_url=(
            "https://your-resource-name.cognitiveservices.azure.com/openai/responses"
        ),
    )
    app.dependency_overrides[get_settings] = lambda: bad_settings

    try:
        resp = app_client.get("/api/test-openai")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_test_openai_missing_key_returns_not_ok(app_client, mock_settings):
    from dataclasses import replace
    from main import app
    from config import get_settings

    bad_settings = replace(mock_settings, azure_openai_api_key="replace-me")
    app.dependency_overrides[get_settings] = lambda: bad_settings

    try:
        resp = app_client.get("/api/test-openai")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False
    finally:
        app.dependency_overrides.pop(get_settings, None)
