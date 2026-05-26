#!/usr/bin/env bash
# Adds all new files (landing page, GUI, workflows), commits, and pushes.
# Safe to re-run — does normal git push, no force.

cd "$(dirname "$0")"
set -e

# Remove bootstrap scripts so they don't get committed
rm -f setup-and-push.command setup-and-push.sh force-push.command just-push.command 2>/dev/null

echo "==> git add ."
git add .
echo ""
echo "==> Files about to commit:"
git --no-pager diff --cached --name-only

echo ""
echo "==> git commit"
git commit -m "Add landing page, GUI wrapper, and CI build workflows

- docs/index.html: full landing page (GitHub Pages-ready)
- docs/screenshots/: 5 real screenshots of the review UI + landing hero
- zoho_video_renamer/gui.py: native tkinter desktop GUI
- pyproject.toml: register zoho-video-renamer-gui entry point
- .github/workflows/pages.yml: auto-deploy landing on push
- .github/workflows/build.yml: build .dmg (macOS) + .exe (Windows) on tag
- README.md: link to landing + downloads, GUI quickstart

The desktop binaries get built and attached to GitHub Releases when you push
a version tag (e.g. \`git tag v0.1.0 && git push --tags\`)."

echo ""
echo "==> git push"
git push

echo ""
echo "Done. Next:"
echo "  1. Verify the new files on github.com/princezoho/ZohoVideoRenamer"
echo "  2. Enable GitHub Pages: Settings → Pages → Source → GitHub Actions"
echo "     (The pages.yml workflow will deploy automatically next push.)"
echo "  3. For the first binary release:"
echo "     git tag v0.1.0 && git push --tags"
echo "     The build.yml workflow will produce the .dmg and .exe and attach them"
echo "     to a new GitHub Release."
