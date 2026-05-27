#!/usr/bin/env bash
cd "$(dirname "$0")"
set -e

git add -A
if git diff --cached --quiet; then echo "(nothing to commit)"
else git commit -m "Landing + README: rewrite for v0.2.0 single-window flow

The old copy described a multi-step browser → JSON-export → CLI flow
that v0.2.0 no longer requires. Updates:

- Hero badge: 'One Window' added
- Hero subhead: rewritten around the new one-window flow
- 'How it works' four steps rewritten:
  ① Open app, pick folders
  ② AI proposes names
  ③ Review in the same window (was: 'review in a browser')
  ④ Click 'Approve & Rename All' (was: 'export approvals, run apply')
- CLI section reframed as 'for power users / scripts & CI' rather
  than the recommended flow
- Meta description updated
- FAQ: new 'Do I have to leave the app to use it?' entry, updated
  Linux entry (pywebview supports GTK), updated undo + overwrite
  entries to reflect the in-app experience
- README: new desktop-app quickstart as the primary, CLI demoted"
fi
git push

echo ""
echo "Pages will redeploy in ~30 seconds:"
echo "  https://princezoho.github.io/ZohoVideoRenamer/"
