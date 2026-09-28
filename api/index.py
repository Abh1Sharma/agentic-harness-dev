"""Vercel entry point: Vercel serves the ASGI `app` found here.

All routes are rewritten to this function (see vercel.json). Secrets come from Vercel
environment variables: TYPESAFE_API_KEY, DEMO_PASSWORD, PASSPORT_SIGNING_KEY.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reuse_router.server import app  # noqa: E402,F401
