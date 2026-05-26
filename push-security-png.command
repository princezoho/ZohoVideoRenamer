#!/usr/bin/env bash
# Push the real macOS security screenshot into the landing page.
cd "$(dirname "$0")"
set -e

git add docs/assets/macos-security-allow.png docs/assets/macos-security-allow-small.png docs/index.html
if git diff --cached --quiet; then
  echo "(nothing to commit)"
else
  git commit -m "Add real macOS Privacy & Security screenshot to Gatekeeper bypass instructions"
fi
git push
echo ""
echo "Done. Landing page will redeploy in ~30 seconds via GitHub Pages workflow."
