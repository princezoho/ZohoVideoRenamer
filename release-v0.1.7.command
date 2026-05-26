#!/usr/bin/env bash
cd "$(dirname "$0")"
set -e
VERSION="v0.1.7"

git add -A
if git diff --cached --quiet; then echo "(nothing to commit)"
else git commit -m "v0.1.7: per-video include/exclude + bundled ffmpeg

User feedback:
1. 'Video thumbnails don't render' — ffmpeg missing from PATH
2. 'Sometimes some matched videos are right but some are wrong, and I can't
   approve the entry without taking the bad ones too'

Fixes:
- pyproject: imageio-ffmpeg dependency (bundles static ffmpeg binary so
  the .dmg works without brew install ffmpeg)
- thumbnailer.py: _ffmpeg_cmd() returns bundled binary path, falls back
  to system PATH ffmpeg
- build.yml: --collect-all imageio_ffmpeg
- ui.py HTML: each video card is now click-to-toggle (KEEP / EXCLUDED).
  Renames preview filters to KEPT-only videos. v1/v2 numbering uses the
  kept-only index. Excluded videos won't be renamed on apply. State
  persists in localStorage.excluded[] (backward-compatible: missing =
  all kept by default).
- cli.py: new 'regen-html' subcommand to rebuild index.html from an
  existing matches.json so users with in-flight reviews can pick up
  the new UI without re-scanning."
fi
git push

git tag -d "$VERSION" 2>/dev/null || true
git push --delete origin "$VERSION" 2>/dev/null || true
sleep 1
git tag -a "$VERSION" -m "Release $VERSION — per-video toggle + bundled ffmpeg"
git push origin "$VERSION"

echo ""
echo "Build at https://github.com/princezoho/ZohoVideoRenamer/actions"
echo "When green (~5 min), download fresh DMG from:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/releases/tag/$VERSION"
echo ""
echo "To upgrade your CURRENT review folder (no rescan needed), once v0.1.7"
echo "is installed run from Terminal:"
echo "  zoho-video-renamer regen-html -o ~/Desktop/video-rename-review2"
echo "Your existing approvals in the browser localStorage are preserved."
