#!/usr/bin/env bash
# Push v0.1.3: fix the actual crash (ImportError: relative import) via
# launcher.py wrapper.
cd "$(dirname "$0")"
set -e
VERSION="v0.1.3"

git add -A
if git diff --cached --quiet; then
  echo "(nothing to commit)"
else
  git commit -m "v0.1.3: fix relative-import crash with launcher.py wrapper

Root cause (from user's diagnose-crash.command output):
  ImportError: attempted relative import with no known parent package
  at gui.py line 22 (\`from . import __version__\`)

PyInstaller's entry point must be a top-level script, so gui.py's
relative imports failed when run as the bundled binary's __main__.

Fix:
- launcher.py at project root: \`from zoho_video_renamer.gui import main; main()\`
- build.yml: PyInstaller entry point changed from zoho_video_renamer/gui.py
  to launcher.py (now uses package context, relative imports resolve)
- --collect-submodules zoho_video_renamer to ensure all package modules
  are bundled even if not directly imported by the launcher"
fi
git push

git tag -d "$VERSION" 2>/dev/null || true
git push --delete origin "$VERSION" 2>/dev/null || true
sleep 1
git tag -a "$VERSION" -m "Release $VERSION — fix relative-import crash"
git push origin "$VERSION"

echo ""
echo "Done. Watch at https://github.com/princezoho/ZohoVideoRenamer/actions"
echo "When green (~5 min), the fixed DMGs will replace the broken ones at"
echo "  https://github.com/princezoho/ZohoVideoRenamer/releases/tag/$VERSION"
