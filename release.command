#!/usr/bin/env bash
# Commits any pending changes, pushes, then tags v0.1.0 and pushes the tag.
# Pushing a v* tag triggers .github/workflows/build.yml which produces the
# macOS .dmg and Windows .exe and attaches them to a GitHub Release.

cd "$(dirname "$0")"
set -e

VERSION="v0.1.0"

echo "==> Commit any pending changes"
git add .
if git diff --cached --quiet; then
  echo "    (nothing to commit)"
else
  git commit -m "Add logo, wire it into landing + README + app icons"
fi

echo ""
echo "==> Push to main"
git push

echo ""
echo "==> Tag $VERSION"
if git rev-parse "$VERSION" >/dev/null 2>&1; then
  echo "    Tag $VERSION already exists — deleting and recreating"
  git tag -d "$VERSION"
  git push --delete origin "$VERSION" 2>/dev/null || true
fi
git tag -a "$VERSION" -m "Release $VERSION

First public release of ZohoVideoRenamer.

CLI + GUI + landing page + macOS .dmg + Windows .exe.
See README and https://princezoho.github.io/ZohoVideoRenamer/ for usage."

echo ""
echo "==> Push tag (triggers build workflow)"
git push origin "$VERSION"

echo ""
echo "Done. Watch the binary build at:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/actions"
echo ""
echo "When the workflow finishes (~5-10 minutes), the .dmg and .exe will be"
echo "attached to the release at:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/releases/tag/$VERSION"
echo ""
echo "Now:"
echo "  1. Settings -> Pages -> Source: GitHub Actions (one-time)"
echo "  2. Settings -> General -> Danger Zone -> Change visibility to public"
echo "     (only AFTER you have verified the build succeeded and the repo is clean)"
