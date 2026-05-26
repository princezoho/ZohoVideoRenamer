#!/usr/bin/env bash
# Push the landing-page update + UI/CLI bugfixes found while testing v0.1.8
cd "$(dirname "$0")"
set -e

git add -A
if git diff --cached --quiet; then
  echo "(nothing to commit)"
else
  git commit -m "Landing: add 'Two modes' section + Catalog mode screenshots

Documents the new videos-only catalog mode released in v0.1.8.

- New 'Two modes' section to docs/index.html with side-by-side cards
  explaining Match mode (stills+videos) vs Catalog mode (videos only)
- Catalog mode screenshot from a real videos-only scan run
- 'Three ways to apply the renames' explainer for rename/copy/move
- Fix ui.py JS syntax error (apostrophe in raw Python string broke
  the videos-only review UI render — JS choked on \\' inside a
  single-quoted string)
- Fix cli.py scan: re-save matches.json after videos-only 3-frame
  extraction so still_thumb / _video_frames persist for ai-name
  and regen-html"
fi
git push

echo ""
echo "Pages will redeploy in ~30 seconds. Site:"
echo "  https://princezoho.github.io/ZohoVideoRenamer/#modes"
