#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "Force-pushing main to origin..."
git push -u origin main --force-with-lease
echo ""
echo "Done. Verify at https://github.com/princezoho/ZohoVideoRenamer"
