from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import UploadFile

from models import UploadedImage
from services.upload_service import MAX_UPLOAD_BYTES


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_upload_file(filename: str, content_type: str, data: bytes) -> MagicMock:
    upload = MagicMock(spec=UploadFile)
    upload.filename = filename
    upload.content_type = content_type
    upload.read = AsyncMock(return_value=data)
    return upload


TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)
TINY_JPEG = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 20 + bytes([0xFF, 0xD9])
TINY_WEBP = b"RIFF\x1c\x00\x00\x00WEBPVP8 " + b"\x00" * 12


# ── upload_service: valid types ───────────────────────────────────────────────

async def test_save_upload_png(upload_svc):
    upload = _make_upload_file("photo.png", "image/png", TINY_PNG)
    results = await upload_svc.save_uploads([upload])
    assert len(results) == 1
    img = results[0]
    assert img.file_name == "photo.png"
    assert img.content_type == "image/png"
    assert Path(img.local_path).exists()
    assert img.size_bytes == len(TINY_PNG)


async def test_save_upload_jpeg(upload_svc):
    upload = _make_upload_file("product.jpg", "image/jpeg", TINY_JPEG)
    results = await upload_svc.save_uploads([upload])
    assert results[0].content_type == "image/jpeg"


async def test_save_upload_webp(upload_svc):
    upload = _make_upload_file("image.webp", "image/webp", TINY_WEBP)
    results = await upload_svc.save_uploads([upload])
    assert results[0].content_type == "image/webp"


async def test_save_upload_multiple_files(upload_svc):
    uploads = [
        _make_upload_file("a.png", "image/png", TINY_PNG),
        _make_upload_file("b.jpg", "image/jpeg", TINY_JPEG),
    ]
    results = await upload_svc.save_uploads(uploads)
    assert len(results) == 2


# ── upload_service: validation errors ────────────────────────────────────────

async def test_save_upload_rejects_unsupported_type(upload_svc):
    upload = _make_upload_file("doc.pdf", "application/pdf", b"%PDF-1.4")
    with pytest.raises(Exception) as exc_info:
        await upload_svc.save_uploads([upload])
    assert exc_info.value.status_code == 400
    assert "JPEG" in exc_info.value.detail or "PNG" in exc_info.value.detail


async def test_save_upload_rejects_empty_file(upload_svc):
    upload = _make_upload_file("empty.png", "image/png", b"")
    with pytest.raises(Exception) as exc_info:
        await upload_svc.save_uploads([upload])
    assert exc_info.value.status_code == 400


async def test_save_upload_rejects_oversized_file(upload_svc):
    big_data = b"x" * (MAX_UPLOAD_BYTES + 1)
    upload = _make_upload_file("huge.png", "image/png", big_data)
    with pytest.raises(Exception) as exc_info:
        await upload_svc.save_uploads([upload])
    assert exc_info.value.status_code == 400
    assert "30 MB" in exc_info.value.detail


async def test_save_upload_skips_entry_without_filename(upload_svc):
    upload = _make_upload_file("", "image/png", TINY_PNG)
    results = await upload_svc.save_uploads([upload])
    assert results == []


# ── upload_service: build_data_url ────────────────────────────────────────────

def test_build_data_url_produces_valid_base64(upload_svc, tmp_path):
    img_path = tmp_path / "test.png"
    img_path.write_bytes(TINY_PNG)
    img = UploadedImage(
        upload_id="abc",
        file_name="test.png",
        content_type="image/png",
        local_path=str(img_path),
        size_bytes=len(TINY_PNG),
    )
    data_url = upload_svc.build_data_url(img)
    assert data_url.startswith("data:image/png;base64,")
    b64_part = data_url.split(",", 1)[1]
    decoded = base64.b64decode(b64_part)
    assert decoded == TINY_PNG


def test_build_data_urls_returns_one_per_image(upload_svc, tmp_path):
    paths = []
    for i in range(3):
        p = tmp_path / f"img{i}.png"
        p.write_bytes(TINY_PNG)
        paths.append(p)

    images = [
        UploadedImage(
            upload_id=f"id{i}",
            file_name=f"img{i}.png",
            content_type="image/png",
            local_path=str(p),
            size_bytes=len(TINY_PNG),
        )
        for i, p in enumerate(paths)
    ]
    urls = upload_svc.build_data_urls(images)
    assert len(urls) == 3
    assert all(u.startswith("data:") for u in urls)


# ── download_service ──────────────────────────────────────────────────────────

async def test_download_video_mock_mode_returns_none(download_svc_mock):
    result = await download_svc_mock.download_video(
        job_id="job-123",
        video_url="https://example.com/video.mp4",
    )
    assert result is None


async def test_download_video_live_mode_writes_file(download_svc_live):
    video_bytes = b"fake-mp4-content"

    class FakeStreamCtx:
        """Mimics httpx.AsyncClient.stream() context manager."""
        def stream(self, method, url):
            class _Ctx:
                async def __aenter__(_self):
                    class _Resp:
                        status_code = 200
                        def raise_for_status(self): pass
                        async def aread(self): return video_bytes
                    return _Resp()
                async def __aexit__(_self, *args): pass
            return _Ctx()
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass

    with patch("httpx.AsyncClient", return_value=FakeStreamCtx()):
        result = await download_svc_live.download_video(
            job_id="job-abc",
            video_url="https://cdn.fal.ai/video.mp4",
        )

    assert result is not None
    saved_path = Path(result)
    assert saved_path.exists()
    assert saved_path.read_bytes() == video_bytes
    assert saved_path.name == "job-abc.mp4"


async def test_download_video_live_http_error_raises_502(download_svc_live):
    class FakeStreamCtxError:
        def stream(self, method, url):
            class _Ctx:
                async def __aenter__(_self):
                    class _Resp:
                        status_code = 403
                        text = "Forbidden"
                        def raise_for_status(self):
                            raise httpx.HTTPStatusError(
                                "403", request=MagicMock(), response=MagicMock(text="Forbidden")
                            )
                        async def aread(self): return b""
                    return _Resp()
                async def __aexit__(_self, *args): pass
            return _Ctx()
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass

    with patch("httpx.AsyncClient", return_value=FakeStreamCtxError()):
        with pytest.raises(Exception) as exc_info:
            await download_svc_live.download_video(
                job_id="job-err",
                video_url="https://cdn.fal.ai/missing.mp4",
            )
    assert exc_info.value.status_code == 502
