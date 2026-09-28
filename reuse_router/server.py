"""Demo web server. A thin layer: every endpoint delegates to the pipeline or eval.

    uv run python -m reuse_router.server                    # http://127.0.0.1:8000
    uv run --env-file .env python -m reuse_router.server    # with a key in .env
"""

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from reuse_router import audit, evaluate, passport
from reuse_router.catalog import CATALOG
from reuse_router.engine import Engine, EngineError, make_engine, requested_model, resolve_mode
from reuse_router.models import Request, answers_from_dict
from reuse_router.pipeline import decide, route_request
from reuse_router.policy import Policy
from reuse_router.questions import build_questions

STATIC_DIR = Path(__file__).resolve().parent / "static"
AUDIT_PATH = audit.AUDIT_PATH
RESULTS_PATH = evaluate.RESULTS_PATH

# Demo examples come from the eval set, so one live eval run makes all of them replayable.
EXAMPLES = [
    ("e24", "Reuse: invoice extraction"),
    ("e02", "Reuse: meeting notes"),
    ("e05", "Extend: French emails"),
    ("e09", "Blocked: credit model"),
    ("e11", "Blocked: ChatGPT"),
    ("e13", "Too vague"),
]
# Slider ranges for the cutoffs the UI can adjust.
CUTOFF_RANGES = {
    "match_min_confidence": (0.0, 1.0, 0.05),
    "reuse_min_fit": (0.0, 3.0, 0.1),
    "extend_min_fit": (0.0, 3.0, 0.1),
    "review_min_p": (0.0, 1.0, 0.05),
    "ready_min_score": (0.0, 3.0, 0.1),
    "element_min_p": (0.0, 1.0, 0.05),
}

app = FastAPI(title="Reuse Router")
_engine: Engine | None = None


def get_engine() -> Engine:
    """Created on first use, so the page still loads (and explains) if live mode has no key."""
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


@app.exception_handler(EngineError)
def engine_error(_request, error: EngineError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(error)})


class RouteBody(BaseModel):
    description: str = Field(min_length=10, max_length=5000)
    title: str = Field(default="", max_length=200)
    team: str = Field(default="", max_length=200)
    cutoffs: dict[str, float] | None = None


class ReapplyBody(BaseModel):
    request: RouteBody
    answers: dict
    model: str
    cutoffs: dict[str, float] | None = None


def _policy(cutoffs: dict[str, float] | None) -> Policy:
    try:
        return Policy.load().with_overrides(cutoffs)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _request(body: RouteBody) -> Request:
    return Request(description=body.description.strip(), title=body.title.strip(), team=body.team.strip())


@app.get("/")
def intro() -> FileResponse:
    """Slides that set the scene, then hand off to the demo."""
    return FileResponse(STATIC_DIR / "intro.html")


@app.get("/app")
def demo_app() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/meta")
def meta() -> dict:
    policy = Policy.load()
    eval_items = {item["id"]: item for item in evaluate.load_eval_set()}
    return {
        "mode": resolve_mode(),
        "requested_model": requested_model(),
        "policy": policy.to_dict(),
        "policy_version": policy.version(),
        "cutoff_ranges": CUTOFF_RANGES,
        "questions": build_questions(),
        "catalog": [tool.listing() for tool in CATALOG],
        "examples": [
            {"label": label, **{k: eval_items[i][k] for k in ("title", "team", "description")}}
            for i, label in EXAMPLES
        ],
    }


@app.post("/api/route")
def route(body: RouteBody) -> dict:
    return route_request(_request(body), get_engine(), _policy(body.cutoffs), audit_path=AUDIT_PATH).to_dict()


@app.post("/api/reapply")
def reapply(body: ReapplyBody) -> dict:
    """What-if: re-run policy and template on existing answers. No Jev call, not logged."""
    policy = _policy(body.cutoffs)
    decision = decide(_request(body.request), answers_from_dict(body.answers), policy, body.model)
    return {
        "policy": policy.to_dict(),
        "policy_version": policy.version(),
        "verdict": decision.verdict.to_dict(),
        "spec_markdown": decision.spec_markdown,
    }


@app.get("/api/eval")
def eval_results() -> dict:
    if not RESULTS_PATH.exists():
        return {"available": False}
    return {"available": True, **json.loads(RESULTS_PATH.read_text())}


@app.post("/api/eval/run")
def eval_run() -> dict:
    report = evaluate.run(get_engine())
    RESULTS_PATH.write_text(json.dumps(report, indent=2))
    return {"available": True, **report}


class VerifyBody(BaseModel):
    passport: Any
    current_commit: str | None = Field(default=None, max_length=64)


@app.get("/api/passports")
def passports() -> dict:
    """Every listing with its passport and verification against the repo head we know."""
    items = []
    for tool in CATALOG:
        issued = passport.issue(tool)
        items.append({"listing": tool.listing(), "passport": issued,
                      "verification": passport.verify(issued, current_commit=tool.commit)})
    return {"public_key": passport.public_key_info(), "items": items}


@app.post("/api/passports/verify")
def verify_passport(body: VerifyBody) -> dict:
    """Verify any passport JSON, including hand-edited ones from the tamper test."""
    return passport.verify(body.passport, current_commit=body.current_commit)


@app.get("/api/audit")
def audit_log(limit: int = 25) -> list[dict]:
    return audit.recent(limit=min(limit, 200), path=AUDIT_PATH)


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    print(f"Reuse Router on http://127.0.0.1:{port}  (mode: {resolve_mode()})")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
