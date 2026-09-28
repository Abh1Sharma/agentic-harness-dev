"""Policy: turns Jev's numbers into a verdict with plain, deterministic code (SPEC §6).

`evaluate` is a pure function of (answers, cutoffs): no network, no files, no randomness.
The same answers always give the same verdict, which is what lets the UI re-run it
instantly when a cutoff slider moves, and what makes each verdict auditable.
"""

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Literal

from reuse_router.catalog import NONE_ID, get_tool
from reuse_router.models import Answers
from reuse_router.questions import DATA_CLASSES, READINESS_ELEMENTS

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "policy.toml"
CLASS_RANK = {name: rank for rank, name in enumerate(DATA_CLASSES)}

Route = Literal["REUSE", "EXTEND", "BUILD"]
Status = Literal["REUSE_EXISTING", "NEEDS_REVIEW", "NEEDS_CLARIFICATION", "READY_TO_BUILD"]
REVIEW_NAMES = {"privacy": "Privacy", "model_risk": "Model risk", "third_party": "Third-party risk"}


@dataclass(frozen=True)
class Policy:
    match_min_confidence: float
    reuse_min_fit: float
    extend_min_fit: float
    review_min_p: float
    ready_min_score: float
    element_min_p: float
    sensitive_classes: tuple[str, ...] = ("confidential", "restricted")
    blocking: tuple[str, ...] = ("model_risk", "third_party")

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Policy":
        config = tomllib.loads(path.read_text())
        return cls(
            match_min_confidence=config["route"]["match_min_confidence"],
            reuse_min_fit=config["route"]["reuse_min_fit"],
            extend_min_fit=config["route"]["extend_min_fit"],
            review_min_p=config["reviews"]["review_min_p"],
            sensitive_classes=tuple(config["reviews"]["sensitive_classes"]),
            blocking=tuple(config["reviews"]["blocking"]),
            ready_min_score=config["readiness"]["ready_min_score"],
            element_min_p=config["readiness"]["element_min_p"],
        )

    def with_overrides(self, overrides: dict | None) -> "Policy":
        """Apply numeric cutoff changes (from the UI sliders); unknown keys are rejected."""
        if not overrides:
            return self
        numeric = {f.name for f in fields(self) if f.type is float}
        unknown = set(overrides) - numeric
        if unknown:
            raise ValueError(f"Unknown cutoffs: {', '.join(sorted(unknown))}")
        return replace(self, **{name: float(value) for name, value in overrides.items()})

    def to_dict(self) -> dict:
        return asdict(self)

    def version(self) -> str:
        """Short hash of the cutoffs, recorded with every decision."""
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()[:12]


@dataclass(frozen=True)
class TraceStep:
    step: str
    outcome: str
    because: str


@dataclass
class Verdict:
    route: Route
    status: Status
    matched_tool: str | None
    data_class: str
    reviews: list[str]
    blocking_reviews: list[str]
    missing_elements: list[str]
    readiness: float
    warnings: list[str] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _cmp(value: float, cutoff: float) -> str:
    return "≥" if value >= cutoff else "<"


def evaluate(answers: Answers, policy: Policy) -> Verdict:
    trace: list[TraceStep] = []
    warnings: list[str] = []

    # --- Route -----------------------------------------------------------------------------
    match, fit = answers["catalog_match"], answers["reuse_fit"]
    confident = match.label != NONE_ID and match.confidence >= policy.match_min_confidence
    if confident and fit.score >= policy.reuse_min_fit:
        route: Route = "REUSE"
    elif confident and fit.score >= policy.extend_min_fit:
        route = "EXTEND"
    else:
        route = "BUILD"

    if match.label == NONE_ID:
        because = f"catalog_match = none (confidence {match.confidence:.2f}): no catalog tool performs the core task"
    elif not confident:
        because = (
            f"closest tool is {match.label}, but confidence {match.confidence:.2f} < "
            f"{policy.match_min_confidence:.2f}, too uncertain to reuse"
        )
        warnings.append("Low-confidence catalog match: ask an architect to confirm build vs reuse.")
    else:
        because = (
            f"catalog_match = {match.label} (confidence {match.confidence:.2f} ≥ {policy.match_min_confidence:.2f}); "
            f"reuse_fit {fit.score:.2f} vs reuse cutoff {policy.reuse_min_fit:.2f}, "
            f"extend cutoff {policy.extend_min_fit:.2f}"
        )
    trace.append(TraceStep("Route", route, because))
    matched_tool = match.label if match.label != NONE_ID else None

    # --- Reviews ---------------------------------------------------------------------------
    data_class = answers["data_class"].label
    client_p = answers["client_data"].p
    reviews: list[str] = []

    privacy = client_p >= policy.review_min_p or data_class in policy.sensitive_classes
    sensitive_note = " (sensitive)" if data_class in policy.sensitive_classes else ""
    trace.append(TraceStep(
        "Privacy review", "required" if privacy else "not required",
        f"client_data {client_p:.2f} {_cmp(client_p, policy.review_min_p)} {policy.review_min_p:.2f}; "
        f"data_class = {data_class}{sensitive_note}",
    ))

    # Reusing a tool is only safe if it is approved for the data this request needs.
    tool = get_tool(matched_tool) if matched_tool else None
    if route != "BUILD" and tool and CLASS_RANK[data_class] > CLASS_RANK[tool.approved_up_to]:
        warnings.append(f"{tool.name} is approved up to {tool.approved_up_to} data; this request needs {data_class}.")
        if not privacy:
            privacy = True
            trace.append(TraceStep(
                "Privacy review", "required",
                f"data_class {data_class} exceeds {tool.id}'s approval ({tool.approved_up_to})",
            ))
    if privacy:
        reviews.append("privacy")

    for review, question in (("model_risk", "model_risk"), ("third_party", "external_transfer")):
        p = answers[question].p
        required = p >= policy.review_min_p
        trace.append(TraceStep(
            f"{REVIEW_NAMES[review]} review", "required" if required else "not required",
            f"{question} {p:.2f} {_cmp(p, policy.review_min_p)} {policy.review_min_p:.2f}",
        ))
        if required:
            reviews.append(review)
    blocking_reviews = [review for review in reviews if review in policy.blocking]

    # --- Readiness -------------------------------------------------------------------------
    readiness = answers["spec_readiness"].score
    missing = [name for name in READINESS_ELEMENTS if answers[name].p < policy.element_min_p]
    ready = readiness >= policy.ready_min_score and not missing
    element_notes = ", ".join(f"{name} {answers[name].p:.2f}" for name in READINESS_ELEMENTS)
    trace.append(TraceStep(
        "Readiness", "ready" if ready else "not ready",
        f"spec_readiness {readiness:.2f} {_cmp(readiness, policy.ready_min_score)} {policy.ready_min_score:.2f}; "
        f"elements (cutoff {policy.element_min_p:.2f}): {element_notes}",
    ))

    # --- Status (first match wins) ---------------------------------------------------------
    if route == "REUSE":
        status: Status = "REUSE_EXISTING"
        because = f"route is REUSE: use {matched_tool} instead of building"
    elif blocking_reviews:
        status = "NEEDS_REVIEW"
        because = "blocking review required: " + ", ".join(REVIEW_NAMES[r] for r in blocking_reviews)
    elif not ready:
        status = "NEEDS_CLARIFICATION"
        because = "request is not specific enough for a coding agent yet"
    else:
        status = "READY_TO_BUILD"
        because = "no blocking reviews and the request is ready"
    trace.append(TraceStep("Status", status, because))

    return Verdict(
        route=route,
        status=status,
        matched_tool=matched_tool,
        data_class=data_class,
        reviews=reviews,
        blocking_reviews=blocking_reviews,
        missing_elements=missing,
        readiness=readiness,
        warnings=warnings,
        trace=trace,
    )
