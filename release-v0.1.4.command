#!/usr/bin/env bash
# v0.1.4: drop slow Intel macOS build so releases actually ship.
cd "$(dirname "$0")"
set -e
VERSION="v0.1.4"

# Cancel any in-flight Intel build for v0.1.3 to free the runner queue
echo "==> (optional) Cancel any in-flight v0.1.3 Intel build via GitHub UI"
echo "    https://github.com/princezoho/ZohoVideoRenamer/actions"

git add -A
if git diff --cached --quiet; then
  echo "(nothing to commit)"
else
  git commit -m "v0.1.4: drop slow Intel macOS build to unblock releases

The Intel macos-13 runner queue on GitHub Actions free tier was holding
v0.1.3 hostage — Apple Silicon and Windows builds were done in <3 min but
the release job couldn't fire because it needed all matrix entries.

This release drops macos-13 from the build matrix entirely (Apple Silicon
covers 95%+ of Macs sold since 2020). Intel users can still install via
pip from source. Re-add Intel build via PR if there's demand.

Landing page also simplified to one macOS download card."
fi
git push

git tag -d "$VERSION" 2>/dev/null || true
git push --delete origin "$VERSION" 2>/dev/null || true
sleep 1
git tag -a "$VERSION" -m "Release $VERSION — drop Intel build"
git push origin "$VERSION"

echo ""
echo "Done. Build should complete in ~3 min (Apple Silicon + Windows only)."
echo "Watch at https://github.com/princezoho/ZohoVideoRenamer/actions"
