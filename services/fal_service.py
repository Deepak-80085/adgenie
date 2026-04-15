from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import randint
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException

from config import Settings

logger = logging.getLogger(__name__)

try:
    import fal_client
    from fal_client.client import AppId as _FalAppId
except ImportError:  # pragma: no cover - dependency is only needed in live mode
    fal_client = None
    _FalAppId = None  # type: ignore[assignment]


FAL_ENDPOINTS = {
    "text-to-video": "bytedance/seedance-2.0/text-to-video",
    "image-to-video": "bytedance/seedance-2.0/image-to-video",
}


@dataclass
class FalService:
    settings: Settings
    _mock_jobs: dict[str, dict[str, Any]] = field(default_factory=dict)

    @staticmethod
    def _poll_base_url(endpoint: str, request_id: str) -> str:
        """Build the correct fal.ai queue base URL for status/result polling.

        fal_client uses owner/alias only (drops the path component) for polling.
        e.g. 'bytedance/seedance-2.0/text-to-video' → queue.fal.run/bytedance/seedance-2.0/requests/{id}
        """
        if _FalAppId is not None:
            app_id = _FalAppId.from_endpoint_id(endpoint)
            return f"https://queue.fal.run/{app_id.owner}/{app_id.alias}/requests/{request_id}"
        # Fallback: drop everything after second slash segment
        parts = endpoint.split("/")
        base = "/".join(parts[:2])
        return f"https://queue.fal.run/{base}/requests/{request_id}"

    def _resolve_endpoint(self, mode: str) -> str:
        try:
            return FAL_ENDPOINTS[mode]
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}") from exc

    def has_live_key(self) -> bool:
        return bool(self.settings.fal_key and not self.settings.fal_key.startswith("replace-"))

    def _require_fal_key(self) -> None:
        if not self.has_live_key():
            raise HTTPException(status_code=500, detail="FAL_KEY is not configured in .env")
        os.environ["FAL_KEY"] = self.settings.fal_key

    async def upload_image(self, path: str) -> str:
        self._require_fal_key()
        if fal_client is None:
            raise HTTPException(
                status_code=500,
                detail="fal-client is not installed. Run `pip install -r requirements.txt` to enable live uploads.",
            )

        try:
            return await asyncio.to_thread(fal_client.upload_file, Path(path), repository="cdn")
        except Exception as exc:  # pragma: no cover - depends on live fal environment
            raise HTTPException(status_code=502, detail=f"fal.ai image upload failed: {exc}") from exc

    async def submit_generation(
        self,
        *,
        mode: str,
        prompt: str,
        resolution: str,
        duration: str,
        aspect_ratio: str,
        generate_audio: bool,
        image_url: str | None,
        end_user_id: str | None = None,
    ) -> tuple[str, str, str, str | None, str | None]:
        endpoint = self._resolve_endpoint(mode)

        if self.settings.fal_mock_mode:
            request_id = f"mock-{uuid4()}"
            self._mock_jobs[request_id] = {
                "created_at": datetime.now(timezone.utc),
                "endpoint": endpoint,
                "prompt": prompt,
                "image_url": image_url,
                "resolution": resolution,
                "duration": duration,
                "aspect_ratio": aspect_ratio,
                "generate_audio": generate_audio,
                "end_user_id": end_user_id,
            }
            return request_id, endpoint, "IN_QUEUE", None, None

        self._require_fal_key()

        payload: dict[str, Any] = {
            "prompt": prompt,
            "resolution": resolution,
            "generate_audio": generate_audio,
        }
        if duration and duration != "auto":
            payload["duration"] = duration  # fal.ai expects string e.g. '5' not int
        if aspect_ratio and aspect_ratio != "auto":
            payload["aspect_ratio"] = aspect_ratio
        if image_url:
            payload["image_url"] = image_url
        if end_user_id:
            payload["end_user_id"] = end_user_id

        headers = {
            "Authorization": f"Key {self.settings.fal_key}",
            "Content-Type": "application/json",
        }

        submit_url = f"https://queue.fal.run/{endpoint}"
        logger.info("fal.ai SUBMIT → POST %s  payload=%s", submit_url, payload)
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            try:
                response = await client.post(submit_url, headers=headers, json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error("fal.ai SUBMIT error [%s]: %s", exc.response.status_code, exc.response.text)
                raise HTTPException(status_code=502, detail=f"fal.ai submission error: {exc.response.text}") from exc
            except httpx.HTTPError as exc:
                logger.error("fal.ai SUBMIT network error: %s", exc)
                raise HTTPException(status_code=502, detail=f"fal.ai submission failed: {exc}") from exc

        body = response.json()
        logger.info("fal.ai SUBMIT ← request_id=%s  status_url=%s  response_url=%s",
                    body.get("request_id"), body.get("status_url"), body.get("response_url"))
        return (
            body["request_id"],
            endpoint,
            body.get("status", "IN_QUEUE"),
            body.get("status_url"),
            body.get("response_url"),
        )

    async def get_status(self, *, endpoint: str, request_id: str, status_url: str | None = None) -> dict[str, Any]:
        if self.settings.fal_mock_mode:
            mock = self._mock_jobs.get(request_id)
            if mock is None:
                raise HTTPException(status_code=404, detail="Mock fal job not found")
            elapsed = datetime.now(timezone.utc) - mock["created_at"]
            halfway = self.settings.mock_completion_seconds / 2
            if elapsed.total_seconds() >= self.settings.mock_completion_seconds:
                return {"status": "COMPLETED"}
            if elapsed.total_seconds() >= halfway:
                return {"status": "IN_PROGRESS"}
            return {"status": "IN_QUEUE"}

        url = status_url or (self._poll_base_url(endpoint, request_id) + "/status")
        logger.info("fal.ai STATUS → GET %s", url)
        headers = {"Authorization": f"Key {self.settings.fal_key}"}
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error("fal.ai STATUS error [%s]: %s", exc.response.status_code, exc.response.text)
                raise HTTPException(status_code=502, detail=f"fal.ai status error [{exc.response.status_code}]: {exc.response.text}") from exc
            except httpx.HTTPError as exc:
                logger.error("fal.ai STATUS network error: %s", exc)
                raise HTTPException(status_code=502, detail=f"fal.ai status request failed: {exc}") from exc
        data = response.json()
        logger.info("fal.ai STATUS ← %s", data)
        return data

    async def get_result(self, *, endpoint: str, request_id: str, response_url: str | None = None) -> dict[str, Any]:
        if self.settings.fal_mock_mode:
            mock = self._mock_jobs.get(request_id)
            if mock is None:
                raise HTTPException(status_code=404, detail="Mock fal job not found")
            return {
                "video": {
                    "url": self.settings.mock_video_url,
                    "file_name": "mock-video.mp4",
                    "file_size": None,
                },
                "seed": randint(1000000000, 1999999999),
            }

        url = response_url or self._poll_base_url(endpoint, request_id)
        logger.info("fal.ai RESULT → GET %s", url)
        headers = {"Authorization": f"Key {self.settings.fal_key}"}
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error("fal.ai RESULT error [%s]: %s", exc.response.status_code, exc.response.text)
                raise HTTPException(
                    status_code=502,
                    detail=f"fal.ai result error [{exc.response.status_code}]: {exc.response.text}",
                ) from exc
            except httpx.HTTPError as exc:
                logger.error("fal.ai RESULT network error: %s", exc)
                raise HTTPException(status_code=502, detail=f"fal.ai result request failed: {exc}") from exc
        data = response.json()
        logger.info("fal.ai RESULT ← video_url=%s  seed=%s", data.get("video", {}).get("url"), data.get("seed"))
        return data
