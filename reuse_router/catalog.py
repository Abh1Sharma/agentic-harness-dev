"""The AI Marketplace: SafeAI-certified assets that Discover matches requests against.

ILLUSTRATIVE ONLY: names come from the real portfolio, but every description, owner,
repo, commit, tier and check below is a placeholder. Replace with the marketplace's
real listings (SPEC §11.1). Repos use a fake internal host on purpose.
"""

from dataclasses import asdict, dataclass

NONE_ID = "none"

# Pantheon's checks are mocked: names and suite versions are placeholders (SPEC §12).
BASE_CHECKS = ("licence", "secrets", "dependencies", "tests", "eval_evidence")
GENAI_CHECKS = ("prompt_injection",)
SENSITIVE_DATA_CHECKS = ("pii_leakage",)


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    description: str
    # Most sensitive data class the asset is certified to process.
    approved_up_to: str
    # Certification metadata, used to issue the asset's SafeAI Passport.
    risk_tier: str = "low"
    owner: str = ""
    version: str = "1.0.0"
    repo: str = ""
    commit: str = ""
    certified_on: str = "2026-06-01"
    checks: tuple[str, ...] = BASE_CHECKS

    def to_dict(self) -> dict:
        """What Jev sees about each asset: only what helps match a request."""
        return {"id": self.id, "name": self.name, "description": self.description,
                "approved_up_to": self.approved_up_to}

    def listing(self) -> dict:
        return asdict(self)


CATALOG: tuple[Tool, ...] = (
    Tool(
        id="emma",
        name="EMMA (email analysis)",
        description=(
            "Summarizes email threads in the user's own mailbox, extracts action items and "
            "deadlines, classifies the sender's intent, and drafts suggested replies for the "
            "user to edit before sending. English only."
        ),
        approved_up_to="confidential",
        risk_tier="medium",
        owner="AI Tools · Productivity",
        version="2.3.0",
        repo="git.example.internal/ai-marketplace/emma",
        commit="4f2c9e17d0a3b58e61c2f94a7d3e0b1c5a8f6d20",
        certified_on="2026-06-02",
        checks=BASE_CHECKS + GENAI_CHECKS + SENSITIVE_DATA_CHECKS,
    ),
    Tool(
        id="webex_notes",
        name="Notetaker (WebEx)",
        description=(
            "Transcribes WebEx meetings and produces a summary, the decisions made, and action "
            "items with owners, then posts the notes to the meeting's space. English only."
        ),
        approved_up_to="confidential",
        risk_tier="medium",
        owner="AI Tools · Productivity",
        version="1.8.1",
        repo="git.example.internal/ai-marketplace/notetaker",
        commit="9b1e6a0c3d7f42e8a5b90c1d6e2f7a3b8c4d5e61",
        certified_on="2026-05-14",
        checks=BASE_CHECKS + GENAI_CHECKS + SENSITIVE_DATA_CHECKS,
    ),
    Tool(
        id="docvision",
        name="Docvision (document extraction)",
        description=(
            "Extracts text, tables and key fields from scanned documents and PDFs, such as forms, "
            "invoices and statements, into structured data with a confidence score per field."
        ),
        approved_up_to="confidential",
        risk_tier="medium",
        owner="AI Tools · Document Intelligence",
        version="3.1.0",
        repo="git.example.internal/ai-marketplace/docvision",
        commit="c7d2a9e4b1f063857a2e9d4c0b6f1a3e7d5c8b92",
        certified_on="2026-07-21",
        checks=BASE_CHECKS + SENSITIVE_DATA_CHECKS,
    ),
    Tool(
        id="policy_qa",
        name="Policy Q&A",
        description=(
            "Answers employees' questions about internal policies and procedures from an indexed "
            "document library, with citations to the source section."
        ),
        approved_up_to="internal",
        owner="AI Tools · Knowledge",
        version="1.2.4",
        repo="git.example.internal/ai-marketplace/policy-qa",
        commit="1a8f3c6e9d2b47a05e8c1f3d6a9b2e4c7f0a3d58",
        certified_on="2026-04-08",
        checks=BASE_CHECKS + GENAI_CHECKS,
    ),
    Tool(
        id="code_review",
        name="Code Review Assistant",
        description=(
            "Reviews pull requests in internal repositories, flags likely bugs, security issues "
            "and style problems, and suggests fixes as review comments."
        ),
        approved_up_to="internal",
        owner="Developer Platform",
        version="0.9.3",
        repo="git.example.internal/ai-marketplace/code-review",
        commit="e3b7d1a5c9f24e680b3d7a1c5e9f2b6d0a4c8e17",
        certified_on="2026-08-30",
        checks=BASE_CHECKS + GENAI_CHECKS,
    ),
    Tool(
        id="translate",
        name="Translation Service",
        description="Translates internal documents and messages between English and French.",
        approved_up_to="confidential",
        owner="AI Tools · Language",
        version="2.0.0",
        repo="git.example.internal/ai-marketplace/translate",
        commit="5d9a2f7c1e4b38d06a9f2c5e8b1d4a7f0c3e6b29",
        certified_on="2026-03-19",
        checks=BASE_CHECKS + SENSITIVE_DATA_CHECKS,
    ),
)


def get_tool(tool_id: str) -> Tool | None:
    return next((tool for tool in CATALOG if tool.id == tool_id), None)
