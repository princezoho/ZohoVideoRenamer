"""Match videos to source stills.

Primary strategy: look for a substring of the still's filename embedded in the
video's filename. This works when the source-image filename is preserved as part
of the generated video filename (a common pattern with AI video generators
like Runway, Pika, etc.).

The matcher does not try to be clever about semantic similarity — it relies on
filename substrings. Visual matching is intentionally out of scope for v0.1.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif")
VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")


@dataclass
class Still:
    """A still image found in one of the stills folders."""

    abs_path: str
    rel_path: str  # relative to its scan root
    filename: str
    stub: str  # extension stripped, optional 'copy' / '(N)' suffixes stripped
    is_copy: bool = False  # filename had "copy" suffix
    size: int = 0


@dataclass
class Video:
    """A video file."""

    abs_path: str
    rel_path: str
    filename: str
    size: int = 0


@dataclass
class Match:
    """One still matched to one or more videos."""

    stub: str
    stills: list[Still] = field(default_factory=list)
    videos: list[Video] = field(default_factory=list)


def _strip_copy_suffix(name: str) -> tuple[str, bool]:
    """Strip ' copy', '-copy', or ' (N)' from the end. Return (new_name, was_copy)."""
    was_copy = False
    base = name
    m = re.search(r"^(.*?)\s*[-_ ]?copy$", base, flags=re.IGNORECASE)
    if m:
        base = m.group(1)
        was_copy = True
    # strip ' (1)', ' (2)' duplicate markers
    base = re.sub(r"\s*\(\d+\)$", "", base)
    return base.strip(), was_copy


def stub_from_still_filename(filename: str) -> tuple[str, bool]:
    """Return (stub, is_copy) for a still filename."""
    base = re.sub(r"\.[A-Za-z0-9]+$", "", filename)  # strip extension
    stub, is_copy = _strip_copy_suffix(base)
    return stub, is_copy


def scan_stills(*roots: str, recursive: bool = True, max_depth: int = 6) -> dict[str, list[Still]]:
    """Walk one or more directories and collect all images, indexed by stub.

    Same stub from different folders gets collected into one list.
    """
    index: dict[str, list[Still]] = defaultdict(list)
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        root_abs = os.path.abspath(root)
        for dirpath, dirnames, filenames in os.walk(root_abs):
            depth = dirpath[len(root_abs):].count(os.sep)
            if depth > max_depth:
                dirnames[:] = []
                continue
            if not recursive and depth > 0:
                dirnames[:] = []
                continue
            for fn in filenames:
                if not fn.lower().endswith(IMAGE_EXTS):
                    continue
                if fn.startswith("."):
                    continue
                abs_path = os.path.join(dirpath, fn)
                rel = os.path.relpath(abs_path, root_abs)
                stub, is_copy = stub_from_still_filename(fn)
                try:
                    sz = os.path.getsize(abs_path)
                except OSError:
                    sz = 0
                index[stub].append(Still(abs_path=abs_path, rel_path=rel, filename=fn,
                                          stub=stub, is_copy=is_copy, size=sz))
    return dict(index)


def scan_videos(root: str, recursive: bool = True, max_depth: int = 6) -> list[Video]:
    """Walk a directory and return all video files."""
    out: list[Video] = []
    if not root or not os.path.isdir(root):
        return out
    root_abs = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root_abs):
        depth = dirpath[len(root_abs):].count(os.sep)
        if depth > max_depth:
            dirnames[:] = []
            continue
        if not recursive and depth > 0:
            dirnames[:] = []
            continue
        for fn in filenames:
            if not fn.lower().endswith(VIDEO_EXTS):
                continue
            if fn.startswith("."):
                continue
            abs_path = os.path.join(dirpath, fn)
            rel = os.path.relpath(abs_path, root_abs)
            try:
                sz = os.path.getsize(abs_path)
            except OSError:
                sz = 0
            out.append(Video(abs_path=abs_path, rel_path=rel, filename=fn, size=sz))
    return out


# ---------------------------------------------------------------------------
# Candidate-stub extraction from video filenames
# ---------------------------------------------------------------------------

# Patterns to look for inside a video filename that probably refer to a still.
# Tuned to be permissive — extracts plausible identifiers without false positives
# from random words.
_STUB_PATTERNS = [
    # Numeric-with-dash IDs like 00290-3597567898 (common AI-image filename style)
    re.compile(r"(\d{3,6}-\d{6,12})"),
    # bg##, bg##b, etc. (manual numbering)
    re.compile(r"\b(bg\d+[a-z]?)\b", re.IGNORECASE),
    re.compile(r"(bg\d+[a-z]?)(?=png|jpg|jpeg|webp)", re.IGNORECASE),
    # title-blah
    re.compile(r"\b(title[-\w]*)\b", re.IGNORECASE),
]


def candidate_stubs_for_video(video_filename: str, extra_stubs: Iterable[str] = ()) -> list[str]:
    """Extract plausible source-still identifiers from a video filename.

    Also tries each entry in `extra_stubs` as a literal substring — this is how
    user-defined still names ('mountain-sunset.png' → stub 'mountain-sunset')
    get matched: we just check whether the stub appears anywhere in the video
    filename.
    """
    base = re.sub(r"\.[A-Za-z0-9]+$", "", video_filename)
    base = re.sub(r"_prob\d+$", "", base, flags=re.IGNORECASE)
    base = re.sub(r"_stab\w+$", "", base, flags=re.IGNORECASE)

    seen: set[str] = set()
    out: list[str] = []

    for pat in _STUB_PATTERNS:
        for m in pat.finditer(base):
            s = m.group(1).lower() if pat is _STUB_PATTERNS[1] or pat is _STUB_PATTERNS[2] else m.group(1)
            if s not in seen:
                seen.add(s)
                out.append(s)

    # Literal substring match against user-supplied stubs (longest first to
    # prefer specific matches over generic ones).
    lowered = base.lower()
    for s in sorted(set(extra_stubs), key=len, reverse=True):
        if not s:
            continue
        if s.lower() in lowered and s not in seen:
            seen.add(s)
            out.append(s)

    return out


def match_videos_to_stills(
    stills_index: dict[str, list[Still]],
    videos: list[Video],
) -> tuple[list[Match], list[Video]]:
    """Build matches between videos and stills.

    Returns (matches, unmatched_videos).
    Each match groups one stub -> all its stills + all videos referencing it.
    """
    stub_to_videos: dict[str, list[Video]] = defaultdict(list)
    unmatched: list[Video] = []

    extra_stubs = list(stills_index.keys())

    for v in videos:
        cands = candidate_stubs_for_video(v.filename, extra_stubs=extra_stubs)
        chosen: Optional[str] = None
        for c in cands:
            if c in stills_index:
                chosen = c
                break
        if chosen:
            stub_to_videos[chosen].append(v)
        else:
            unmatched.append(v)

    matches: list[Match] = []
    for stub in sorted(stub_to_videos.keys()):
        matches.append(Match(stub=stub, stills=stills_index.get(stub, []),
                             videos=stub_to_videos[stub]))

    return matches, unmatched


def scan_videos_only(videos: list[Video]) -> list[Match]:
    """Build one Match per video, with no stills attached.

    Used by the 'catalog' / videos-only mode where the user has no source
    stills and just wants AI to look at each video and propose a name.

    The stub is derived from the filename (extension stripped) so the entry
    ID is stable across rescans. There is exactly one video per Match and the
    stills list is always empty.
    """
    matches: list[Match] = []
    for v in videos:
        stub = os.path.splitext(v.filename)[0]
        matches.append(Match(stub=stub, stills=[], videos=[v]))
    return matches


def pick_canonical_still(stills: list[Still], prefer_folders: Iterable[str] = ()) -> Optional[Still]:
    """Pick the 'best' still to represent a stub for preview purposes.

    prefer_folders is an ordered list of folder-name substrings the caller wants
    to prefer (earliest = highest priority). Within the same priority, prefer
    non-copy over copy.
    """
    if not stills:
        return None
    prefer = list(prefer_folders)

    def score(s: Still) -> tuple[int, int]:
        # Lower priority number is better; we negate later.
        for i, frag in enumerate(prefer):
            if frag and frag in s.abs_path:
                return (i, 1 if s.is_copy else 0)
        return (len(prefer), 1 if s.is_copy else 0)

    return min(stills, key=score)
