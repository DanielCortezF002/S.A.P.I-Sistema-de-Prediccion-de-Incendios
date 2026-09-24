"""Manual return to an evidenced pre-refresh absence; no network or refresh.

This is not the ordinary rollback CLI. Preserve versions, pointer snapshots,
history and the removed pointer in quarantine. Consumers must remain stopped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.refresh.atomic import append_jsonl
from src.refresh.dmc_refresh import DmcPaths
from src.refresh.lock import refresh_lock


def return_to_absence(
    paths: DmcPaths,
    *,
    expected_sha256: str,
    initial_current_absent: bool,
    consumers_stopped: bool,
) -> dict:
    """Quarantine exactly the reviewed CURRENT, including a corrupt pointer.

    The two attestations refer to operator evidence, not automatic detection.
    No lock breaking, cleanup, version rewrite or inferred rollback target.
    A crash after the intent is resolved by inspecting CURRENT and quarantine;
    do not blindly rerun or delete history.
    """
    if not initial_current_absent or not consumers_stopped:
        raise ValueError("Require initial-absence evidence and stopped consumers")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("Require the reviewed CURRENT byte SHA-256")
    root = paths.root.resolve()
    if paths.station_dir.resolve().parent != root or paths.pointer.is_symlink():
        raise ValueError("DMC station/pointer must be confined and not a symlink")
    with refresh_lock(paths.lock):
        payload = paths.pointer.read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError("CURRENT changed since review; recovery refused")
        quarantine = paths.station_dir / "recovery"
        if quarantine.is_symlink():
            raise ValueError("Recovery directory must not be a symlink")
        quarantine.mkdir(exist_ok=True)
        destination = quarantine / f"CURRENT-{uuid4().hex}.json"
        record = {
            "event": "return_to_absence_intent",
            "at": datetime.now(timezone.utc).isoformat(),
            "pointer_sha256": expected_sha256,
            "quarantine": str(destination.relative_to(paths.station_dir)),
            "initial_current_absent": True,
            "consumers_stopped": True,
        }
        append_jsonl(paths.history, record)
        paths.pointer.rename(destination)
        record = {**record, "event": "return_to_absence_complete"}
        append_jsonl(paths.history, record)
        return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--initial-current-absent", action="store_true", required=True)
    parser.add_argument("--consumers-stopped", action="store_true", required=True)
    args = parser.parse_args()
    result = return_to_absence(
        DmcPaths(root=args.root),
        expected_sha256=args.expected_sha256,
        initial_current_absent=args.initial_current_absent,
        consumers_stopped=args.consumers_stopped,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
