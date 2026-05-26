#!/usr/bin/env bash
cd "$(dirname "$0")"
set -e
VERSION="v0.1.8"

git add -A
if git diff --cached --quiet; then echo "(nothing to commit)"
else git commit -m "v0.1.8: videos-only catalog mode + 3-frame AI + selectable apply operation

User feedback: 'sometimes videos don't need an image attached — it's just
the renaming that matters. Just a folder of videos, AI catalogs them.'

Adds a 'Videos only' mode for cataloging a folder of videos that don't
have source stills. AI watches 3 frames per video (start/mid/end) and
proposes a 3-word descriptive name. Same review UI, same rename pipeline,
same undo log.

Changes:
- matcher.scan_videos_only(): one Match per video, no stills attached
- thumbnailer.extract_three_frames(): 5% / 50% / 95% timecode extraction
- ai/base.VisionClient.name_images(): now takes a list of paths so one
  AI call can see multiple frames at once. New VIDEO_NAMING_PROMPT.
- ai/anthropic + ai/openai: both now send multi-image content blocks
- naming.ai_name_batch_multi(): multi-image batch helper
- ui.py: dataset now has 'mode' field; entries in videos-only mode store
  the 3 frames in _video_frames so ai-name can use them
- apply.execute_plan(): operation parameter (rename|copy|move); copy
  preserves originals, move handles cross-filesystem
- cli.py scan: --videos-only flag; --stills optional when videos-only set
- cli.py apply: --operation flag (rename|copy|move)
- gui.py: 'Videos only' checkbox that hides the Stills folder field;
  'Apply operation' dropdown (in-place rename / copy / move)"
fi
git push

git tag -d "$VERSION" 2>/dev/null || true
git push --delete origin "$VERSION" 2>/dev/null || true
sleep 1
git tag -a "$VERSION" -m "Release $VERSION — videos-only catalog mode"
git push origin "$VERSION"

echo ""
echo "Build at https://github.com/princezoho/ZohoVideoRenamer/actions"
echo "When green (~5 min), download fresh DMG from:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/releases/tag/$VERSION"
