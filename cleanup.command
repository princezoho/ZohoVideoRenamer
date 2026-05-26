#!/usr/bin/env bash
# Removes the one-time bootstrap .command scripts from the project + repo.
# Run once, then delete this file too.

cd "$(dirname "$0")"
set -e

echo "==> Removing bootstrap scripts from git"
for f in push-update.command release.command swap-logo-and-rerelease.command; do
  if [ -f "$f" ]; then
    git rm "$f" 2>/dev/null && echo "  removed $f" || rm -f "$f"
  fi
done

if git diff --cached --quiet; then
  echo "    (nothing to commit)"
else
  git commit -m "Remove one-time bootstrap scripts"
  git push
  echo "  pushed"
fi

echo ""
echo "Done. You can also delete cleanup.command itself now:"
echo "  rm cleanup.command"
