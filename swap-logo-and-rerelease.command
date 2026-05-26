#!/usr/bin/env bash
# Replaces the placeholder SVG with the real logo, commits, pushes, and
# re-tags v0.1.0 so the build workflow re-runs with the correct app icon.

cd "$(dirname "$0")"
set -e

# Remove the placeholder SVG (sandbox couldn't delete it)
rm -f docs/logo.svg

echo "==> git status"
git status --short

echo ""
echo "==> git add ."
git add -A docs/assets docs/index.html docs/logo.svg README.md .github 2>/dev/null || git add -A

echo ""
echo "==> git commit"
if git diff --cached --quiet; then
  echo "    (nothing to commit)"
else
  git commit -m "Use real logo (from logo-run.png), remove placeholder SVG"
fi

echo ""
echo "==> git push"
git push

echo ""
echo "==> Re-tag v0.1.0 (delete old, push new)"
git tag -d v0.1.0 2>/dev/null || true
git push --delete origin v0.1.0 2>/dev/null || true
sleep 1
git tag -a v0.1.0 -m "Release v0.1.0 (with real logo)

CLI + GUI + landing page + macOS .dmg + Windows .exe.
App icon uses the actual ZohoVideoRenamer logo.
See README and https://princezoho.github.io/ZohoVideoRenamer/ for usage."
git push origin v0.1.0

echo ""
echo "Done. Build re-running at:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/actions"
echo "When it finishes, the .dmg + .exe will land at:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/releases/tag/v0.1.0"
