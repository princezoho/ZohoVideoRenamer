# Architecture

Short tour of the codebase for anyone hacking on it.

## Layers

```
cli.py            argparse, orchestrates the subcommands
  ↓
matcher.py        scan folders, parse stubs, pair videos with stills
thumbnailer.py    Pillow (stills) + ffmpeg (video frames)
naming.py         existing-name extraction, AI-call orchestration, dedup
ai/               vendor-specific vision clients (anthropic, openai)
ui.py             generates the self-contained HTML review page
apply.py          turns approvals JSON into rename ops, executes with undo
undo.py           reverses a previous run from its undo log
```

No module depends on `cli.py`. All other modules are independently usable from Python.

## Data flow

1. `scan` → walks both folder trees, builds a list of `Match` objects (one per unique still stub, listing all matched videos and all still files for that stub), writes `matches.json`, generates JPEG thumbnails.
2. `ai-name` (optional) → reads `matches.json`, sends each canonical-still thumbnail to a vision API, writes back proposed names as `suggested_name` field, regenerates the HTML.
3. `review` → opens `index.html` in the browser. All UI state (per-entry approvals) is held in `localStorage`. User clicks Export to download `rename-approvals.json`.
4. `apply` → reads both files, resolves project-relative paths back to absolute, dry-runs (default) or executes the renames. Always writes an undo log on `--execute`.
5. `undo` → reverses each move recorded in an undo log.

## Why the browser UI is self-contained HTML

It runs from `file://` with zero server, zero install beyond Python. The state lives in `localStorage` so users can close and re-open the tab without losing decisions. The cost: image and video paths must be relative to the HTML file. The `scan` step generates everything inside the project output directory and references thumbs via relative path; videos are referenced via `../` paths back into the original videos folder, which works as long as the project directory is a sibling of the original media or wherever the relative pathing resolves correctly on the user's machine.

## Adding a new AI provider

1. Add `zoho_video_renamer/ai/<provider>.py` with a class that subclasses `VisionClient` and implements `name_image(self, image_path, prompt) -> NameResult`.
2. Register it in `zoho_video_renamer/ai/__init__.py`'s `get_client` factory.
3. Add the package to `pyproject.toml`'s optional-dependencies and the CLI's `--provider` choices in `cli.py`.

## Testing strategy (TODO)

There's no test suite yet. The most valuable tests to add:

- `matcher.py`: stub extraction across a curated set of synthetic filenames
- `apply.py`: collision detection and undo-log shape
- A small end-to-end test that scans a fixture directory of fake stills + videos (1-frame test clips made with ffmpeg) and asserts the resulting matches.json
