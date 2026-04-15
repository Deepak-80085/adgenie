from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from models import ChatMessage, PromptPair
from services.prompt_service import MAX_FAL_PROMPT_LENGTH, PromptService


# ── helpers ───────────────────────────────────────────────────────────────────

def _azure_response(text: str) -> dict:
    return {"output": [{"content": [{"text": text}]}]}


def _prompt_json(en: str = "EN prompt.", zh: str = "ZH提示。") -> str:
    return json.dumps({"prompts": [{"lang": "en", "prompt": en}, {"lang": "zh", "prompt": zh}]})


def _mock_azure_client(body: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.reason_phrase = "OK" if status < 400 else "Error"
    resp.json.return_value = body
    resp.text = json.dumps(body)
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=resp.text, request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None

    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=resp)
    return client


# ── _strip_wrappers ───────────────────────────────────────────────────────────

def test_strip_wrappers_plain_json():
    raw = '{"prompts":[]}'
    assert PromptService._strip_wrappers(raw) == '{"prompts":[]}'


def test_strip_wrappers_json_fence():
    raw = "```json\n{\"prompts\":[]}\n```"
    result = PromptService._strip_wrappers(raw)
    assert result == '{"prompts":[]}'


def test_strip_wrappers_plain_fence():
    raw = "```\n{\"prompts\":[]}\n```"
    result = PromptService._strip_wrappers(raw)
    assert result.startswith("{")


def test_strip_wrappers_preserves_whitespace_within():
    raw = '  {"a": 1}  '
    result = PromptService._strip_wrappers(raw)
    assert result == '{"a": 1}'


# ── _extract_output_text ──────────────────────────────────────────────────────

def test_extract_output_text_from_output_text_field():
    body = {"output_text": "hello world"}
    assert PromptService._extract_output_text(body) == "hello world"


def test_extract_output_text_ignores_empty_output_text():
    body = {"output_text": "  ", "output": [{"content": [{"text": "from output"}]}]}
    assert PromptService._extract_output_text(body) == "from output"


def test_extract_output_text_from_output_array():
    body = {"output": [{"content": [{"text": "part1"}, {"text": "part2"}]}]}
    assert PromptService._extract_output_text(body) == "part1part2"


def test_extract_output_text_falls_back_to_json_dump():
    body = {"unexpected": "shape"}
    result = PromptService._extract_output_text(body)
    assert "unexpected" in result


def test_extract_output_text_skips_non_dict_content():
    body = {"output": [{"content": ["not a dict", {"text": "valid"}]}]}
    assert PromptService._extract_output_text(body) == "valid"


# ── _parse_prompt_pair ────────────────────────────────────────────────────────

def test_parse_prompt_pair_valid(prompt_svc):
    body = _azure_response(_prompt_json("Wide shot.", "宽镜头。"))
    result = prompt_svc._parse_prompt_pair(body)
    assert result.en == "Wide shot."
    assert result.zh == "宽镜头。"


def test_parse_prompt_pair_invalid_json_raises_502(prompt_svc):
    body = _azure_response("not json at all {{{")
    with pytest.raises(Exception) as exc_info:
        prompt_svc._parse_prompt_pair(body)
    assert exc_info.value.status_code == 502


def test_parse_prompt_pair_missing_en_raises_502(prompt_svc):
    bad = json.dumps({"prompts": [{"lang": "zh", "prompt": "ZH only"}]})
    body = _azure_response(bad)
    with pytest.raises(Exception) as exc_info:
        prompt_svc._parse_prompt_pair(body)
    assert exc_info.value.status_code == 502


def test_parse_prompt_pair_missing_zh_raises_502(prompt_svc):
    bad = json.dumps({"prompts": [{"lang": "en", "prompt": "EN only"}]})
    body = _azure_response(bad)
    with pytest.raises(Exception) as exc_info:
        prompt_svc._parse_prompt_pair(body)
    assert exc_info.value.status_code == 502


def test_parse_prompt_pair_strips_whitespace_from_prompts(prompt_svc):
    padded = json.dumps({"prompts": [{"lang": "en", "prompt": "  EN  "}, {"lang": "zh", "prompt": " ZH "}]})
    body = _azure_response(padded)
    result = prompt_svc._parse_prompt_pair(body)
    assert result.en == "EN"
    assert result.zh == "ZH"


# ── _strip_image_tags ─────────────────────────────────────────────────────────

def test_strip_image_tags_removes_single_tag():
    text = "<<<image_1>>> Wide shot of the product."
    assert PromptService._strip_image_tags(text) == "Wide shot of the product."


def test_strip_image_tags_removes_multiple_tags():
    text = "<<<image_1>>> <<<image_2>>> Wide shot."
    assert PromptService._strip_image_tags(text) == "Wide shot."


def test_strip_image_tags_no_tags_unchanged():
    text = "Wide shot of the product."
    assert PromptService._strip_image_tags(text) == "Wide shot of the product."


def test_strip_image_tags_removes_mid_prompt_tag():
    text = "Style: dark. <<<image_1>>> Camera orbits."
    result = PromptService._strip_image_tags(text)
    assert "<<<image_1>>>" not in result
    assert "Camera orbits." in result


# ── select_fal_prompt ─────────────────────────────────────────────────────────

def test_select_fal_prompt_uses_en_when_under_limit():
    pair = PromptPair(en="Short EN prompt.", zh="短中文提示。")
    prompt, lang = PromptService.select_fal_prompt(pair)
    assert lang == "en"
    assert prompt == "Short EN prompt."


def test_select_fal_prompt_strips_image_tags_from_en():
    pair = PromptPair(en="<<<image_1>>> Wide shot.", zh="宽镜头。")
    prompt, lang = PromptService.select_fal_prompt(pair)
    assert lang == "en"
    assert "<<<image_1>>>" not in prompt
    assert "Wide shot." in prompt


def test_select_fal_prompt_strips_image_tags_from_zh():
    long_en = "A" * (MAX_FAL_PROMPT_LENGTH + 1)
    pair = PromptPair(en=long_en, zh="<<<image_1>>> 宽镜头。")
    prompt, lang = PromptService.select_fal_prompt(pair)
    assert lang == "zh"
    assert "<<<image_1>>>" not in prompt
    assert "宽镜头。" in prompt


def test_select_fal_prompt_uses_zh_when_en_over_limit():
    long_en = "A" * (MAX_FAL_PROMPT_LENGTH + 1)
    pair = PromptPair(en=long_en, zh="短中文提示。")
    prompt, lang = PromptService.select_fal_prompt(pair)
    assert lang == "zh"
    assert prompt == "短中文提示。"


def test_select_fal_prompt_uses_en_at_exact_limit():
    exact_en = "A" * MAX_FAL_PROMPT_LENGTH
    pair = PromptPair(en=exact_en, zh="ZH")
    _, lang = PromptService.select_fal_prompt(pair)
    assert lang == "en"


def test_select_fal_prompt_length_check_uses_stripped_en():
    """Tag stripping must happen before the length check."""
    # EN is over limit only because of the tag; after stripping it fits
    tag = "<<<image_1>>> "
    base = "A" * (MAX_FAL_PROMPT_LENGTH - 5)
    pair = PromptPair(en=tag + base, zh="ZH")
    _, lang = PromptService.select_fal_prompt(pair)
    assert lang == "en"


# ── config validation ─────────────────────────────────────────────────────────

def test_validate_config_raises_500_when_url_missing(prompt_svc):
    from dataclasses import replace
    prompt_svc.settings = replace(prompt_svc.settings, azure_openai_responses_url="")
    with pytest.raises(Exception) as exc_info:
        prompt_svc._validate_config()
    assert exc_info.value.status_code == 500


def test_validate_config_raises_500_for_placeholder_url(prompt_svc):
    from dataclasses import replace
    prompt_svc.settings = replace(
        prompt_svc.settings,
        azure_openai_responses_url="https://your-resource-name.cognitiveservices.azure.com/openai/responses",
    )
    with pytest.raises(Exception) as exc_info:
        prompt_svc._validate_config()
    assert exc_info.value.status_code == 500


# ── generate_bilingual_prompt ─────────────────────────────────────────────────

async def test_generate_bilingual_prompt_success(prompt_svc):
    body = _azure_response(_prompt_json("Wide tracking shot.", "广角跟拍。"))
    with patch("httpx.AsyncClient", return_value=_mock_azure_client(body)):
        result = await prompt_svc.generate_bilingual_prompt("A t-shirt product.")
    assert isinstance(result, PromptPair)
    assert result.en == "Wide tracking shot."
    assert result.zh == "广角跟拍。"


async def test_generate_bilingual_prompt_with_image_inputs(prompt_svc):
    body = _azure_response(_prompt_json("Wide tracking shot.", "广角跟拍。"))
    with patch("httpx.AsyncClient", return_value=_mock_azure_client(body)):
        result = await prompt_svc.generate_bilingual_prompt(
            "A t-shirt product.",
            image_inputs=["https://cdn.example.com/img.png"],
        )
    assert result.en


async def test_generate_bilingual_prompt_azure_401_raises_502(prompt_svc):
    with patch("httpx.AsyncClient", return_value=_mock_azure_client({}, status=401)):
        with pytest.raises(Exception) as exc_info:
            await prompt_svc.generate_bilingual_prompt("A product.")
    assert exc_info.value.status_code == 502


async def test_generate_bilingual_prompt_connection_error_raises_502(prompt_svc):
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(side_effect=httpx.ConnectError("no route"))
    with patch("httpx.AsyncClient", return_value=client):
        with pytest.raises(Exception) as exc_info:
            await prompt_svc.generate_bilingual_prompt("A product.")
    assert exc_info.value.status_code == 502


async def test_generate_bilingual_prompt_invalid_json_from_llm_raises_502(prompt_svc):
    body = _azure_response("not valid json {{{")
    with patch("httpx.AsyncClient", return_value=_mock_azure_client(body)):
        with pytest.raises(Exception) as exc_info:
            await prompt_svc.generate_bilingual_prompt("A product.")
    assert exc_info.value.status_code == 502


# ── generate_from_conversation ────────────────────────────────────────────────

async def test_generate_from_conversation_success(prompt_svc):
    body = _azure_response(_prompt_json("Orbit shot.", "轨道镜头。"))
    messages = [
        ChatMessage(role="user", content="Dark chocolate t-shirt, 360 view"),
        ChatMessage(role="assistant", content="A slow orbital shot would work perfectly."),
    ]
    with patch("httpx.AsyncClient", return_value=_mock_azure_client(body)):
        result = await prompt_svc.generate_from_conversation(messages, image_inputs=[])
    assert result.en == "Orbit shot."


async def test_generate_from_conversation_with_images_in_first_user_message(prompt_svc):
    body = _azure_response(_prompt_json("Product orbit.", "产品轨道。"))
    messages = [
        ChatMessage(role="user", content="Show me a 360 of this tee."),
        ChatMessage(role="assistant", content="A smooth orbital arc fits perfectly."),
    ]
    with patch("httpx.AsyncClient", return_value=_mock_azure_client(body)):
        result = await prompt_svc.generate_from_conversation(
            messages,
            image_inputs=["https://cdn.example.com/tee.png"],
        )
    assert result.zh


# ── start_product_analysis ────────────────────────────────────────────────────

async def test_start_product_analysis_returns_plain_text(prompt_svc):
    body = {"output_text": "The product is a bold, oversized tee with clean edges."}
    with patch("httpx.AsyncClient", return_value=_mock_azure_client(body)):
        result = await prompt_svc.start_product_analysis(
            brief="Dark brown oversized tee",
            image_inputs=[],
        )
    assert "tee" in result


# ── chat_turn ─────────────────────────────────────────────────────────────────

async def test_chat_turn_appends_new_message(prompt_svc):
    body = {"output_text": "Refined: dramatic side lighting."}
    messages = [
        ChatMessage(role="user", content="Initial brief."),
        ChatMessage(role="assistant", content="First concept."),
    ]
    with patch("httpx.AsyncClient", return_value=_mock_azure_client(body)):
        result = await prompt_svc.chat_turn(
            messages=messages,
            new_message="Make it more dramatic.",
            image_inputs=[],
        )
    assert "dramatic" in result
