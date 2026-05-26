#!/usr/bin/env bash
# Double-clickable launcher — opens in Terminal automatically on macOS.
# This is just a thin wrapper around setup-and-push.sh that cd's to the
# right folder first.

cd "$(dirname "$0")"
exec bash setup-and-push.sh
