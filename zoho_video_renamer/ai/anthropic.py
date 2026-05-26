"""Anthropic Claude vision client."""
from __future__ import annotations

import os
import re
from typing import Optional

from .base import DEFAULT_NAMING_PROMPT, NameResult, VisionClient, encode_image_b64


DEFAULT_MODEL = "claude-sonnet-4-5"


class AnthropicVisionClient(VisionClient):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 max_tokens: int = 64):
        try:
            from anthropic import Anthropic  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "The 'anthropic' package is required. Install with: pip install anthropic"
            ) from e
        from anthropic import Anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "No Anthropic API key. Pass --api-key, set ANTHROPIC_API_KEY env var, "
                "or put it in a .env file (see examples/.env.example)."
            )
        self.client = Anthropic(api_key=key)
        self.model = model or os.environ.get("ZVR_ANTHROPIC_MODEL") or DEFAULT_MODEL
        self.max_tokens = max_tokens

    def name_images(self, image_paths: list[str], prompt: str = DEFAULT_NAMING_PROMPT) -> NameResult:
        try:
            content = []
            for path in image_paths:
                b64, media_type = encode_image_b64(path)
                content.append({"type": "image", "source": {
                    "type": "base64", "media_type": media_type, "data": b64,
                }})
            content.append({"type": "text", "text": prompt})
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": content}],
            )
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
            name = _clean_name(text)
            return NameResult(name=name, raw_response=text)
        except Exception as e:
            return NameResult(name="", error=str(e))


def _clean_name(text: str) -> str:
    """Pick out the first hyphenated-name-looking line from a response."""
    for line in text.splitlines():
        line = line.strip().strip("`").strip("'\"")
        # Find first thing that looks like a hyphenated lowercase identifier
        m = re.search(r"\b([a-z][a-z0-9]*(?:-[a-z][a-z0-9]*){1,4})\b", line)
        if m:
            return m.group(1)
    return text.strip().lower().replace(" ", "-")
