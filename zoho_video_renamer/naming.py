"""Generate descriptive names for matched entries.

Two strategies:
- 'still'  : use the matched still's existing filename (stem) as the name.
- 'ai'     : ask a vision API to look at the canonical still and propose a name.
- 'stub'   : fall back to the raw stub (no transformation).

The CLI's `ai-name` subcommand uses 'ai'. The `scan` step records 'stub' or
'still' as a default suggestion so the review UI is usable without any API key.
"""
from __future__ import annotations

import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from .ai import VisionClient
from .ai.base import DEFAULT_NAMING_PROMPT


def name_from_still_filename(filename: str) -> str:
    """Turn 'Mountain Sunset.png' into 'mountain-sunset'."""
    base = re.sub(r"\.[A-Za-z0-9]+$", "", filename)
    base = re.sub(r"[\s_]+", "-", base.strip())
    base = re.sub(r"[^A-Za-z0-9-]", "", base)
    base = re.sub(r"-+", "-", base).strip("-").lower()
    return base or "untitled"


def looks_like_descriptive_name(name: str) -> bool:
    """Heuristic: 'mountain-sunset' yes; '00290-3597567898' no.

    Returns True if the name looks like human-typed words (mostly letters,
    not mostly digits, has at least one hyphen between word-letters).
    """
    if not name:
        return False
    # Reject names that are mostly digits.
    digit_count = sum(c.isdigit() for c in name)
    if digit_count > len(name) * 0.4:
        return False
    # Want at least one letter-only segment between hyphens.
    parts = name.split("-")
    if not any(p.isalpha() and len(p) >= 3 for p in parts):
        return False
    return True


def disambiguate_names(name_by_id: dict[str, str]) -> dict[str, str]:
    """Ensure all values in name_by_id are unique. Append -alt/-two/-three for repeats."""
    seen: Counter = Counter()
    out: dict[str, str] = {}
    suffixes = {2: "alt", 3: "two", 4: "three", 5: "four", 6: "five"}
    for _id in sorted(name_by_id.keys()):
        name = name_by_id[_id]
        seen[name] += 1
        if seen[name] == 1:
            out[_id] = name
        else:
            suf = suffixes.get(seen[name], f"v{seen[name]}")
            out[_id] = f"{name}-{suf}"
    return out


def ai_name_batch_multi(
    client: VisionClient,
    items: list[tuple[str, list[str]]],  # (id, [image_path, ...])
    prompt: str = DEFAULT_NAMING_PROMPT,
    max_workers: int = 4,
    on_progress: Optional[Callable[[int, int, str, str], None]] = None,
) -> dict[str, str]:
    """Like ai_name_batch but each entry can supply multiple images per request.

    Used by videos-only mode where each video produces 3 frames (start/mid/end)
    that are sent to the AI as a single multi-image prompt.
    """
    out: dict[str, str] = {}
    total = len(items)
    done = 0

    def _do(item):
        _id, paths = item
        return _id, client.name_images([p for p in paths if p], prompt=prompt)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_do, it) for it in items]
        for fut in as_completed(futures):
            _id, result = fut.result()
            done += 1
            if result.name and not result.error:
                out[_id] = result.name
            if on_progress:
                on_progress(done, total, _id, result.name or "(failed)")
    return out


def ai_name_batch(
    client: VisionClient,
    items: list[tuple[str, str]],  # (id, image_path)
    prompt: str = DEFAULT_NAMING_PROMPT,
    max_workers: int = 4,
    on_progress: Optional[Callable[[int, int, str, str], None]] = None,
) -> dict[str, str]:
    """Use a VisionClient to name a batch of images.

    Returns {id: name}. Items that fail or return empty are skipped (caller decides
    fallback). on_progress(done, total, id, name) is called as each completes.
    """
    out: dict[str, str] = {}
    total = len(items)
    done = 0

    def _do(item):
        _id, path = item
        result = client.name_image(path, prompt=prompt)
        return _id, result

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_do, it) for it in items]
        for fut in as_completed(futures):
            _id, result = fut.result()
            done += 1
            if result.name and not result.error:
                out[_id] = result.name
            if on_progress:
                on_progress(done, total, _id, result.name or "(failed)")
    return out
