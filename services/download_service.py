from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import httpx
from fastapi import HTTPException

from config import Settings


@dataclass
class DownloadService:
    settings: Settings

    async def download_video(self, *, job_id: str, video_url: str) -> str | None:
        if self.settings.fal_mock_mode:
            return None

        target_path = self.settings.download_dir / f"{job_id}.mp4"

        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("GET", video_url) as response:
                    response.raise_for_status()
                    payload = await response.aread()
                    await asyncio.to_thread(target_path.write_bytes, payload)
            except httpx.HTTPStatusError as exc:
                raise HTTPException(status_code=502, detail=f"Video download error: {exc.response.text}") from exc
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail=f"Video download failed: {exc}") from exc

        return str(target_path)
