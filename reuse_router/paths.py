"""Where the app reads committed inputs and writes runtime files.

Serverless hosts such as Vercel only allow writes under /tmp, and those files vanish
between instances, so runtime files (audit log, eval results, live recordings) go there
when running on Vercel. Committed inputs (eval set, recordings for replay) stay put.
"""

import os
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_DIR / "data"


def runtime_dir() -> Path:
    configured = os.environ.get("RUNTIME_DIR", "").strip()
    if configured:
        return Path(configured)
    if os.environ.get("VERCEL"):
        return Path("/tmp/reuse-router")
    return DATA_DIR
