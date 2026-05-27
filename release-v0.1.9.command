#!/usr/bin/env bash
cd "$(dirname "$0")"
set -e
VERSION="v0.1.9"

git add -A
if git diff --cached --quiet; then echo "(nothing to commit)"
else git commit -m "v0.1.9: end-to-end rename in the GUI — no CLI required

User feedback (verbatim): 'these are not technical people. they just
want to open up the app, rename all the files with the AI, and then
hit a button. it just goes in and renames the files and organizes them.
that was the whole point. not forcing them to do a multi-step process
and leave an application and then go into a fucking terminal.'

Adds a third action button to the GUI: '③ Apply Renames'. End-to-end
flow now lives entirely inside the app:
  ① Scan + Open Review  →  user reviews in browser, clicks Export
  ② Open last review    (re-open if they closed the tab)
  ③ Apply Renames       (this is new — actually renames the files)

The Apply button:
- Auto-finds rename-approvals.json in the project folder or ~/Downloads
- Falls back to a file picker if not found
- Resolves project-relative paths back to absolute file paths
- Detects collisions and missing sources before any move
- Shows a preview dialog with the first 20 planned renames
- Respects the 'Apply operation' dropdown (rename / copy / move)
- Executes on a background thread with an undo log
- Reports success/failure via modal + log area

Also adds a labeled hint string next to the action buttons explaining
the three-step flow for non-technical users."
fi
git push

git tag -d "$VERSION" 2>/dev/null || true
git push --delete origin "$VERSION" 2>/dev/null || true
sleep 1
git tag -a "$VERSION" -m "Release $VERSION — end-to-end rename in GUI"
git push origin "$VERSION"

echo ""
echo "Build at https://github.com/princezoho/ZohoVideoRenamer/actions"
echo "When green (~5 min), download fresh DMG from:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/releases/tag/$VERSION"
