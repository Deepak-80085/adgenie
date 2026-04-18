from __future__ import annotations

import pytest
from pydantic import ValidationError

from models import (
    ChatMessage,
    GenerateVideoRequest,
    JobRecord,
    PromptPair,
    PromptPreviewRequest,
    utc_now_iso,
)


# ── PromptPreviewRequest ──────────────────────────────────────────────────────

def test_prompt_preview_request_valid_text_to_video():
    req = PromptPreviewRequest(user_prompt="A dark chocolate tee orbits slowly.")
    assert req.mode == "text-to-video"
    assert req.resolution == "720p"
    assert req.aspect_ratio == "16:9"
    assert req.generate_audio is True
    assert req.duration == "5"


def test_prompt_preview_request_strips_whitespace_from_prompt():
    req = PromptPreviewRequest(user_prompt="  Padded prompt.  ")
    assert req.user_prompt == "Padded prompt."


def test_prompt_preview_request_empty_prompt_raises():
    with pytest.raises(ValidationError):
        PromptPreviewRequest(user_prompt="")


def test_prompt_preview_request_whitespace_only_prompt_raises():
    with pytest.raises(ValidationError):
        PromptPreviewRequest(user_prompt="   ")


def test_prompt_preview_request_image_to_video_without_image_raises():
    with pytest.raises(ValidationError):
        PromptPreviewRequest(user_prompt="A product.", mode="image-to-video")


def test_prompt_preview_request_image_to_video_with_image_url_valid():
    req = PromptPreviewRequest(
        user_prompt="A product.",
        mode="image-to-video",
        image_url="https://example.com/img.png",
    )
    assert req.mode == "image-to-video"


def test_prompt_preview_request_http_image_url_raises():
    with pytest.raises(ValidationError):
        PromptPreviewRequest(
            user_prompt="A product.",
            mode="image-to-video",
            image_url="http://example.com/img.png",
        )


def test_prompt_preview_request_duration_auto_valid():
    req = PromptPreviewRequest(user_prompt="p", duration="auto")
    assert req.duration == "auto"


def test_prompt_preview_request_duration_min_boundary():
    req = PromptPreviewRequest(user_prompt="p", duration="4")
    assert req.duration == "4"


def test_prompt_preview_request_duration_max_boundary():
    req = PromptPreviewRequest(user_prompt="p", duration="15")
    assert req.duration == "15"


def test_prompt_preview_request_duration_below_min_raises():
    with pytest.raises(ValidationError):
        PromptPreviewRequest(user_prompt="p", duration="3")


def test_prompt_preview_request_duration_above_max_raises():
    with pytest.raises(ValidationError):
        PromptPreviewRequest(user_prompt="p", duration="16")


def test_prompt_preview_request_duration_non_digit_raises():
    with pytest.raises(ValidationError):
        PromptPreviewRequest(user_prompt="p", duration="five")


def test_prompt_preview_request_unsupported_resolution_raises():
    with pytest.raises(ValidationError):
        PromptPreviewRequest(user_prompt="p", resolution="1080p")


def test_prompt_preview_request_unsupported_mode_raises():
    with pytest.raises(ValidationError):
        PromptPreviewRequest(user_prompt="p", mode="gif")


def test_prompt_preview_request_end_user_id_stripped():
    req = PromptPreviewRequest(user_prompt="p", end_user_id="  user-123  ")
    assert req.end_user_id == "user-123"


def test_prompt_preview_request_end_user_id_whitespace_becomes_none():
    req = PromptPreviewRequest(user_prompt="p", end_user_id="   ")
    assert req.end_user_id is None


def test_prompt_preview_request_primary_uploaded_image_none_when_empty():
    req = PromptPreviewRequest(user_prompt="p")
    assert req.primary_uploaded_image() is None


# ── GenerateVideoRequest ──────────────────────────────────────────────────────

def test_generate_video_request_minimal():
    req = GenerateVideoRequest(preview_id="preview-abc")
    assert req.preview_id == "preview-abc"
    assert req.mode is None
    assert req.resolution is None
    assert req.duration is None
    assert req.generate_audio is None


def test_generate_video_request_with_overrides():
    req = GenerateVideoRequest(
        preview_id="p",
        mode="image-to-video",
        resolution="480p",
        duration="5",
        aspect_ratio="9:16",
        generate_audio=False,
        end_user_id="user-xyz",
    )
    assert req.mode == "image-to-video"
    assert req.resolution == "480p"
    assert req.generate_audio is False


# ── PromptPair ────────────────────────────────────────────────────────────────

def test_prompt_pair_en_and_zh():
    pair = PromptPair(en="Wide shot.", zh="宽镜头。")
    assert pair.en == "Wide shot."
    assert pair.zh == "宽镜头。"


# ── ChatMessage ───────────────────────────────────────────────────────────────

def test_chat_message_user():
    msg = ChatMessage(role="user", content="Hello.")
    assert msg.role == "user"


def test_chat_message_invalid_role_raises():
    with pytest.raises(ValidationError):
        ChatMessage(role="system", content="Nope.")


# ── utc_now_iso ───────────────────────────────────────────────────────────────

def test_utc_now_iso_format():
    ts = utc_now_iso()
    assert "T" in ts
    assert ts.endswith("+00:00") or ts.endswith("Z") or "+" in ts
