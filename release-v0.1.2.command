#!/usr/bin/env bash
# Push v0.1.2: build for both Intel and Apple Silicon Macs.
cd "$(dirname "$0")"
set -e
VERSION="v0.1.2"

git add -A
if git diff --cached --quiet; then
  echo "(nothing to commit)"
else
  git commit -m "v0.1.2: build for both Intel and Apple Silicon Macs

- build.yml matrix expanded: macos-13 (Intel) + macos-14 (Apple Silicon)
  produces two .dmg files (ZohoVideoRenamer-Intel.dmg and ZohoVideoRenamer-AppleSilicon.dmg)
- build.yml now prints architecture in CI log + smoke-runs the binary
- Landing page: two download cards (Apple Silicon and Intel) pointing to
  /releases/latest/download/... so users pick the right one
- Most likely cause of insta-crash on v0.1.0/v0.1.1: arm64 binary on Intel Mac"
fi
git push

git tag -d "$VERSION" 2>/dev/null || true
git push --delete origin "$VERSION" 2>/dev/null || true
sleep 1
git tag -a "$VERSION" -m "Release $VERSION — dual-architecture macOS builds"
git push origin "$VERSION"

echo ""
echo "Done. Build at https://github.com/princezoho/ZohoVideoRenamer/actions"
echo "Will produce ZohoVideoRenamer-Intel.dmg + ZohoVideoRenamer-AppleSilicon.dmg"
