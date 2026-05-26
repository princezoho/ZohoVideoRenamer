#!/usr/bin/env bash
# Finds the installed ZohoVideoRenamer.app, runs it from a terminal so we
# capture stderr instead of the app crashing silently in the GUI launcher,
# saves the output to a log file, and opens it in TextEdit.

LOG="$HOME/Desktop/zvr-crash-log.txt"

echo "Searching for ZohoVideoRenamer.app..."
APP=""
for candidate in \
  "/Applications/ZohoVideoRenamer.app" \
  "$HOME/Applications/ZohoVideoRenamer.app" \
  "$HOME/Downloads/ZohoVideoRenamer.app" \
  "/Volumes/ZohoVideoRenamer/ZohoVideoRenamer.app"; do
  if [ -d "$candidate" ]; then
    APP="$candidate"
    echo "Found: $APP"
    break
  fi
done

if [ -z "$APP" ]; then
  echo "ERROR: Couldn't find ZohoVideoRenamer.app. Searching home dir (this may take a few seconds)..."
  APP=$(mdfind -name "ZohoVideoRenamer.app" 2>/dev/null | head -1)
fi

if [ -z "$APP" ] || [ ! -d "$APP" ]; then
  echo "Still couldn't find ZohoVideoRenamer.app on this Mac." | tee "$LOG"
  echo "Drag it into /Applications first, then re-run this script." | tee -a "$LOG"
  open -a TextEdit "$LOG"
  exit 1
fi

EXE="$APP/Contents/MacOS/ZohoVideoRenamer"

{
  echo "============================================================"
  echo "ZohoVideoRenamer crash diagnostic"
  echo "Date: $(date)"
  echo "Mac: $(sw_vers -productName) $(sw_vers -productVersion) ($(uname -m))"
  echo "App path: $APP"
  echo "Binary file info:"
  file "$EXE"
  echo "Binary architectures:"
  lipo -archs "$EXE" 2>/dev/null || echo "  (lipo couldn't read it)"
  echo "Quarantine attr:"
  xattr -l "$APP" 2>/dev/null | head -5 || echo "  (none)"
  echo "============================================================"
  echo "Launching the binary directly. Any output below is the actual error:"
  echo "------------------------------------------------------------"
  "$EXE" 2>&1
  echo "------------------------------------------------------------"
  echo "Exit code: $?"
} | tee "$LOG"

echo ""
echo "Saved to: $LOG"
echo "Opening in TextEdit..."
open -a TextEdit "$LOG"
