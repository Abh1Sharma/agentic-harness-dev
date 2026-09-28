"""Orchestration: request → Jev → policy → template → audit log.

The only place the steps are wired together. Each step is testable on its own, and
`reapply` re-runs policy and template on answers we already have, without calling Jev.
"""

import hashlib
import json
import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path

from reuse_router import audit, spec_template
from reuse_router.engine import Engine
from reuse_router.models import Answers, EngineResult, Request, answers_to_dict
from reuse_router.policy import CONFIG_PATH, Policy, Verdict, evaluate
from reuse_router.questions import build_questions, build_state


def request_hash(request: Request) -> str:
    return hashlib.sha256(json.dumps(request.to_dict(), sort_keys=True).encode()).hexdigest()


def estimate_cost(result: EngineResult, config_path: Path = CONFIG_PATH) -> float | None:
    if result.input_tokens is None:
        return None
    pricing = tomllib.loads(config_path.read_text())["pricing"]
    return (
        result.input_tokens * pricing["input_per_million"]
        + (result.output_tokens or 0) * pricing["output_per_million"]
    ) / 1_000_000


@dataclass
class Decision:
    verdict: Verdict
    spec_markdown: str


def decide(request: Request, answers: Answers, policy: Policy, model: str) -> Decision:
    """Policy + template only. Pure: safe to call on every slider move."""
    verdict = evaluate(answers, policy)
    spec = spec_template.render(
        request, verdict, model=model, policy_version=policy.version(), request_hash=request_hash(request)
    )
    return Decision(verdict, spec)


@dataclass
class RouteResult:
    request_id: str
    request: Request
    engine: EngineResult
    policy: Policy
    decision: Decision

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "request": self.request.to_dict(),
            "mode": self.engine.mode,
            "model": self.engine.model,
            "latency_ms": self.engine.latency_ms,
            "input_tokens": self.engine.input_tokens,
            "output_tokens": self.engine.output_tokens,
            "cost_usd": estimate_cost(self.engine),
            "answers": answers_to_dict(self.engine.answers),
            "policy": self.policy.to_dict(),
            "policy_version": self.policy.version(),
            "verdict": self.decision.verdict.to_dict(),
            "spec_markdown": self.decision.spec_markdown,
        }


def route_request(
    request: Request,
    engine: Engine,
    policy: Policy | None = None,
    audit_path: Path | None = audit.AUDIT_PATH,
) -> RouteResult:
    """Full pipeline. Pass audit_path=None to skip logging (tests, eval runs)."""
    policy = policy or Policy.load()
    result = engine.decide(build_state(request), build_questions())
    decision = decide(request, result.answers, policy, result.model)
    routed = RouteResult(str(uuid.uuid4()), request, result, policy, decision)

    if audit_path is not None:
        verdict = decision.verdict
        audit.append(
            {
                "request_id": routed.request_id,
                "request_sha256": request_hash(request),
                "mode": result.mode,
                "model": result.model,
                "latency_ms": result.latency_ms,
                "input_tokens": result.input_tokens,
                "policy_version": policy.version(),
                "policy": policy.to_dict(),
                "answers": answers_to_dict(result.answers),
                "route": verdict.route,
                "status": verdict.status,
                "reviews": verdict.reviews,
            },
            path=audit_path,
        )
    return routed
