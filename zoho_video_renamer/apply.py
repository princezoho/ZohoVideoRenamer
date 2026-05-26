"""Execute a rename plan with collision detection and undo logging."""
from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class RenameOp:
    src: str  # absolute path
    dst: str  # absolute path
    kind: str  # 'video' | 'still'
    note: str = ""


@dataclass
class PlanResult:
    ops: list[RenameOp]
    collisions: dict[str, list[RenameOp]]  # dst -> list of ops writing to it
    missing_sources: list[RenameOp]


def build_plan(approvals: dict, project_root: str) -> PlanResult:
    """Convert an approvals JSON (as exported by the review UI) into RenameOp objects.

    approvals['approved'] is a list of entries; each entry has 'renames':
        [{type, from, to, skip?}, ...]
    'from' and 'to' are paths relative to project_root (or absolute).
    """
    ops: list[RenameOp] = []
    for entry in approvals.get("approved", []):
        for r in entry.get("renames", []):
            if r.get("skip"):
                continue
            src = r["from"]
            dst = r["to"]
            if not os.path.isabs(src):
                src = os.path.join(project_root, src)
            if not os.path.isabs(dst):
                dst = os.path.join(project_root, dst)
            ops.append(RenameOp(src=src, dst=dst, kind=r.get("type", "?"),
                                note=entry.get("name", "")))

    # Detect collisions: multiple sources targeting same dst
    by_dst: dict[str, list[RenameOp]] = {}
    for o in ops:
        by_dst.setdefault(o.dst, []).append(o)
    collisions = {d: lst for d, lst in by_dst.items() if len(lst) > 1}

    missing = [o for o in ops if not os.path.exists(o.src)]

    return PlanResult(ops=ops, collisions=collisions, missing_sources=missing)


def execute_plan(plan: PlanResult, undo_log_dir: str, operation: str = "rename") -> tuple[int, int, str]:
    """Apply the plan with the given operation.

    operation: 'rename' (default, in-place os.rename), 'copy' (shutil.copy2 —
    originals preserved), or 'move' (shutil.move — works across filesystems).

    For 'copy', the undo log only allows deleting the new copies (we record
    the destination paths). For 'move' and 'rename', the undo log reverses
    the move.

    Returns (succeeded, failed, undo_log_path).
    """
    import shutil
    os.makedirs(undo_log_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    undo_path = os.path.join(undo_log_dir, f"rename-undo-{ts}.json")

    if operation not in ("rename", "copy", "move"):
        raise ValueError(f"Unknown operation {operation!r}; use rename / copy / move")

    completed: list[dict] = []
    ok = 0
    failed = 0
    try:
        for op in plan.ops:
            try:
                os.makedirs(os.path.dirname(op.dst), exist_ok=True)
                if operation == "rename":
                    os.rename(op.src, op.dst)
                elif operation == "move":
                    shutil.move(op.src, op.dst)
                elif operation == "copy":
                    shutil.copy2(op.src, op.dst)
                # Record reversed (dst -> src) so undo can re-apply easily.
                # For 'copy' we record the dest path with operation='copy' so
                # undo knows it should delete the copy rather than move it back.
                completed.append({
                    "from": op.dst, "to": op.src,
                    "kind": op.kind, "note": op.note,
                    "operation": operation,
                })
                ok += 1
            except OSError as e:
                failed += 1
                completed.append({
                    "from": op.src, "to": op.dst, "kind": op.kind,
                    "error": str(e), "note": op.note, "operation": operation,
                })
    finally:
        with open(undo_path, "w") as f:
            json.dump({
                "created_at": ts,
                "operation": operation,
                "renames": [c for c in completed if "error" not in c],
                "failures": [c for c in completed if "error" in c],
                "note": ("To undo: rename/move each entry's 'from' back to 'to'. For 'copy' "
                         "operations the originals were preserved, so undo deletes the copies."),
            }, f, indent=2)

    return ok, failed, undo_path
