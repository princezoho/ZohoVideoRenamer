#!/usr/bin/env bash
# Push the v0.1.1 fixes (tkinter collection + security instructions) and tag.

cd "$(dirname "$0")"
set -e

VERSION="v0.1.1"

echo "==> git add ."
git add -A

echo ""
echo "==> Files to commit:"
git --no-pager diff --cached --name-only

echo ""
echo "==> git commit"
if git diff --cached --quiet; then
  echo "    (nothing to commit)"
else
  git commit -m "v0.1.1: fix macOS crash (collect tkinter), add Gatekeeper bypass docs

- build.yml: --collect-all tkinter + explicit hidden-imports for tkinter.ttk,
  tkinter.filedialog, tkinter.messagebox, _tkinter (the usual cause of
  'app crashes immediately' for tkinter GUIs bundled with PyInstaller on macOS)
- build.yml: strip com.apple.quarantine attr from the .app inside the .dmg
- build.yml: set --osx-bundle-identifier so Gatekeeper has a stable ID to remember
- build.yml: smoke-run the bundled binary headlessly during CI to catch import errors
- docs/index.html: new 'first launch security warning' section with click-by-click
  bypass for both macOS Gatekeeper and Windows SmartScreen
- pyproject.toml + __init__.py: bump to 0.1.1"
fi

echo ""
echo "==> git push"
git push

echo ""
echo "==> Tag $VERSION"
git tag -d "$VERSION" 2>/dev/null || true
git push --delete origin "$VERSION" 2>/dev/null || true
sleep 1
git tag -a "$VERSION" -m "Release $VERSION

- Fixed macOS app crash (missing tkinter resources in PyInstaller bundle)
- Added security-bypass instructions to landing page
- Stripped quarantine attr from packaged .app"
git push origin "$VERSION"

echo ""
echo "Done. Build re-running at:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/actions"
echo "When it finishes, the fixed .dmg + .exe will land at:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/releases/tag/$VERSION"
