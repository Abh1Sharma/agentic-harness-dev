"""Append-only audit log of every decision (SPEC §10).

Stores a hash of the request rather than its text, so the log never becomes a second
copy of whatever a requester pasted in. Slider what-ifs are not logged: they are not
decisions.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from reuse_router.paths import runtime_dir

AUDIT_PATH = runtime_dir() / "audit.jsonl"


def append(entry: dict, path: Path = AUDIT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamped = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    with path.open("a") as log:
        log.write(json.dumps(stamped) + "\n")


def recent(limit: int = 20, path: Path = AUDIT_PATH) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text().splitlines()[-limit:]
    return [json.loads(line) for line in reversed(lines)]
