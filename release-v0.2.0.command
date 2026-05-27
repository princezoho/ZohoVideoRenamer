#!/usr/bin/env bash
cd "$(dirname "$0")"
set -e
VERSION="v0.2.0"

git add -A
if git diff --cached --quiet; then echo "(nothing to commit)"
else git commit -m "v0.2.0: single-window pywebview app — fully encapsulated

User feedback: 'why can't you have the browser inside the app and not
actually have to go to an external browser. Make it completely encapsulated.'

Replaces the tkinter+browser split with a single native webview window
(macOS WKWebView, Windows WebView2, Linux GTK). The whole flow — folder
pickers, API key entry, scan progress, review, approve, rename — lives
in one window. No external browser, no file export, no app switching,
no Terminal.

- pyproject: pywebview>=5.0 dependency
- new embedded.py: Api class exposed to JS via window.pywebview.api.{...}
- new FORM_HTML for the setup screen
- launcher.py: now starts embedded.main()
- ui.py: review HTML detects window.pywebview and rewires the Export
  button to call api.apply_renames() directly. Falls back to JSON
  download in regular browsers.
- 'Back to setup' button when running inside the app
- build.yml: --collect-all webview + --collect-submodules webview"
fi
git push

git tag -d "$VERSION" 2>/dev/null || true
git push --delete origin "$VERSION" 2>/dev/null || true
sleep 1
git tag -a "$VERSION" -m "Release $VERSION — single-window pywebview app"
git push origin "$VERSION"

echo ""
echo "Build at https://github.com/princezoho/ZohoVideoRenamer/actions"
echo "When green (~5-7 min), download fresh DMG from:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/releases/tag/$VERSION"
