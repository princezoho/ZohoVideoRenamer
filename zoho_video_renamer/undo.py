"""Reverse a previous rename run using its undo log."""
from __future__ import annotations

import json
import os
from typing import Tuple


def undo(undo_log_path: str, execute: bool = False) -> Tuple[int, int, list[str]]:
    """Reverse renames recorded in `undo_log_path`.

    Returns (succeeded, failed, missing_sources).
    """
    with open(undo_log_path) as f:
        data = json.load(f)
    items = data.get("renames", [])

    missing = []
    ok = 0
    failed = 0
    for i in items:
        if not os.path.exists(i["from"]):
            missing.append(i["from"])
            continue
        if not execute:
            continue
        try:
            os.makedirs(os.path.dirname(i["to"]), exist_ok=True)
            os.rename(i["from"], i["to"])
            ok += 1
        except OSError:
            failed += 1
    return ok, failed, missing
