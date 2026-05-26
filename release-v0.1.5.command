#!/usr/bin/env bash
cd "$(dirname "$0")"
set -e
VERSION="v0.1.5"

git add -A
if git diff --cached --quiet; then echo "(nothing to commit)"
else git commit -m "v0.1.5: fix unreadable buttons on macOS

tk.Button on macOS ignores bg/fg (native AppKit rendering), so the
custom orange Scan button and gray Browse/Open buttons rendered as
unstyled light-gray chrome with white text — unreadable.

Fix: new FlatButton widget = tk.Frame + tk.Label with click bindings.
Bypasses native button rendering entirely; bg/fg colors apply correctly.
Hover state included (auto-lightens bg by 12%).

Replaced all 3 tk.Button instances: Scan, Open last review, Browse…
Also patched the configure(state=disabled) call to use the new
FlatButton.configure_state() API."
fi
git push

git tag -d "$VERSION" 2>/dev/null || true
git push --delete origin "$VERSION" 2>/dev/null || true
sleep 1
git tag -a "$VERSION" -m "Release $VERSION — readable buttons on macOS"
git push origin "$VERSION"

echo ""
echo "Build at https://github.com/princezoho/ZohoVideoRenamer/actions"
echo "When green (~3 min), download the new DMG from:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/releases/tag/$VERSION"
