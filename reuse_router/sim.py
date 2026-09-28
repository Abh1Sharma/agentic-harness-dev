"""SimEngine: keyword rules standing in for Jev so tests and development run offline.

THIS IS NOT A MODEL. Its numbers are made up by keyword matching and say nothing about
Jev's quality. The UI shows a banner in this mode; never record a demo or quote an eval
from it. It is deliberately simple and is not tuned against the eval set.
"""

import math
import time

from reuse_router.catalog import NONE_ID
from reuse_router.models import Answers, ChoiceAnswer, EngineResult, NoulAnswer, ScoreAnswer

TOOL_KEYWORDS = {
    "emma": ["email", "inbox", "mailbox", "outlook", "reply", "replies"],
    "webex_notes": ["meeting", "webex", "transcript", "minutes"],
    "policy_qa": ["policy", "policies", "procedure", "handbook", "guideline"],
    "code_review": ["pull request", "code review", "repository", "repositories"],
    "translate": ["translat", "french", "bilingual"],
}
EXTEND_CUES = ["extend", "add ", "also ", "integrat", "support for", "connect", "instead of", "slack", "teams chat"]
ONBOARD_CUES = ["access to", "onboard", "set up", "get started", "already"]

DATA_CLASS_KEYWORDS = {
    "restricted": ["client", "customer", "account number", "balance", "transaction", "credit", "sin ", "kyc"],
    "confidential": ["strategy", "forecast", "employee", "salary", "contract", "audit", "vendor"],
    "public": ["press release", "public website", "published"],
}
YES_NO_KEYWORDS = {
    "client_data": DATA_CLASS_KEYWORDS["restricted"],
    "model_risk": ["credit", "fraud", "pricing", "eligib", "underwrit", "risk score", "predict", "approve"],
    "external_transfer": ["chatgpt", "openai", "third-party", "third party", "saas", "gmail", "dropbox", "google"],
    "has_inputs": ["from ", "input", "reads", "using ", "source", "export", "feed"],
    "has_outputs": ["produce", "output", "generate", "report", "summary", "summar", "dashboard", "csv", "draft"],
    "has_users": ["team", "analyst", "manager", "users", "advisor", "developers", "employees", "staff"],
    "has_acceptance": ["acceptance", "success", "must ", "within ", "%", "accuracy", "at least", "under "],
}


def _hits(text: str, keywords: list[str]) -> int:
    return sum(keyword in text for keyword in keywords)


def _softmax(weights: dict[str, float]) -> dict[str, float]:
    exps = {key: math.exp(value) for key, value in weights.items()}
    total = sum(exps.values())
    return {key: value / total for key, value in exps.items()}


def _choice(weights: dict[str, float]) -> ChoiceAnswer:
    probabilities = _softmax(weights)
    label = max(probabilities, key=probabilities.get)
    return ChoiceAnswer(label=label, confidence=probabilities[label], probabilities=probabilities)


def _score(level: int, levels: int = 4) -> ScoreAnswer:
    # 70% on the chosen level, the rest spread over the others.
    probabilities = {i: (0.7 if i == level else 0.3 / (levels - 1)) for i in range(levels)}
    expected = sum(i * p for i, p in probabilities.items())
    return ScoreAnswer(score=expected, confidence=0.7, probabilities=probabilities)


class SimEngine:
    mode = "sim"

    def decide(self, state: dict, questions: dict[str, dict]) -> EngineResult:
        start = time.perf_counter()
        request = state["request"]
        text = f"{request.get('title', '')} {request['description']}".lower() + " "
        tool_ids = [tool["id"] for tool in state["catalog"]]

        tool_hits = {tool_id: _hits(text, TOOL_KEYWORDS.get(tool_id, [])) for tool_id in tool_ids}
        best_hits = max(tool_hits.values(), default=0)
        weights = {tool_id: 1.5 * hits for tool_id, hits in tool_hits.items()}
        weights[NONE_ID] = 1.0 if best_hits else 3.0

        if not best_hits:
            fit = 0
        elif _hits(text, ONBOARD_CUES):
            fit = 3
        elif _hits(text, EXTEND_CUES):
            fit = 2
        else:
            fit = 1

        data_class = next(
            (name for name, keywords in DATA_CLASS_KEYWORDS.items() if _hits(text, keywords)), "internal"
        )
        present = {name: bool(_hits(text, keywords)) for name, keywords in YES_NO_KEYWORDS.items()}
        elements = sum(present[name] for name in ("has_inputs", "has_outputs", "has_users", "has_acceptance"))

        answers: Answers = {
            "catalog_match": _choice(weights),
            "reuse_fit": _score(fit),
            "data_class": _choice({name: (2.0 if name == data_class else 0.0) for name in
                                   ("public", "internal", "confidential", "restricted")}),
            "spec_readiness": _score(min(3, max(0, elements - 1))),
        }
        for name, is_present in present.items():
            answers[name] = NoulAnswer(p=0.85 if is_present else 0.12)

        return EngineResult(
            answers={name: answers[name] for name in questions if name in answers},
            mode=self.mode,
            model="sim-keywords (not a model)",
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
        )
