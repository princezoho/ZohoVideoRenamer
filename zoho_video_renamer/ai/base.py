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


VIDEO_NAMING_PROMPT = """You are naming a video file based on what's shown in it. Below are 1-3 frames extracted from the video (in chronological order: start, middle, end if multiple are provided).

Look at the frames and produce a SHORT descriptive name for the overall video.

Rules (strict):
- Exactly 3 English words, joined with hyphens. Example: `sunset-mountain-timelapse`, `kitchen-cooking-pasta`, `dog-running-beach`.
- All lowercase letters and hyphens only. No numbers, no punctuation, no spaces.
- Describe the VIDEO content as a whole: subject + action/setting + a defining detail.
- If the frames show a clear transition (e.g. day to night, before/after), reflect that.
- Avoid generic words like "video", "clip", "scene", "footage".

Output ONLY the 3-word name on a single line. No explanation, no punctuation, no quotes."""


class VisionClient(ABC):
    """Vision-API client that proposes names for images."""

    @abstractmethod
    def name_images(self, image_paths: list[str], prompt: str = DEFAULT_NAMING_PROMPT) -> NameResult:
        """Look at one or more images (jointly), return one NameResult."""
        ...

    def name_image(self, image_path: str, prompt: str = DEFAULT_NAMING_PROMPT) -> NameResult:
        """Convenience wrapper: name a single image. Backwards-compatible API."""
        return self.name_images([image_path], prompt)
