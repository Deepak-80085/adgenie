from __future__ import annotations

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.fal_service import FalService


# ── helpers ───────────────────────────────────────────────────────────────────

def _http_response(status: int = 200, body: dict | None = None, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body or {}
    resp.text = text
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=text, request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _async_client(response: MagicMock) -> MagicMock:
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=response)
    client.get = AsyncMock(return_value=response)
    return client


# ── has_live_key ──────────────────────────────────────────────────────────────

def test_has_live_key_with_real_key(fal_live):
    assert fal_live.has_live_key() is True


def test_has_live_key_with_placeholder(mock_settings):
    svc = FalService(settings=replace(mock_settings, fal_key="replace-me"))
    assert svc.has_live_key() is False


def test_has_live_key_empty(mock_settings):
    svc = FalService(settings=replace(mock_settings, fal_key=""))
    assert svc.has_live_key() is False


# ── _require_fal_key ──────────────────────────────────────────────────────────

def test_require_fal_key_raises_when_missing(mock_settings):
    svc = FalService(settings=replace(mock_settings, fal_key="replace-me"))
    with pytest.raises(Exception) as exc_info:
        svc._require_fal_key()
    assert exc_info.value.status_code == 500
    assert "FAL_KEY" in exc_info.value.detail


def test_require_fal_key_sets_env_var(fal_live, monkeypatch):
    import os
    monkeypatch.delenv("FAL_KEY", raising=False)
    fal_live._require_fal_key()
    assert os.environ.get("FAL_KEY") == fal_live.settings.fal_key


# ── submit_generation — mock mode ─────────────────────────────────────────────

async def test_submit_generation_mock_mode_returns_mock_id(fal_mock):
    request_id, endpoint, status, status_url, response_url = await fal_mock.submit_generation(
        mode="text-to-video",
        prompt="A figure walks through mist.",
        resolution="480p",
        duration="5",
        aspect_ratio="16:9",
        generate_audio=False,
        image_url=None,
    )
    assert request_id.startswith("mock-")
    assert "seedance" in endpoint
    assert status == "IN_QUEUE"
    assert status_url is None  # mock mode has no real URLs
    assert response_url is None


async def test_submit_generation_mock_mode_stores_job(fal_mock):
    request_id, _, _, _, _ = await fal_mock.submit_generation(
        mode="text-to-video",
        prompt="Test scene.",
        resolution="720p",
        duration="auto",
        aspect_ratio="9:16",
        generate_audio=True,
        image_url=None,
        end_user_id="user-abc",
    )
    job = fal_mock._mock_jobs[request_id]
    assert job["prompt"] == "Test scene."
    assert job["resolution"] == "720p"
    assert job["end_user_id"] == "user-abc"


async def test_submit_generation_image_to_video_endpoint(fal_mock):
    _, endpoint, _, _, _ = await fal_mock.submit_generation(
        mode="image-to-video",
        prompt="Product rotates.",
        resolution="480p",
        duration="4",
        aspect_ratio="1:1",
        generate_audio=False,
        image_url="https://cdn.example.com/image.png",
    )
    assert "image-to-video" in endpoint


async def test_submit_generation_unsupported_mode_raises_400(fal_mock):
    with pytest.raises(Exception) as exc_info:
        await fal_mock.submit_generation(
            mode="bad-mode",
            prompt="X",
            resolution="480p",
            duration="5",
            aspect_ratio="16:9",
            generate_audio=False,
            image_url=None,
        )
    assert exc_info.value.status_code == 400


# ── submit_generation — live mode ─────────────────────────────────────────────

async def test_submit_generation_live_sends_correct_payload(fal_live):
    success_resp = _http_response(200, body={
        "request_id": "fal-req-123",
        "status": "IN_QUEUE",
        "status_url": "https://queue.fal.run/bytedance/seedance-2.0/text-to-video/requests/fal-req-123/status",
        "response_url": "https://queue.fal.run/bytedance/seedance-2.0/text-to-video/requests/fal-req-123",
    })
    with patch("httpx.AsyncClient", return_value=_async_client(success_resp)):
        request_id, endpoint, status, status_url, response_url = await fal_live.submit_generation(
            mode="text-to-video",
            prompt="Scene prompt here.",
            resolution="480p",
            duration="5",
            aspect_ratio="16:9",
            generate_audio=False,
            image_url=None,
        )
    assert request_id == "fal-req-123"
    assert status == "IN_QUEUE"
    assert "status" in status_url
    assert response_url.endswith("fal-req-123")


async def test_submit_generation_live_duration_as_string(fal_live):
    """Duration must be sent as a string (e.g. '7'), not an int — fal.ai Seedance 2.0 rejects int literals."""
    captured_payload: dict = {}

    async def fake_post(url, headers, json):
        captured_payload.update(json)
        return _http_response(200, body={"request_id": "r1", "status": "IN_QUEUE", "status_url": "https://q/s", "response_url": "https://q/r"})

    client_mock = AsyncMock()
    client_mock.__aenter__ = AsyncMock(return_value=client_mock)
    client_mock.__aexit__ = AsyncMock(return_value=None)
    client_mock.post = fake_post

    with patch("httpx.AsyncClient", return_value=client_mock):
        await fal_live.submit_generation(
            mode="text-to-video",
            prompt="p",
            resolution="480p",
            duration="7",
            aspect_ratio="16:9",
            generate_audio=False,
            image_url=None,
        )
    assert captured_payload["duration"] == "7"
    assert isinstance(captured_payload["duration"], str)


async def test_submit_generation_live_auto_duration_omitted(fal_live):
    """'auto' duration must NOT be included in the payload."""
    captured_payload: dict = {}

    async def fake_post(url, headers, json):
        captured_payload.update(json)
        return _http_response(200, body={"request_id": "r1", "status": "IN_QUEUE", "status_url": "https://q/s", "response_url": "https://q/r"})

    client_mock = AsyncMock()
    client_mock.__aenter__ = AsyncMock(return_value=client_mock)
    client_mock.__aexit__ = AsyncMock(return_value=None)
    client_mock.post = fake_post

    with patch("httpx.AsyncClient", return_value=client_mock):
        await fal_live.submit_generation(
            mode="text-to-video",
            prompt="p",
            resolution="480p",
            duration="auto",
            aspect_ratio="16:9",
            generate_audio=False,
            image_url=None,
        )
    assert "duration" not in captured_payload


async def test_submit_generation_live_auto_aspect_ratio_omitted(fal_live):
    """'auto' aspect_ratio must NOT be included in the payload."""
    captured_payload: dict = {}

    async def fake_post(url, headers, json):
        captured_payload.update(json)
        return _http_response(200, body={"request_id": "r1", "status": "IN_QUEUE", "status_url": "https://q/s", "response_url": "https://q/r"})

    client_mock = AsyncMock()
    client_mock.__aenter__ = AsyncMock(return_value=client_mock)
    client_mock.__aexit__ = AsyncMock(return_value=None)
    client_mock.post = fake_post

    with patch("httpx.AsyncClient", return_value=client_mock):
        await fal_live.submit_generation(
            mode="text-to-video",
            prompt="p",
            resolution="480p",
            duration="5",
            aspect_ratio="auto",
            generate_audio=False,
            image_url=None,
        )
    assert "aspect_ratio" not in captured_payload


async def test_submit_generation_live_image_url_included(fal_live):
    captured_payload: dict = {}

    async def fake_post(url, headers, json):
        captured_payload.update(json)
        return _http_response(200, body={"request_id": "r1", "status": "IN_QUEUE", "status_url": "https://q/s", "response_url": "https://q/r"})

    client_mock = AsyncMock()
    client_mock.__aenter__ = AsyncMock(return_value=client_mock)
    client_mock.__aexit__ = AsyncMock(return_value=None)
    client_mock.post = fake_post

    with patch("httpx.AsyncClient", return_value=client_mock):
        await fal_live.submit_generation(
            mode="image-to-video",
            prompt="p",
            resolution="480p",
            duration="5",
            aspect_ratio="1:1",
            generate_audio=False,
            image_url="https://cdn.fal.ai/img.png",
        )
    assert captured_payload["image_url"] == "https://cdn.fal.ai/img.png"


async def test_submit_generation_live_http_error_raises_502(fal_live):
    error_resp = _http_response(400, text="Bad Request: invalid prompt")
    with patch("httpx.AsyncClient", return_value=_async_client(error_resp)):
        with pytest.raises(Exception) as exc_info:
            await fal_live.submit_generation(
                mode="text-to-video",
                prompt="p",
                resolution="480p",
                duration="5",
                aspect_ratio="16:9",
                generate_audio=False,
                image_url=None,
            )
    assert exc_info.value.status_code == 502


async def test_submit_generation_live_network_error_raises_502(fal_live):
    client_mock = AsyncMock()
    client_mock.__aenter__ = AsyncMock(return_value=client_mock)
    client_mock.__aexit__ = AsyncMock(return_value=None)
    client_mock.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    with patch("httpx.AsyncClient", return_value=client_mock):
        with pytest.raises(Exception) as exc_info:
            await fal_live.submit_generation(
                mode="text-to-video",
                prompt="p",
                resolution="480p",
                duration="5",
                aspect_ratio="16:9",
                generate_audio=False,
                image_url=None,
            )
    assert exc_info.value.status_code == 502


# ── get_status — mock mode ────────────────────────────────────────────────────

async def test_get_status_mock_in_queue(fal_mock):
    request_id, endpoint, _, _, _ = await fal_mock.submit_generation(
        mode="text-to-video", prompt="p", resolution="480p",
        duration="5", aspect_ratio="16:9", generate_audio=False, image_url=None,
    )
    result = await fal_mock.get_status(endpoint=endpoint, request_id=request_id)
    assert result["status"] == "IN_QUEUE"


async def test_get_status_mock_completes_after_elapsed(fal_mock):
    from datetime import datetime, timezone, timedelta

    request_id, endpoint, _, _, _ = await fal_mock.submit_generation(
        mode="text-to-video", prompt="p", resolution="480p",
        duration="5", aspect_ratio="16:9", generate_audio=False, image_url=None,
    )
    # Backdate creation time past mock_completion_seconds
    fal_mock._mock_jobs[request_id]["created_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=20)
    )
    result = await fal_mock.get_status(endpoint=endpoint, request_id=request_id)
    assert result["status"] == "COMPLETED"


async def test_get_status_mock_in_progress_at_halfway(fal_mock):
    from datetime import datetime, timezone, timedelta

    request_id, endpoint, _, _, _ = await fal_mock.submit_generation(
        mode="text-to-video", prompt="p", resolution="480p",
        duration="5", aspect_ratio="16:9", generate_audio=False, image_url=None,
    )
    halfway = fal_mock.settings.mock_completion_seconds / 2 + 1
    fal_mock._mock_jobs[request_id]["created_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=halfway)
    )
    result = await fal_mock.get_status(endpoint=endpoint, request_id=request_id)
    assert result["status"] == "IN_PROGRESS"


async def test_get_status_mock_unknown_id_raises_404(fal_mock):
    with pytest.raises(Exception) as exc_info:
        await fal_mock.get_status(endpoint="bytedance/seedance-2.0/text-to-video", request_id="ghost-id")
    assert exc_info.value.status_code == 404


# ── get_status — live mode ────────────────────────────────────────────────────

async def test_get_status_live_success(fal_live):
    resp = _http_response(200, body={"status": "IN_PROGRESS"})
    with patch("httpx.AsyncClient", return_value=_async_client(resp)):
        result = await fal_live.get_status(
            endpoint="bytedance/seedance-2.0/text-to-video",
            request_id="req-abc",
        )
    assert result["status"] == "IN_PROGRESS"


async def test_get_status_live_http_error_raises_502(fal_live):
    resp = _http_response(500, text="Internal server error")
    with patch("httpx.AsyncClient", return_value=_async_client(resp)):
        with pytest.raises(Exception) as exc_info:
            await fal_live.get_status(
                endpoint="bytedance/seedance-2.0/text-to-video",
                request_id="req-abc",
            )
    assert exc_info.value.status_code == 502


# ── get_result — mock mode ────────────────────────────────────────────────────

async def test_get_result_mock_returns_mock_video(fal_mock):
    request_id, endpoint, _, _, _ = await fal_mock.submit_generation(
        mode="text-to-video", prompt="p", resolution="480p",
        duration="5", aspect_ratio="16:9", generate_audio=False, image_url=None,
    )
    result = await fal_mock.get_result(endpoint=endpoint, request_id=request_id)
    assert result["video"]["url"] == fal_mock.settings.mock_video_url
    assert isinstance(result["seed"], int)


async def test_get_result_mock_unknown_id_raises_404(fal_mock):
    with pytest.raises(Exception) as exc_info:
        await fal_mock.get_result(
            endpoint="bytedance/seedance-2.0/text-to-video",
            request_id="does-not-exist",
        )
    assert exc_info.value.status_code == 404


# ── get_result — live mode ────────────────────────────────────────────────────

async def test_get_result_live_success(fal_live):
    body = {"video": {"url": "https://cdn.fal.ai/out.mp4", "file_name": "out.mp4"}, "seed": 42}
    resp = _http_response(200, body=body)
    with patch("httpx.AsyncClient", return_value=_async_client(resp)):
        result = await fal_live.get_result(
            endpoint="bytedance/seedance-2.0/text-to-video",
            request_id="req-123",
        )
    assert result["video"]["url"] == "https://cdn.fal.ai/out.mp4"


async def test_get_result_live_http_error_raises_502(fal_live):
    resp = _http_response(404, text="Not found")
    with patch("httpx.AsyncClient", return_value=_async_client(resp)):
        with pytest.raises(Exception) as exc_info:
            await fal_live.get_result(
                endpoint="bytedance/seedance-2.0/text-to-video",
                request_id="req-123",
            )
    assert exc_info.value.status_code == 502
