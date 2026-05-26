#!/usr/bin/env bash
# One-shot script: init the repo, commit everything, push to GitHub.
# Run from this directory:
#   cd ~/Desktop/videos-claude-fix/zoho-video-renamer
#   bash setup-and-push.sh
#
# You can read every step before it runs — nothing is hidden.

set -e  # stop on first error

REMOTE_URL="https://github.com/princezoho/ZohoVideoRenamer.git"

# Sanity check: are we in the right folder?
if [ ! -f "pyproject.toml" ] || ! grep -q "zoho-video-renamer" pyproject.toml; then
  echo "ERROR: pyproject.toml not found or doesn't look like the ZohoVideoRenamer project."
  echo "       cd into the project folder first."
  exit 1
fi

echo "==> 1/7  Cleaning up sandbox-broken .git directory (if any) and macOS junk"
rm -rf .git zoho_video_renamer.egg-info
find . -name ".DS_Store" -delete 2>/dev/null || true

echo "==> 2/7  git init"
git init -b main >/dev/null

echo "==> 3/7  git add ."
git add .
echo "    Files staged:"
git diff --cached --name-only | sed 's/^/      /'

echo "==> 4/7  git commit"
git commit -m "Initial commit: ZohoVideoRenamer v0.1.0

Match videos to source stills via filename substring + stub patterns,
propose descriptive names (from existing still filenames or via AI vision),
review every pairing in a self-contained HTML UI with localStorage,
bulk-rename with full undo log support.

Features:
- Python 3.9+ CLI: scan / ai-name / review / apply / undo
- AI providers: Anthropic Claude, OpenAI GPT-4o (bring your own key)
- Self-contained browser review UI (file:// HTML + localStorage state)
- Automatic v1/v2/v3 numbering for multiple videos per still
- Collision detection, missing-source detection, undo log per run" > /dev/null

echo "==> 5/7  git remote add origin"
git remote add origin "$REMOTE_URL"
git remote -v

echo "==> 6/7  About to push to $REMOTE_URL"
echo "         You may be prompted for GitHub credentials in your browser or terminal."
echo "         Press Ctrl+C now if you want to inspect the commit first (run \`git log\`)."
echo "         Pushing in 3 seconds..."
sleep 3

echo "==> 7/7  git push -u origin main"
# --force because the remote has GitHub-auto-generated files we want to overwrite,
# and we just did `rm -rf .git` so --force-with-lease can't work (no ref knowledge).
git push -u origin main --force

echo ""
echo "Done. Repo pushed to $REMOTE_URL"
echo ""
echo "Once you have verified everything is clean and you're ready for the public,"
echo "go to: https://github.com/princezoho/ZohoVideoRenamer/settings  ->  Danger Zone  ->  Change visibility."
