from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, model_validator


VALID_RESOLUTIONS = {"480p", "720p"}
VALID_MODES = {"text-to-video", "image-to-video"}
VALID_ASPECT_RATIOS = {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "auto"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PromptPair(BaseModel):
    en: str
    zh: str


class UploadedImage(BaseModel):
    upload_id: str
    file_name: str
    content_type: str
    local_path: str
    size_bytes: int
    public_url: str | None = None


class PromptPreviewRequest(BaseModel):
    user_prompt: str = Field(min_length=1)
    mode: Literal["text-to-video", "image-to-video"] = "text-to-video"
    image_url: HttpUrl | None = None
    uploaded_images: list[UploadedImage] = Field(default_factory=list)
    resolution: Literal["480p", "720p"] = "720p"
    duration: str = "auto"
    aspect_ratio: Literal["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "auto"] = "16:9"
    generate_audio: bool = True
    end_user_id: str | None = None

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> "PromptPreviewRequest":
        self.user_prompt = self.user_prompt.strip()
        if not self.user_prompt:
            raise ValueError("user_prompt must not be empty or whitespace only")
        if self.end_user_id is not None:
            self.end_user_id = self.end_user_id.strip() or None
        if self.mode == "image-to-video" and self.image_url is None and not self.uploaded_images:
            raise ValueError("Upload at least one image when mode is image-to-video")
        if self.image_url is not None and self.image_url.scheme != "https":
            raise ValueError("image_url must be a valid HTTPS URL")
        if self.duration != "auto":
            if not self.duration.isdigit():
                raise ValueError("duration must be 'auto' or a string integer between '4' and '15'")
            duration_int = int(self.duration)
            if duration_int < 4 or duration_int > 15:
                raise ValueError("duration must be between '4' and '15'")
        return self

    def primary_uploaded_image(self) -> UploadedImage | None:
        return self.uploaded_images[0] if self.uploaded_images else None


class PromptPreviewRecord(BaseModel):
    preview_id: str
    request: PromptPreviewRequest
    generated_prompt: PromptPair
    created_at: str


class GenerateVideoRequest(BaseModel):
    preview_id: str
    # Optional overrides applied at generation time
    mode: Literal["text-to-video", "image-to-video"] | None = None
    resolution: Literal["480p", "720p"] | None = None
    duration: str | None = None
    aspect_ratio: Literal["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "auto"] | None = None
    generate_audio: bool | None = None
    end_user_id: str | None = None


class JobRecord(BaseModel):
    job_id: str
    preview_id: str
    status: str
    fal_request_id: str | None = None
    fal_endpoint: str | None = None
    fal_status_url: str | None = None   # exact URL from fal.ai submission response
    fal_response_url: str | None = None  # exact URL from fal.ai submission response
    mode: str
    resolution: str
    duration: str
    aspect_ratio: str
    generate_audio: bool
    image_url: str | None = None
    uploaded_images: list[UploadedImage] = Field(default_factory=list)
    end_user_id: str | None = None
    user_prompt: str
    generated_prompt: PromptPair
    submitted_prompt: str | None = None
    submitted_prompt_language: Literal["en", "zh"] | None = None
    video_url: str | None = None
    local_path: str | None = None
    seed: int | None = None
    error: str | None = None
    created_at: str
    completed_at: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    image_inputs: list[str] = Field(default_factory=list)          # CDN or data URLs for the LLM
    uploaded_images: list[UploadedImage] = Field(default_factory=list)  # full metadata for /generate
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)


class ChatSessionStore:
    def __init__(self) -> None:
        self._items: dict[str, ChatSession] = {}
        self._lock = RLock()

    def create(self, *, image_inputs: list[str], uploaded_images: list[UploadedImage]) -> ChatSession:
        session = ChatSession(image_inputs=image_inputs, uploaded_images=uploaded_images)
        with self._lock:
            self._items[session.session_id] = session
        return session

    def get(self, session_id: str) -> ChatSession | None:
        with self._lock:
            return self._items.get(session_id)

    def append_message(self, session_id: str, role: str, content: str) -> ChatSession | None:
        with self._lock:
            session = self._items.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(update={"messages": [*session.messages, ChatMessage(role=role, content=content)]})
            self._items[session_id] = updated
            return updated


class JobsListResponse(BaseModel):
    total: int
    jobs: list[JobRecord]


class PromptPreviewStore:
    def __init__(self) -> None:
        self._items: dict[str, PromptPreviewRecord] = {}
        self._lock = RLock()

    def create(self, request: PromptPreviewRequest, generated_prompt: PromptPair) -> PromptPreviewRecord:
        preview = PromptPreviewRecord(
            preview_id=str(uuid4()),
            request=request,
            generated_prompt=generated_prompt,
            created_at=utc_now_iso(),
        )
        with self._lock:
            self._items[preview.preview_id] = preview
        return preview

    def get(self, preview_id: str) -> PromptPreviewRecord | None:
        with self._lock:
            return self._items.get(preview_id)


class JobStore:
    def __init__(self) -> None:
        self._items: dict[str, JobRecord] = {}
        self._lock = RLock()

    def create(
        self,
        *,
        preview: PromptPreviewRecord,
        fal_request_id: str | None = None,
        fal_endpoint: str | None = None,
        fal_status_url: str | None = None,
        fal_response_url: str | None = None,
        status: str,
        image_url: str | None = None,
        end_user_id: str | None = None,
        submitted_prompt: str | None = None,
        submitted_prompt_language: Literal["en", "zh"] | None = None,
        error: str | None = None,
        completed_at: str | None = None,
    ) -> JobRecord:
        job = JobRecord(
            job_id=str(uuid4()),
            preview_id=preview.preview_id,
            status=status,
            fal_request_id=fal_request_id,
            fal_endpoint=fal_endpoint,
            fal_status_url=fal_status_url,
            fal_response_url=fal_response_url,
            mode=preview.request.mode,
            resolution=preview.request.resolution,
            duration=preview.request.duration,
            aspect_ratio=preview.request.aspect_ratio,
            generate_audio=preview.request.generate_audio,
            image_url=image_url or (str(preview.request.image_url) if preview.request.image_url else None),
            uploaded_images=preview.request.uploaded_images,
            end_user_id=end_user_id or preview.request.end_user_id,
            user_prompt=preview.request.user_prompt,
            generated_prompt=preview.generated_prompt,
            submitted_prompt=submitted_prompt,
            submitted_prompt_language=submitted_prompt_language,
            error=error,
            created_at=utc_now_iso(),
            completed_at=completed_at,
        )
        with self._lock:
            self._items[job.job_id] = job
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._items.get(job_id)

    def update(self, job_id: str, **changes: object) -> JobRecord | None:
        with self._lock:
            current = self._items.get(job_id)
            if current is None:
                return None
            updated = current.model_copy(update=changes)
            self._items[job_id] = updated
            return updated

    def list(self, limit: int = 20, offset: int = 0) -> JobsListResponse:
        with self._lock:
            ordered = sorted(self._items.values(), key=lambda job: job.created_at, reverse=True)
            sliced = ordered[offset : offset + limit]
            return JobsListResponse(total=len(ordered), jobs=sliced)
