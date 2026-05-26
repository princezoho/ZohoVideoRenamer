"""Abstract base class for vision-based name proposers."""
from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


DEFAULT_NAMING_PROMPT = """You are naming an image file. Look at the image and produce a SHORT descriptive name.

Rules (strict):
- Exactly 3 English words, joined with hyphens. Example: `saloon-night-shootout`, `mountain-pink-clouds`, `quiet-forest-path`.
- All lowercase letters and hyphens only. No numbers, no punctuation, no spaces.
- Describe WHAT IS IN the image: concrete subject + setting + a defining detail (color, mood, time of day).
- Avoid generic words like "scene", "image", "background", "art", "photo".

Output ONLY the 3-word name on a single line. No explanation, no punctuation, no quotes."""


@dataclass
class NameResult:
    """One name proposal for one image."""

    name: str
    raw_response: str = ""
    error: Optional[str] = None


def encode_image_b64(path: str) -> tuple[str, str]:
    """Return (base64_data, media_type) for an image path."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    media_type = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("ascii"), media_type


class VisionClient(ABC):
    """Vision-API client that proposes names for images."""

    @abstractmethod
    def name_image(self, image_path: str, prompt: str = DEFAULT_NAMING_PROMPT) -> NameResult:
        """Look at one image, return one NameResult."""
        ...
