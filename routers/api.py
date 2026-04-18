from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, ValidationError

from config import Settings, get_settings
from models import (
    ChatSessionStore,
    GenerateVideoRequest,
    JobStore,
    PromptPreviewRecord,
    PromptPreviewRequest,
    PromptPreviewStore,
    UploadedImage,
    utc_now_iso,
)
from services.download_service import DownloadService
from services.fal_service import FalService
from services.prompt_service import PromptService
from services.upload_service import UploadService

logger = logging.getLogger(__name__)


class ChatMessageBody(BaseModel):
    session_id: str
    message: str


class ConfirmChatRequest(BaseModel):
    session_id: str
    mode: Literal["text-to-video", "image-to-video"] = "text-to-video"
    resolution: Literal["480p", "720p"] = "720p"
    duration: str = "auto"
    aspect_ratio: Literal["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "auto"] = "16:9"
    generate_audio: bool = True
    end_user_id: str | None = None


router = APIRouter(prefix="/api", tags=["api"])

preview_store = PromptPreviewStore()
job_store = JobStore()
chat_session_store = ChatSessionStore()
TERMINAL_JOB_STATUSES = {"COMPLETED", "FAILED", "MOCK_PROMPT_ONLY"}


@lru_cache
def get_prompt_service(settings: Settings = Depends(get_settings)) -> PromptService:
    return PromptService(settings=settings)


@lru_cache
def get_fal_service(settings: Settings = Depends(get_settings)) -> FalService:
    return FalService(settings=settings)


@lru_cache
def get_download_service(settings: Settings = Depends(get_settings)) -> DownloadService:
    return DownloadService(settings=settings)


@lru_cache
def get_upload_service(settings: Settings = Depends(get_settings)) -> UploadService:
    return UploadService(settings=settings)


def _optional_form_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _bool_from_form(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


async def _parse_preview_request(
    raw_request: Request,
    upload_service: UploadService,
) -> PromptPreviewRequest:
    content_type = raw_request.headers.get("content-type", "").lower()

    if content_type.startswith("multipart/form-data"):
        form = await raw_request.form()
        uploaded_images = await upload_service.save_uploads(
            item
            for item in form.getlist("product_images")
            if getattr(item, "filename", None)
        )
        payload: dict[str, object] = {
            "user_prompt": _optional_form_value(form.get("user_prompt")) or "",
            "mode": _optional_form_value(form.get("mode")) or "text-to-video",
            "image_url": _optional_form_value(form.get("image_url")),
            "uploaded_images": uploaded_images,
            "resolution": _optional_form_value(form.get("resolution")) or "720p",
            "duration": _optional_form_value(form.get("duration")) or "auto",
            "aspect_ratio": _optional_form_value(form.get("aspect_ratio")) or "16:9",
            "generate_audio": _bool_from_form(form.get("generate_audio")),
            "end_user_id": _optional_form_value(form.get("end_user_id")),
        }
    elif content_type.startswith("application/json"):
        body = await raw_request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object")
        payload = body
    else:
        raise HTTPException(
            status_code=415,
            detail="Use multipart/form-data for file uploads or application/json for text-only requests",
        )

    try:
        preview_request = PromptPreviewRequest.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    return preview_request


async def _build_preview_image_inputs(
    preview_request: PromptPreviewRequest,
    upload_service: UploadService,
    fal_service: FalService,
) -> tuple[PromptPreviewRequest, list[str]]:
    image_inputs: list[str] = []
    if preview_request.image_url:
        image_inputs.append(str(preview_request.image_url))

    if not preview_request.uploaded_images:
        return preview_request, image_inputs

    if fal_service.has_live_key():
        uploaded_images = []
        for image in preview_request.uploaded_images:
            public_url = image.public_url or await fal_service.upload_image(image.local_path)
            uploaded_images.append(image.model_copy(update={"public_url": public_url}))
            image_inputs.append(public_url)
        preview_request = preview_request.model_copy(update={"uploaded_images": uploaded_images})
        return preview_request, image_inputs

    image_inputs.extend(upload_service.build_data_urls(preview_request.uploaded_images))
    return preview_request, image_inputs


@router.post("/chat/start")
async def chat_start(
    raw_request: Request,
    prompt_service: PromptService = Depends(get_prompt_service),
    upload_service: UploadService = Depends(get_upload_service),
    fal_service: FalService = Depends(get_fal_service),
):
    """Step 1: upload product images + brief → get initial creative story concept."""
    form = await raw_request.form()
    brief = str(form.get("brief", "")).strip()
    if not brief:
        raise HTTPException(status_code=422, detail="brief is required")

    uploaded_images = await upload_service.save_uploads(
        item for item in form.getlist("product_images") if getattr(item, "filename", None)
    )

    # Upload to fal CDN when a live key is available so we get stable public URLs
    image_inputs: list[str] = []
    if uploaded_images:
        if fal_service.has_live_key():
            updated: list[UploadedImage] = []
            for img in uploaded_images:
                cdn_url = await fal_service.upload_image(img.local_path)
                updated.append(img.model_copy(update={"public_url": cdn_url}))
                image_inputs.append(cdn_url)
            uploaded_images = updated
        else:
            image_inputs = upload_service.build_data_urls(uploaded_images)

    analysis = await prompt_service.start_product_analysis(brief=brief, image_inputs=image_inputs)

    session = chat_session_store.create(image_inputs=image_inputs, uploaded_images=uploaded_images)
    chat_session_store.append_message(session.session_id, "user", brief)
    chat_session_store.append_message(session.session_id, "assistant", analysis)

    return {"session_id": session.session_id, "message": analysis, "image_count": len(uploaded_images)}


@router.post("/chat/message")
async def chat_message_endpoint(
    body: ChatMessageBody,
    prompt_service: PromptService = Depends(get_prompt_service),
):
    """Step 2: continue refining the story concept."""
    session = chat_session_store.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")

    response_text = await prompt_service.chat_turn(
        messages=session.messages,
        new_message=body.message,
        image_inputs=session.image_inputs,
    )
    chat_session_store.append_message(session.session_id, "user", body.message)
    chat_session_store.append_message(session.session_id, "assistant", response_text)
    return {"session_id": session.session_id, "message": response_text}


@router.post("/chat/confirm")
async def chat_confirm(
    body: ConfirmChatRequest,
    prompt_service: PromptService = Depends(get_prompt_service),
):
    """Step 3: generate final EN/ZH Seedance prompts from the refined conversation."""
    session = chat_session_store.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if not session.messages:
        raise HTTPException(status_code=400, detail="Chat session has no messages to generate from")

    prompt_pair = await prompt_service.generate_from_conversation(
        conversation=session.messages,
        image_inputs=session.image_inputs,
    )

    user_brief = next((m.content for m in session.messages if m.role == "user"), "Product video")
    preview_request = PromptPreviewRequest(
        user_prompt=user_brief,
        mode=body.mode,
        resolution=body.resolution,
        duration=body.duration,
        aspect_ratio=body.aspect_ratio,
        generate_audio=body.generate_audio,
        end_user_id=body.end_user_id,
        uploaded_images=session.uploaded_images,
    )
    preview = preview_store.create(request=preview_request, generated_prompt=prompt_pair)
    return preview


@router.post("/prompt-preview")
async def create_prompt_preview(
    request: Request,
    prompt_service: PromptService = Depends(get_prompt_service),
    upload_service: UploadService = Depends(get_upload_service),
    fal_service: FalService = Depends(get_fal_service),
):
    preview_request = await _parse_preview_request(request, upload_service)
    preview_request, image_inputs = await _build_preview_image_inputs(preview_request, upload_service, fal_service)
    prompt_pair = await prompt_service.generate_bilingual_prompt(
        preview_request.user_prompt,
        image_inputs=image_inputs,
    )
    preview = preview_store.create(request=preview_request, generated_prompt=prompt_pair)
    return preview


@router.post("/generate", status_code=202)
async def generate_video(
    request: GenerateVideoRequest,
    fal_service: FalService = Depends(get_fal_service),
):
    preview = preview_store.get(request.preview_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Prompt preview not found")

    # Apply any video-setting overrides passed at generate time
    effective_request = preview.request.model_copy(update={
        k: v for k, v in {
            "mode": request.mode,
            "resolution": request.resolution,
            "duration": request.duration,
            "aspect_ratio": request.aspect_ratio,
            "generate_audio": request.generate_audio,
            "end_user_id": request.end_user_id,
        }.items() if v is not None
    })

    submitted_prompt, submitted_prompt_language = PromptService.select_fal_prompt(preview.generated_prompt)
    effective_end_user_id = effective_request.end_user_id
    image_url = str(effective_request.image_url) if effective_request.image_url else None

    logger.info(
        "generate  preview=%s  mode=%s  resolution=%s  duration=%s  aspect=%s  audio=%s  lang=%s  prompt_chars=%d\n--- PROMPT ---\n%s\n--------------",
        request.preview_id,
        effective_request.mode,
        effective_request.resolution,
        effective_request.duration,
        effective_request.aspect_ratio,
        effective_request.generate_audio,
        submitted_prompt_language,
        len(submitted_prompt),
        submitted_prompt,
    )

    if effective_request.mode == "image-to-video":
        primary_uploaded_image = preview.request.primary_uploaded_image()
        if primary_uploaded_image is not None:
            image_url = primary_uploaded_image.public_url
            if image_url is None and not fal_service.settings.fal_mock_mode:
                image_url = await fal_service.upload_image(primary_uploaded_image.local_path)
        elif primary_uploaded_image is None and image_url is None:
            raise HTTPException(status_code=400, detail="Image-to-video requires at least one uploaded image")

    if fal_service.settings.fal_mock_mode:
        job = job_store.create(
            preview=preview,
            status="MOCK_PROMPT_ONLY",
            image_url=image_url,
            end_user_id=effective_end_user_id,
            submitted_prompt=submitted_prompt,
            submitted_prompt_language=submitted_prompt_language,
            completed_at=utc_now_iso(),
        )
        return {
            "job_id": job.job_id,
            "status": job.status,
            "prompt_language": submitted_prompt_language,
            "message": "fal mock mode is enabled, so no request was sent. The selected prompt is stored in the job list.",
        }

    fal_request_id, fal_endpoint, fal_status, fal_status_url, fal_response_url = await fal_service.submit_generation(
        mode=effective_request.mode,
        prompt=submitted_prompt,
        resolution=effective_request.resolution,
        duration=effective_request.duration,
        aspect_ratio=effective_request.aspect_ratio,
        generate_audio=effective_request.generate_audio,
        image_url=image_url,
        end_user_id=effective_end_user_id,
    )
    logger.info(
        "fal.ai job queued  request_id=%s  endpoint=%s  status_url=%s",
        fal_request_id, fal_endpoint, fal_status_url,
    )
    job = job_store.create(
        preview=preview,
        fal_request_id=fal_request_id,
        fal_endpoint=fal_endpoint,
        fal_status_url=fal_status_url,
        fal_response_url=fal_response_url,
        status=fal_status,
        image_url=image_url,
        end_user_id=effective_end_user_id,
        submitted_prompt=submitted_prompt,
        submitted_prompt_language=submitted_prompt_language,
    )
    return {
        "job_id": job.job_id,
        "status": "queued",
        "prompt_language": submitted_prompt_language,
        "message": "Job submitted. Poll /api/status/{job_id} to track progress.",
    }


@router.get("/status/{job_id}")
async def get_job_status(
    job_id: str,
    fal_service: FalService = Depends(get_fal_service),
    download_service: DownloadService = Depends(get_download_service),
):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in TERMINAL_JOB_STATUSES:
        return job

    if not job.fal_endpoint or not job.fal_request_id:
        raise HTTPException(status_code=500, detail="Live fal job is missing tracking metadata")

    logger.info("polling fal.ai  job=%s  request_id=%s  status_url=%s", job_id, job.fal_request_id, job.fal_status_url)
    status_payload = await fal_service.get_status(
        endpoint=job.fal_endpoint,
        request_id=job.fal_request_id,
        status_url=job.fal_status_url,
    )
    fal_status = status_payload.get("status", job.status)
    logger.info("fal.ai status  job=%s  fal_status=%s", job_id, fal_status)

    if fal_status == "COMPLETED":
        try:
            result = await fal_service.get_result(
                endpoint=job.fal_endpoint,
                request_id=job.fal_request_id,
                response_url=job.fal_response_url,
            )
        except HTTPException as exc:
            detail = str(exc.detail)
            logger.error("fal.ai get_result failed for job %s: %s", job_id, detail)
            updated = job_store.update(job_id, status="FAILED", error=detail, completed_at=utc_now_iso())
            return updated

        video_url = result.get("video", {}).get("url")
        if not video_url:
            updated = job_store.update(
                job_id,
                status="FAILED",
                error="fal.ai completed without a video URL",
                completed_at=utc_now_iso(),
            )
            return updated

        audio_field = result.get("audio")
        audio_url = audio_field.get("url") if isinstance(audio_field, dict) else None

        local_path = job.local_path
        if not local_path:
            local_path = await download_service.download_video(job_id=job_id, video_url=video_url)

        updated = job_store.update(
            job_id,
            status="COMPLETED",
            video_url=video_url,
            audio_url=audio_url,
            local_path=local_path,
            seed=result.get("seed"),
            completed_at=utc_now_iso(),
        )
        return updated

    if fal_status == "FAILED":
        try:
            result = await fal_service.get_result(endpoint=job.fal_endpoint, request_id=job.fal_request_id)
            error_message = result.get("error") or "fal.ai returned FAILED"
        except HTTPException as exc:
            error_message = str(exc.detail)

        logger.error("fal.ai job %s FAILED: %s", job_id, error_message)
        updated = job_store.update(job_id, status="FAILED", error=error_message, completed_at=utc_now_iso())
        return updated

    updated = job_store.update(job_id, status=fal_status)
    return {
        "job_id": job_id,
        "status": updated.status if updated else fal_status,
        "message": "Video is being generated on fal.ai...",
    }


@router.get("/test-fal")
async def test_fal(fal_service: FalService = Depends(get_fal_service)):
    """Zero-cost check that the FAL_KEY authenticates against the Seedance 2.0 endpoint."""
    if not fal_service.has_live_key():
        return {"ok": False, "error": "FAL_KEY is not configured"}

    endpoint = "bytedance/seedance-2.0/text-to-video/fast"
    url = f"https://queue.fal.run/{endpoint}"
    headers = {"Authorization": f"Key {fal_service.settings.fal_key}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
        authed = resp.status_code != 401
        return {"ok": authed, "status": resp.status_code, "endpoint": endpoint}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc), "endpoint": endpoint}


@router.get("/test-openai")
async def test_openai(settings: Settings = Depends(get_settings)):
    """Quick connectivity + auth check against Azure OpenAI."""
    url = settings.azure_openai_responses_url
    api_key = settings.azure_openai_api_key
    model = settings.openai_model

    if not url or "your-resource-name" in url:
        return {"ok": False, "error": "AZURE_OPENAI_RESPONSES_URL is still a placeholder"}
    if not api_key or api_key == "replace-me":
        return {"ok": False, "error": "AZURE_OPENAI_API_KEY is not set"}

    payload = {
        "model": model,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": "Say hi"}]}],
        "max_output_tokens": 16,
    }
    headers = {"api-key": api_key, "Content-Type": "application/json"}

    logger.info("test-openai → POST %s", url)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
        logger.info("test-openai ← %s", resp.status_code)
        if resp.is_success:
            return {"ok": True, "status": resp.status_code, "model": model, "url": url}
        return {"ok": False, "status": resp.status_code, "error": resp.text, "url": url}
    except httpx.HTTPError as exc:
        logger.error("test-openai connection error: %s", exc)
        return {"ok": False, "error": str(exc), "url": url}


@router.get("/jobs")
async def list_jobs(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    return job_store.list(limit=limit, offset=offset)


@router.get("/download/{job_id}")
async def download_job_video(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.local_path:
        path = Path(job.local_path)
        if path.exists():
            return FileResponse(path=path, media_type="video/mp4", filename=path.name)
    if job.video_url:
        return RedirectResponse(url=job.video_url)
    raise HTTPException(status_code=404, detail="Video not yet downloaded")
