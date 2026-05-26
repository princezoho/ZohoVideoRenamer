#!/usr/bin/env bash
cd "$(dirname "$0")"
set -e
VERSION="v0.1.6"

git add -A
if git diff --cached --quiet; then echo "(nothing to commit)"
else git commit -m "v0.1.6: bundle ffmpeg so video thumbnails work out of the box

User feedback: 'app version doesn't show a thumbnail of the videos'
Root cause: ffmpeg not on user's PATH → silent failure of frame extraction
(stills worked because Pillow doesn't need ffmpeg).

Fix:
- Add imageio-ffmpeg dependency (bundles a static ffmpeg binary, ~50 MB
  added to .dmg, but means users don't need to brew install ffmpeg)
- thumbnailer.py: prefer the bundled imageio_ffmpeg binary, fall back
  to system PATH ffmpeg if available
- build.yml: --collect-all imageio_ffmpeg so PyInstaller bundles it
- gui.py: rewrite the environment check to detect bundled vs system
  ffmpeg and only warn when neither is available"
fi
git push

git tag -d "$VERSION" 2>/dev/null || true
git push --delete origin "$VERSION" 2>/dev/null || true
sleep 1
git tag -a "$VERSION" -m "Release $VERSION — bundle ffmpeg"
git push origin "$VERSION"

echo ""
echo "Build at https://github.com/princezoho/ZohoVideoRenamer/actions"
echo "DMG will be ~80MB now (was ~28MB) because ffmpeg is bundled."
echo "When green (~3-5 min), download fresh DMG from:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/releases/tag/$VERSION"
