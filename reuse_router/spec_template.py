"""Fixed template for the build brief (SPEC §7): what a build team or coding agent receives.

Nothing here generates text: every line is either the requester's own words, verbatim,
or a fixed sentence selected by the verdict. The controls are PLACEHOLDERS to be
replaced with RBC's actual policy (SPEC §11.5).
"""

from reuse_router.catalog import get_tool
from reuse_router.models import Request
from reuse_router.policy import REVIEW_NAMES, Verdict
from reuse_router.questions import READINESS_ELEMENTS

STATUS_HEADLINES = {
    "READY_TO_BUILD": "Ready to build: hand to a build team or coding agent",
    "NEEDS_CLARIFICATION": "Not ready: open questions below must be answered first",
    "NEEDS_REVIEW": "Blocked: required review must be completed before build",
    "REUSE_EXISTING": "Reuse a certified asset: no build needed",
}
ROUTE_SENTENCES = {
    "REUSE": "An existing catalog tool already covers this request. Request access and onboard.",
    "EXTEND": "An existing catalog tool covers the core task. Extend it rather than building new.",
    "BUILD": "No catalog tool covers the core task. Build new.",
}
REVIEW_CONTROLS = {
    "privacy": "Use synthetic or masked data in development and tests. Privacy review must approve any use of production data.",
    "model_risk": "Model risk review must approve before build. Outputs must not feed client decisions until the model is validated.",
    "third_party": "Third-party risk review must approve before build. No data may leave approved internal environments.",
}
DATA_CLASS_CONTROLS = {
    "restricted": "Encrypt at rest and in transit, log every access, and never write raw content to application logs.",
    "confidential": "Limit access to named groups and never write raw content to application logs.",
}
ELEMENT_LABELS = {
    "has_inputs": "Inputs and their source",
    "has_outputs": "Outputs and their format",
    "has_users": "Users and recipients",
    "has_acceptance": "Testable acceptance criteria",
}


def _title(request: Request) -> str:
    if request.title.strip():
        return request.title.strip()
    first_line = request.description.strip().splitlines()[0]
    return first_line if len(first_line) <= 70 else first_line[:67].rstrip() + "..."


def render(request: Request, verdict: Verdict, *, model: str, policy_version: str, request_hash: str) -> str:
    tool = get_tool(verdict.matched_tool) if verdict.matched_tool else None
    lines = [
        f"# Build brief: {_title(request)}",
        "",
        f"**Status:** {verdict.status} — {STATUS_HEADLINES[verdict.status]}",
        "",
        "## 1. Problem statement",
        "",
        "_Requester's words, verbatim._",
        "",
        *[f"> {line}" if line.strip() else ">" for line in request.description.strip().splitlines()],
        "",
    ]
    if request.team:
        lines += [f"**Requesting team:** {request.team}", ""]

    lines += ["## 2. Routing decision", "", f"**Route:** {verdict.route}. {ROUTE_SENTENCES[verdict.route]}", ""]
    if tool:
        relation = "Reuse" if verdict.route == "REUSE" else "Extend" if verdict.route == "EXTEND" else "Closest (not reused)"
        lines += [f"**{relation}:** {tool.name} — {tool.description}", ""]

    lines += ["## 3. Data and compliance constraints", "", f"**Data class:** {verdict.data_class}", ""]
    if verdict.reviews:
        lines.append("**Required reviews** _(placeholder controls: replace with RBC policy)_:")
        lines.append("")
        for review in verdict.reviews:
            blocking = " **(blocking)**" if review in verdict.blocking_reviews else ""
            lines.append(f"- {REVIEW_NAMES[review]} review{blocking}: {REVIEW_CONTROLS[review]}")
        lines.append("")
    else:
        lines += ["No reviews triggered.", ""]
    if verdict.data_class in DATA_CLASS_CONTROLS:
        lines += [f"**Handling:** {DATA_CLASS_CONTROLS[verdict.data_class]}", ""]
    for warning in verdict.warnings:
        lines += [f"> ⚠ {warning}", ""]

    lines += ["## 4. Readiness checklist", ""]
    for name in READINESS_ELEMENTS:
        mark = " " if name in verdict.missing_elements else "x"
        lines.append(f"- [{mark}] {ELEMENT_LABELS[name]}")
    lines += ["", f"Readiness score: {verdict.readiness:.1f} / 3", ""]

    if verdict.missing_elements:
        lines += ["## 5. Open questions", "", "_Answer these before anyone builds it._", ""]
        lines += [f"{i}. {READINESS_ELEMENTS[name][1]}" for i, name in enumerate(verdict.missing_elements, 1)]
        lines.append("")

    lines += [
        "## Decision record",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Decision model | `{model}` |",
        f"| Policy version | `{policy_version}` |",
        f"| Request hash | `{request_hash[:16]}` |",
        "",
        "_Generated from a fixed template. No text in this brief was written by a model._",
        "",
    ]
    return "\n".join(lines)
