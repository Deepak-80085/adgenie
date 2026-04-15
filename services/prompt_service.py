from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import httpx
from fastapi import HTTPException

from config import Settings
from models import ChatMessage, PromptPair

logger = logging.getLogger(__name__)

PROMPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["prompts"],
    "additionalProperties": False,
    "properties": {
        "prompts": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {
                "type": "object",
                "required": ["lang", "prompt"],
                "properties": {
                    "lang": {"type": "string", "enum": ["en", "zh"]},
                    "prompt": {"type": "string"},
                },
                "additionalProperties": False,
            },
        }
    },
}

MAX_FAL_PROMPT_LENGTH = 3200

CREATIVE_DIRECTOR_SYSTEM = (
    "You are a creative video director helping small businesses craft compelling product videos "
    "for Seedance, an AI video generation platform.\n\n"
    "Your role:\n"
    "1. Analyze the product images and business brief the user provides\n"
    "2. Suggest a vivid, story-driven scene concept that showcases the product naturally\n"
    "3. Help refine the concept through conversation\n"
    "4. Keep ideas visual and cinematic — think settings, lighting, movement, mood\n\n"
    "Be concise (3–5 sentences per reply), creative, and practical. "
    "Focus on what story resonates with the product's audience and how the product features naturally in the scene."
)


@dataclass
class PromptService:
    settings: Settings

    def __post_init__(self) -> None:
        self.skill_text = self._load_skill_text(self.settings.skill_file)

    @staticmethod
    def _load_skill_text(path: Path) -> str:
        if not path.exists():
            raise RuntimeError(f"Skill file not found: {path}")
        return path.read_text(encoding="utf-8")

    # ── Config guard ─────────────────────────────────────────────────────────

    def _validate_config(self) -> None:
        if not self.settings.azure_openai_responses_url or not self.settings.azure_openai_api_key:
            raise HTTPException(status_code=500, detail="Azure OpenAI is not configured in .env")
        if "your-resource-name.cognitiveservices.azure.com" in self.settings.azure_openai_responses_url:
            raise HTTPException(
                status_code=500,
                detail=(
                    "AZURE_OPENAI_RESPONSES_URL is still using the placeholder value. "
                    "Update .env with your real Azure OpenAI Responses endpoint."
                ),
            )

    # ── Shared HTTP call ──────────────────────────────────────────────────────

    async def _post_responses(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_config()
        headers = {
            "api-key": self.settings.azure_openai_api_key,
            "Content-Type": "application/json",
        }
        payload_size = len(json.dumps(payload))
        logger.info(
            "Azure OpenAI → POST %s  model=%s  payload_bytes=%d",
            self.settings.azure_openai_responses_url,
            self.settings.openai_model,
            payload_size,
        )
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            try:
                response = await client.post(
                    self.settings.azure_openai_responses_url,
                    headers=headers,
                    json=payload,
                )
                logger.info("Azure OpenAI ← %s %s", response.status_code, response.reason_phrase)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text
                logger.error("Azure OpenAI HTTP error %s: %s", exc.response.status_code, detail)
                raise HTTPException(status_code=502, detail=f"Azure OpenAI error: {detail}") from exc
            except httpx.HTTPError as exc:
                logger.error(
                    "Azure OpenAI connection error [%s]: %r  URL=%s",
                    type(exc).__name__, str(exc), self.settings.azure_openai_responses_url,
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Azure OpenAI request failed [{type(exc).__name__}]: {exc}",
                ) from exc
        return response.json()

    # ── Creative-director chat (plain text responses) ─────────────────────────

    async def start_product_analysis(self, brief: str, image_inputs: Sequence[str]) -> str:
        """Initial analysis — returns a plain-text story concept."""
        payload = {
            "model": self.settings.openai_model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": CREATIVE_DIRECTOR_SYSTEM}]},
                {
                    "role": "user",
                    "content": self._build_user_content(user_prompt=brief, image_inputs=list(image_inputs)),
                },
            ],
        }
        body = await self._post_responses(payload)
        return self._extract_output_text(body)

    async def chat_turn(
        self,
        messages: Sequence[ChatMessage],
        new_message: str,
        image_inputs: Sequence[str],
    ) -> str:
        """Continue the creative-director conversation."""
        input_messages: list[dict[str, Any]] = [
            {"role": "system", "content": [{"type": "input_text", "text": CREATIVE_DIRECTOR_SYSTEM}]},
        ]
        for i, msg in enumerate(messages):
            if msg.role == "user":
                content = (
                    self._build_user_content(msg.content, list(image_inputs))
                    if i == 0 and image_inputs
                    else [{"type": "input_text", "text": msg.content}]
                )
                input_messages.append({"role": "user", "content": content})
            else:
                input_messages.append(
                    {"role": "assistant", "content": [{"type": "output_text", "text": msg.content}]}
                )
        input_messages.append({"role": "user", "content": [{"type": "input_text", "text": new_message}]})

        payload = {"model": self.settings.openai_model, "input": input_messages}
        body = await self._post_responses(payload)
        return self._extract_output_text(body)

    # ── Seedance prompt generation ────────────────────────────────────────────

    async def generate_from_conversation(
        self,
        conversation: Sequence[ChatMessage],
        image_inputs: Sequence[str],
    ) -> PromptPair:
        """Generate structured EN/ZH Seedance prompts from a refined story conversation."""
        input_messages: list[dict[str, Any]] = [
            {"role": "system", "content": [{"type": "input_text", "text": self.skill_text}]},
        ]
        for i, msg in enumerate(conversation):
            if msg.role == "user":
                content = (
                    self._build_user_content(msg.content, list(image_inputs))
                    if i == 0 and image_inputs
                    else [{"type": "input_text", "text": msg.content}]
                )
                input_messages.append({"role": "user", "content": content})
            else:
                input_messages.append(
                    {"role": "assistant", "content": [{"type": "output_text", "text": msg.content}]}
                )
        input_messages.append({
            "role": "user",
            "content": [{"type": "input_text", "text": "Based on our discussion, generate the final Seedance video prompts now."}],
        })

        payload = {
            "model": self.settings.openai_model,
            "input": input_messages,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "seedance_prompt_bundle",
                    "schema": PROMPT_SCHEMA,
                    "strict": True,
                }
            },
        }
        body = await self._post_responses(payload)
        return self._parse_prompt_pair(body)

    async def generate_bilingual_prompt(
        self,
        user_prompt: str,
        image_inputs: Sequence[str] | None = None,
    ) -> PromptPair:
        """Single-turn generation (used by legacy /api/prompt-preview)."""
        payload = {
            "model": self.settings.openai_model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": self.skill_text}]},
                {
                    "role": "user",
                    "content": self._build_user_content(user_prompt=user_prompt, image_inputs=image_inputs or []),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "seedance_prompt_bundle",
                    "schema": PROMPT_SCHEMA,
                    "strict": True,
                }
            },
        }
        body = await self._post_responses(payload)
        return self._parse_prompt_pair(body)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_prompt_pair(self, body: dict[str, Any]) -> PromptPair:
        raw_text = self._extract_output_text(body)
        cleaned_text = self._strip_wrappers(raw_text)
        try:
            parsed = json.loads(cleaned_text)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=502,
                detail={"message": "LLM response was not valid JSON", "raw_output": raw_text},
            ) from exc
        prompts = {
            item.get("lang"): item.get("prompt", "").strip()
            for item in parsed.get("prompts", [])
            if isinstance(item, dict)
        }
        if not prompts.get("en") or not prompts.get("zh"):
            raise HTTPException(
                status_code=502,
                detail={"message": "LLM response did not include both en and zh prompts", "raw_output": raw_text},
            )
        return PromptPair(en=prompts["en"], zh=prompts["zh"])

    @staticmethod
    def _strip_image_tags(text: str) -> str:
        """Remove <<<image_n>>> reference markers before sending to fal.ai.
        These are internal skill markers; fal.ai rejects prompts containing them."""
        import re
        return re.sub(r"<<<image_\d+>>>\s*", "", text).strip()

    @classmethod
    def select_fal_prompt(cls, prompt_pair: PromptPair) -> tuple[str, str]:
        en = cls._strip_image_tags(prompt_pair.en)
        zh = cls._strip_image_tags(prompt_pair.zh)
        if len(en) > MAX_FAL_PROMPT_LENGTH:
            return zh, "zh"
        return en, "en"

    @staticmethod
    def _build_user_content(user_prompt: str, image_inputs: Sequence[str]) -> list[dict[str, str]]:
        brief = user_prompt.strip()
        if image_inputs:
            brief = (
                "The attached product image(s) are the source of truth for what the business is selling. "
                "Analyze the product type, materials, packaging, use case, and brand cues from the images, "
                "then suggest a story-driven concept that showcases the product clearly.\n\n"
                f"Business brief:\n{brief}"
            )
        content: list[dict[str, str]] = [{"type": "input_text", "text": brief}]
        content.extend({"type": "input_image", "image_url": url} for url in image_inputs)
        return content

    @staticmethod
    def _strip_wrappers(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`").strip()
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].strip()
        return stripped

    @staticmethod
    def _extract_output_text(body: dict[str, Any]) -> str:
        if isinstance(body.get("output_text"), str) and body["output_text"].strip():
            return body["output_text"]
        parts: list[str] = []
        for item in body.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if isinstance(content, dict):
                    text = content.get("text")
                    if isinstance(text, str):
                        parts.append(text)
        return "".join(parts) if parts else json.dumps(body)
