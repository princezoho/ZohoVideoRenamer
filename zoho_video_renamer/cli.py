"""Command-line interface for ZohoVideoRenamer.

Subcommands:
    scan      Walk stills + videos folders, match them, generate thumbnails.
    ai-name   Call a vision API on each canonical still to propose names.
    review    Open the HTML review UI in the system browser.
    apply     Execute the rename plan from an approvals JSON (dry-run by default).
    undo      Reverse a previous rename run using its undo log.

A typical end-to-end flow:

    zoho-video-renamer scan -s ~/Pictures/stills -v ~/Videos/anim -o ./review
    zoho-video-renamer ai-name -o ./review --provider anthropic
    zoho-video-renamer review -o ./review
    # ... user clicks "Export approvals" in browser, gets rename-approvals.json
    zoho-video-renamer apply -o ./review -a ~/Downloads/rename-approvals.json
    zoho-video-renamer apply -o ./review -a ~/Downloads/rename-approvals.json --execute
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from typing import Optional

from . import __version__
from . import apply as apply_mod
from . import naming
from . import undo as undo_mod
from . import ui
from .matcher import (
    Match, match_videos_to_stills, pick_canonical_still,
    scan_stills, scan_videos,
)
from .thumbnailer import (
    batch_extract_video_frames, batch_make_still_thumbs,
    check_ffmpeg, check_ffprobe, safe_id,
)


# ---------------------------------------------------------------------------
# .env loader (no external dep)
# ---------------------------------------------------------------------------

def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                if key and key not in os.environ:
                    os.environ[key] = val
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    return sys.stdout.isatty()


def _c(text: str, color: str) -> str:
    if not _supports_color():
        return text
    codes = {"green": "\033[32m", "red": "\033[31m", "yellow": "\033[33m",
             "blue": "\033[34m", "dim": "\033[2m", "bold": "\033[1m"}
    return f"{codes.get(color, '')}{text}\033[0m"


def info(msg: str) -> None: print(msg)
def good(msg: str) -> None: print(_c(msg, "green"))
def warn(msg: str) -> None: print(_c(msg, "yellow"))
def err(msg: str) -> None: print(_c(msg, "red"), file=sys.stderr)


# ---------------------------------------------------------------------------
# Subcommand: scan
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> int:
    if not check_ffmpeg():
        err("ffmpeg not found. Install via `brew install ffmpeg` or use the bundled .dmg.")
        return 2

    videos_only = bool(getattr(args, "videos_only", False))

    if not args.videos:
        err("--videos directory is required."); return 2
    if not videos_only:
        stills_dirs = [d for d in (args.stills or []) if d]
        if not stills_dirs:
            err("At least one --stills directory is required (or pass --videos-only).")
            return 2
    else:
        stills_dirs = []

    out_dir = os.path.abspath(args.output)
    os.makedirs(os.path.join(out_dir, "thumbs", "stills"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "thumbs", "videos"), exist_ok=True)

    if videos_only:
        info(_c("Videos-only mode (catalog) — no stills folder needed.", "bold"))
        info(_c("Scanning videos folder...", "bold"))
        videos = scan_videos(args.videos, recursive=not args.no_recursive)
        info(f"  Found {len(videos)} videos")
        from .matcher import scan_videos_only
        matches = scan_videos_only(videos)
        unmatched = []
        info(f"  Building {len(matches)} catalog entries (one per video)")
        stills_index = {}
    else:
        info(_c("Scanning stills folders...", "bold"))
        stills_index = scan_stills(*stills_dirs, recursive=not args.no_recursive)
        info(f"  Found {sum(len(v) for v in stills_index.values())} stills across {len(stills_index)} unique stubs")

        info(_c("Scanning videos folder...", "bold"))
        videos = scan_videos(args.videos, recursive=not args.no_recursive)
        info(f"  Found {len(videos)} videos")

        info(_c("Matching videos to stills...", "bold"))
        matches, unmatched = match_videos_to_stills(stills_index, videos)
        info(f"  {len(matches)} stubs matched ({sum(len(m.videos) for m in matches)} video matches)")
        info(f"  {len(unmatched)} videos unmatched")

    # Build canonical-still picker (CLI lets user pass --prefer-folder N times for
    # priority order, default is empty so non-copy wins).
    prefer = args.prefer_folder or []

    def picker(stills):
        return pick_canonical_still(stills, prefer_folders=prefer)

    # Build UI dataset (no AI names yet)
    stills_root_for_ds = stills_dirs[0] if stills_dirs else args.videos
    dataset = ui.matches_to_ui_dataset(
        matches, stills_root=stills_root_for_ds, videos_root=args.videos,
        project_root=out_dir, canonical_picker=picker,
        suggested_names={},
    )
    dataset["mode"] = "videos-only" if videos_only else "stills+videos"

    # Initial suggested_name: derive from still filename when it looks descriptive,
    # else fallback to stub.
    for entry in dataset["entries"]:
        canon_rel = entry.get("canonical_still_rel")
        if canon_rel:
            stem = os.path.splitext(os.path.basename(canon_rel))[0]
            cleaned = naming.name_from_still_filename(stem + ".png")
            if naming.looks_like_descriptive_name(cleaned):
                entry["suggested_name"] = cleaned

    # Save matches.json
    matches_path = os.path.join(out_dir, "matches.json")
    with open(matches_path, "w") as f:
        json.dump(dataset, f, indent=2, default=str)
    info(f"  Wrote {matches_path}")

    # Save unmatched list
    if unmatched:
        unmatched_path = os.path.join(out_dir, "unmatched-videos.json")
        with open(unmatched_path, "w") as f:
            json.dump([{"filename": v.filename, "rel_path": v.rel_path} for v in unmatched], f, indent=2)
        info(f"  Wrote {unmatched_path}")

    def _progress(done, total):
        if done % 25 == 0 or done == total:
            print(f"  {done}/{total}", end="\r")

    if videos_only:
        info(_c("Extracting 3 frames per video (start/mid/end)...", "bold"))
        from .thumbnailer import extract_three_frames
        three_frames_dir = os.path.join(out_dir, "thumbs", "video_frames")
        os.makedirs(three_frames_dir, exist_ok=True)
        three_ok = 0
        for e in dataset["entries"]:
            vid = e["videos"][0]
            src = next((v.abs_path for v in videos if v.filename == vid["filename"]), None)
            if not src:
                continue
            frames = extract_three_frames(src, three_frames_dir, e["id"])
            # Use the mid frame as the entry's still thumbnail for review-UI preview
            if frames.get("mid"):
                e["still_thumb"] = os.path.relpath(frames["mid"], out_dir)
                e["canonical_still_rel"] = e["still_thumb"]
                three_ok += 1
            # Record the 3 frame paths in the entry for the ai-name step
            e["_video_frames"] = {k: os.path.relpath(p, out_dir) for k, p in frames.items()}
        info(f"  Frames extracted for {three_ok}/{len(dataset['entries'])} videos")
        # Re-save matches.json now that still_thumb + _video_frames are populated
        with open(matches_path, "w") as f:
            json.dump(dataset, f, indent=2, default=str)
    else:
        info(_c("Generating still thumbnails...", "bold"))
        still_tasks = []
        for e in dataset["entries"]:
            if not e["still_thumb"] or not e["canonical_still_rel"]:
                continue
            src = os.path.join(out_dir, e["canonical_still_rel"])
            for s in stills_index.get(e["stub"], []):
                if os.path.relpath(s.abs_path, out_dir) == e["canonical_still_rel"]:
                    src = s.abs_path
                    break
            dst = os.path.join(out_dir, e["still_thumb"])
            still_tasks.append((src, dst))
        ok, fail = batch_make_still_thumbs(still_tasks, max_workers=args.workers, on_progress=_progress)
        print()
        info(f"  Stills: {ok} ok, {fail} failed")

    info(_c("Extracting video frame thumbnails...", "bold"))
    vid_tasks = []
    for e in dataset["entries"]:
        for v in e["videos"]:
            src = None
            # Need absolute video paths - look up in our scanned videos
            for vid in videos:
                if vid.filename == v["filename"] and os.path.relpath(vid.abs_path, out_dir) == v["rel_path"]:
                    src = vid.abs_path; break
                if vid.filename == v["filename"]:
                    src = vid.abs_path; break
            if not src:
                continue
            dst = os.path.join(out_dir, v["thumb"])
            vid_tasks.append((src, dst, 0.5))
    ok, fail = batch_extract_video_frames(vid_tasks, max_workers=args.workers, on_progress=_progress)
    print()
    info(f"  Video frames: {ok} ok, {fail} failed")

    # Write the HTML review UI (uses matches.json so we can regenerate if names change)
    html_path = os.path.join(out_dir, "index.html")
    ui.write_review_html(dataset, html_path)
    good(f"\nScan complete. Open the review UI:")
    good(f"  zoho-video-renamer review -o {out_dir}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: ai-name
# ---------------------------------------------------------------------------

def cmd_ai_name(args: argparse.Namespace) -> int:
    _load_dotenv()
    out_dir = os.path.abspath(args.output)
    matches_path = os.path.join(out_dir, "matches.json")
    if not os.path.exists(matches_path):
        err(f"No matches.json in {out_dir}. Run 'scan' first."); return 2
    with open(matches_path) as f:
        dataset = json.load(f)

    from .ai import get_client
    try:
        client = get_client(args.provider, api_key=args.api_key, model=args.model)
    except (ImportError, RuntimeError, ValueError) as e:
        err(str(e)); return 2

    # Multi-image path for videos-only mode: feed all 3 frames per video to
    # the AI so it can name the video as a whole. Falls back to single-image
    # mode for the standard stills+videos flow.
    is_videos_only = dataset.get("mode") == "videos-only"
    items_multi: list[tuple[str, list[str]]] = []
    items_single: list[tuple[str, str]] = []
    for e in dataset["entries"]:
        if is_videos_only and e.get("_video_frames"):
            paths = [os.path.join(out_dir, p) for p in e["_video_frames"].values() if p]
            paths = [p for p in paths if os.path.exists(p)]
            if paths:
                items_multi.append((e["id"], paths))
                continue
        if e["still_thumb"]:
            thumb_abs = os.path.join(out_dir, e["still_thumb"])
            if os.path.exists(thumb_abs):
                items_single.append((e["id"], thumb_abs))

    total = len(items_multi) + len(items_single)
    if total == 0:
        err("No thumbnails to analyze. Run 'scan' first."); return 2

    info(_c(f"Naming {total} entries via {args.provider} ({client.model})...", "bold"))

    def _progress(done, t, _id, name):
        print(f"  {done}/{t}: {_id} -> {_c(name, 'green')}")

    raw_names: dict[str, str] = {}
    if items_multi:
        from .ai.base import VIDEO_NAMING_PROMPT
        raw_names.update(naming.ai_name_batch_multi(
            client, items_multi, prompt=VIDEO_NAMING_PROMPT,
            max_workers=args.workers, on_progress=_progress))
    if items_single:
        raw_names.update(naming.ai_name_batch(
            client, items_single,
            max_workers=args.workers, on_progress=_progress))
    info(f"\nReceived {len(raw_names)}/{len(items)} names. Deduplicating...")
    final_names = naming.disambiguate_names(raw_names)

    # Inject into dataset
    for e in dataset["entries"]:
        if e["id"] in final_names:
            e["suggested_name"] = final_names[e["id"]]

    with open(matches_path, "w") as f:
        json.dump(dataset, f, indent=2)
    info(f"Updated {matches_path}")

    # Regenerate HTML so suggested names show up pre-filled
    html_path = os.path.join(out_dir, "index.html")
    ui.write_review_html(dataset, html_path)
    good("Done. Reopen index.html in your browser (hard-refresh if it was already open).")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: review (open HTML)
# ---------------------------------------------------------------------------

def cmd_review(args: argparse.Namespace) -> int:
    out_dir = os.path.abspath(args.output)
    html_path = os.path.join(out_dir, "index.html")
    if not os.path.exists(html_path):
        err(f"No index.html in {out_dir}. Run 'scan' first."); return 2
    url = "file://" + html_path
    info(f"Opening {url}")
    if not args.no_open:
        webbrowser.open(url)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: apply (dry-run / execute)
# ---------------------------------------------------------------------------

def cmd_apply(args: argparse.Namespace) -> int:
    out_dir = os.path.abspath(args.output)
    matches_path = os.path.join(out_dir, "matches.json")
    if not os.path.exists(matches_path):
        err(f"No matches.json in {out_dir}. Run 'scan' first."); return 2
    with open(matches_path) as f:
        dataset = json.load(f)

    if not args.approvals:
        err("--approvals path is required (export from the browser UI first).")
        return 2
    with open(args.approvals) as f:
        approvals = json.load(f)

    # The browser exports paths relative to the *project root*. Resolve those
    # back to absolute paths. matches.json carries the original absolute paths
    # in all_still_files; for videos we need to look up by rel_path or filename.
    by_rel: dict[str, str] = {}
    for e in dataset["entries"]:
        for v in e["videos"]:
            by_rel[v["rel_path"]] = v["abs_path"]
        for s in e["all_still_files"]:
            by_rel[s["rel_path"]] = s["abs_path"]

    # Resolve each rename's from/to
    for entry in approvals.get("approved", []):
        for r in entry.get("renames", []):
            if r.get("skip"):
                continue
            # 'from' is a project-relative path; look up absolute source
            abs_src = by_rel.get(r["from"])
            if abs_src:
                r["from"] = abs_src
            # 'to' is project-relative; derive absolute target by replacing
            # filename component while keeping the same directory.
            src_path = r["from"]
            src_dir = os.path.dirname(src_path) if os.path.isabs(src_path) else None
            new_filename = os.path.basename(r["to"])
            if src_dir:
                # Same folder as source - preserve folder, change filename
                r["to"] = os.path.join(src_dir, new_filename)
            # else: leave 'to' as-is, build_plan will join with project_root

    plan = apply_mod.build_plan(approvals, project_root=out_dir)

    info(f"Planned: {len(plan.ops)} renames")
    counts: dict[str, int] = {}
    for o in plan.ops:
        counts[o.kind] = counts.get(o.kind, 0) + 1
    for k, v in counts.items():
        info(f"  {k}: {v}")

    if plan.collisions:
        err(f"\n⚠ {len(plan.collisions)} collisions:")
        for d, ops in list(plan.collisions.items())[:10]:
            err(f"  target: {d}")
            for op in ops:
                err(f"    from: {op.src}")
        return 3
    if plan.missing_sources:
        err(f"\n⚠ {len(plan.missing_sources)} source files missing:")
        for o in plan.missing_sources[:10]:
            err(f"  {o.src}")
        return 4

    if not args.execute:
        info("\nFirst 20 planned renames:")
        for o in plan.ops[:20]:
            info(f"  {o.kind}: {o.src}")
            info(_c(f"     -> {o.dst}", "green"))
        warn("\nDry-run complete. Pass --execute to apply.")
        return 0

    op = getattr(args, "operation", "rename")
    good(f"\nExecuting {len(plan.ops)} {op} ops...")
    ok, failed, undo_path = apply_mod.execute_plan(plan, undo_log_dir=out_dir, operation=op)
    good(f"Done. Succeeded: {ok}, Failed: {failed}")
    info(f"Undo log: {undo_path}")
    info(f"To undo: zoho-video-renamer undo --log {undo_path} --execute")
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# Subcommand: regen-html
# ---------------------------------------------------------------------------

def cmd_regen_html(args: argparse.Namespace) -> int:
    out_dir = os.path.abspath(args.output)
    matches_path = os.path.join(out_dir, "matches.json")
    if not os.path.exists(matches_path):
        err(f"No matches.json in {out_dir}. Run 'scan' first.")
        return 2
    with open(matches_path) as f:
        dataset = json.load(f)
    html_path = os.path.join(out_dir, "index.html")
    ui.write_review_html(dataset, html_path)
    good(f"Regenerated {html_path}")
    info("Open it in your browser (your existing approvals are preserved in localStorage).")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: undo
# ---------------------------------------------------------------------------

def cmd_undo(args: argparse.Namespace) -> int:
    if not os.path.exists(args.log):
        err(f"Undo log not found: {args.log}"); return 2
    with open(args.log) as f:
        data = json.load(f)
    items = data.get("renames", [])
    info(f"Loaded {len(items)} entries from {args.log}")
    if not args.execute:
        warn("DRY-RUN. Pass --execute to actually undo.")
        for i in items[:20]:
            info(f"  {i['from']}")
            info(_c(f"     -> {i['to']}", "green"))
        return 0
    ok, failed, missing = undo_mod.undo(args.log, execute=True)
    if missing:
        warn(f"Skipped {len(missing)} entries (source missing - already undone?)")
    good(f"Undone: {ok}, Failed: {failed}")
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zoho-video-renamer",
        description="Match videos to source stills, generate descriptive names, bulk-rename.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    # scan
    sp = sub.add_parser("scan", help="Walk folders, build matches.json, generate thumbnails.")
    sp.add_argument("-s", "--stills", action="append",
                    help="Stills directory. Pass multiple times for multiple folders. Omit when using --videos-only.")
    sp.add_argument("-v", "--videos", required=True, help="Videos directory.")
    sp.add_argument("-o", "--output", default="./review", help="Project output dir (default ./review).")
    sp.add_argument("--videos-only", action="store_true",
                    help="Catalog mode: no stills folder needed. AI looks at 3 frames "
                         "(start/mid/end) per video to propose names.")
    sp.add_argument("--no-recursive", action="store_true", help="Do not recurse into subdirectories.")
    sp.add_argument("--prefer-folder", action="append",
                    help="Substring of folder path to prefer when picking a canonical still. Pass multiple in priority order.")
    sp.add_argument("--workers", type=int, default=4, help="Thumbnail generation parallelism.")
    sp.set_defaults(func=cmd_scan)

    # ai-name
    sp = sub.add_parser("ai-name", help="Use a vision API to propose names.")
    sp.add_argument("-o", "--output", default="./review", help="Project output dir.")
    sp.add_argument("--provider", choices=["anthropic", "openai"], required=True)
    sp.add_argument("--api-key", help="API key (or set ANTHROPIC_API_KEY / OPENAI_API_KEY env var).")
    sp.add_argument("--model", help="Override default model.")
    sp.add_argument("--workers", type=int, default=4, help="Parallel API calls.")
    sp.set_defaults(func=cmd_ai_name)

    # review
    sp = sub.add_parser("review", help="Open the HTML review UI in your browser.")
    sp.add_argument("-o", "--output", default="./review", help="Project output dir.")
    sp.add_argument("--no-open", action="store_true", help="Print URL without opening a browser.")
    sp.set_defaults(func=cmd_review)

    # apply
    sp = sub.add_parser("apply", help="Apply renames from an approvals JSON (dry-run by default).")
    sp.add_argument("-o", "--output", default="./review", help="Project output dir.")
    sp.add_argument("-a", "--approvals", required=True,
                    help="Path to rename-approvals.json (exported from review UI).")
    sp.add_argument("--execute", action="store_true",
                    help="Actually rename. Without this flag, runs as dry-run.")
    sp.add_argument("--operation", choices=["rename", "copy", "move"], default="rename",
                    help="rename: in-place os.rename (default). copy: shutil.copy2, originals preserved. "
                         "move: shutil.move, works across filesystems and removes originals.")
    sp.set_defaults(func=cmd_apply)

    # regen-html
    sp = sub.add_parser("regen-html", help="Regenerate index.html from an existing matches.json (pick up new UI features without rescanning).")
    sp.add_argument("-o", "--output", default="./review", help="Project output dir containing matches.json")
    sp.set_defaults(func=cmd_regen_html)

    # undo
    sp = sub.add_parser("undo", help="Reverse a previous rename run using its undo log.")
    sp.add_argument("--log", required=True, help="Path to rename-undo-*.json")
    sp.add_argument("--execute", action="store_true", help="Actually undo (otherwise dry-run).")
    sp.set_defaults(func=cmd_undo)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    _load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
