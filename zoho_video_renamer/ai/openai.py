"""OpenAI GPT-4 vision client."""
from __future__ import annotations

import os
import re
from typing import Optional

from .base import DEFAULT_NAMING_PROMPT, NameResult, VisionClient, encode_image_b64

DEFAULT_MODEL = "gpt-4o"


class OpenAIVisionClient(VisionClient):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 max_tokens: int = 64):
        try:
            from openai import OpenAI  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "The 'openai' package is required. Install with: pip install openai"
            ) from e
        from openai import OpenAI

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "No OpenAI API key. Pass --api-key, set OPENAI_API_KEY env var, "
                "or put it in a .env file (see examples/.env.example)."
            )
        self.client = OpenAI(api_key=key)
        self.model = model or os.environ.get("ZVR_OPENAI_MODEL") or DEFAULT_MODEL
        self.max_tokens = max_tokens

    def name_image(self, image_path: str, prompt: str = DEFAULT_NAMING_PROMPT) -> NameResult:
        try:
            b64, media_type = encode_image_b64(image_path)
            data_url = f"data:{media_type};base64,{b64}"
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }],
            )
            text = (resp.choices[0].message.content or "").strip()
            return NameResult(name=_clean_name(text), raw_response=text)
        except Exception as e:
            return NameResult(name="", error=str(e))


def _clean_name(text: str) -> str:
    for line in text.splitlines():
        line = line.strip().strip("`").strip("'\"")
        m = re.search(r"\b([a-z][a-z0-9]*(?:-[a-z][a-z0-9]*){1,4})\b", line)
        if m:
            return m.group(1)
    return text.strip().lower().replace(" ", "-")
