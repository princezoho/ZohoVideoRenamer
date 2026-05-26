#!/usr/bin/env bash
# Force-push the local main branch to GitHub, overwriting whatever GitHub
# auto-generated (README, LICENSE, .gitignore) when you created the repo.
#
# Uses --force-with-lease, which bails if someone else has pushed to the remote
# since you last fetched — so this is safer than plain --force.
#
# Run this after setup-and-push.command if the initial push was rejected
# because the remote was non-empty.

cd "$(dirname "$0")"
set -e

if [ ! -d .git ]; then
  echo "ERROR: no .git directory. Run setup-and-push.command first."
  exit 1
fi

echo "==> Local commits to push:"
git --no-pager log --oneline -5
echo ""
echo "==> Remote URL:"
git remote -v
echo ""
echo "==> Force-pushing main with --force-with-lease in 3 seconds..."
echo "    (Press Ctrl+C to abort.)"
sleep 3

git push -u origin main --force-with-lease

echo ""
echo "Done. Repo pushed to:"
git remote get-url origin
echo ""
echo "Verify on GitHub. Make repo public when satisfied at:"
echo "  https://github.com/princezoho/ZohoVideoRenamer/settings"
