from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from config import Settings
from models import UploadedImage


MAX_UPLOAD_BYTES = 30 * 1024 * 1024
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@dataclass
class UploadService:
    settings: Settings

    async def save_uploads(self, uploads: Iterable[UploadFile]) -> list[UploadedImage]:
        saved: list[UploadedImage] = []
        for upload in uploads:
            if not getattr(upload, "filename", None):
                continue
            saved.append(await self._save_upload(upload))
        return saved

    async def _save_upload(self, upload: UploadFile) -> UploadedImage:
        content_type = (upload.content_type or "").lower().strip()
        if content_type not in SUPPORTED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP files are supported")

        data = await upload.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"{upload.filename or 'Uploaded image'} was empty")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail="Each uploaded image must be 30 MB or smaller")

        extension = Path(upload.filename or "").suffix.lower()
        if not extension:
            extension = mimetypes.guess_extension(content_type) or ".bin"

        destination = self.settings.upload_dir / f"{uuid4().hex}{extension}"
        destination.write_bytes(data)

        return UploadedImage(
            upload_id=destination.stem,
            file_name=upload.filename or destination.name,
            content_type=content_type,
            local_path=str(destination),
            size_bytes=len(data),
        )

    def build_data_urls(self, uploads: Iterable[UploadedImage]) -> list[str]:
        return [self.build_data_url(upload) for upload in uploads]

    def build_data_url(self, upload: UploadedImage) -> str:
        data = Path(upload.local_path).read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{upload.content_type};base64,{encoded}"
