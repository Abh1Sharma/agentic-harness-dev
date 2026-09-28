"""The internal AI tools catalog the router matches requests against.

ILLUSTRATIVE ONLY: these entries are placeholders written from short descriptions,
not the real tools' documentation. Replace them with the real catalog (SPEC §11.1).
"""

from dataclasses import asdict, dataclass

NONE_ID = "none"


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    description: str
    # Most sensitive data class the tool is approved to process.
    approved_up_to: str

    def to_dict(self) -> dict:
        return asdict(self)


CATALOG: tuple[Tool, ...] = (
    Tool(
        id="emma",
        name="Emma (email analysis)",
        description=(
            "Summarizes email threads in the user's own mailbox, extracts action items and "
            "deadlines, classifies the sender's intent, and drafts suggested replies for the "
            "user to edit before sending. English only."
        ),
        approved_up_to="confidential",
    ),
    Tool(
        id="webex_notes",
        name="WebEx Note Taker",
        description=(
            "Transcribes WebEx meetings and produces a summary, the decisions made, and action "
            "items with owners, then posts the notes to the meeting's space. English only."
        ),
        approved_up_to="confidential",
    ),
    Tool(
        id="policy_qa",
        name="Policy Q&A",
        description=(
            "Answers employees' questions about internal policies and procedures from an indexed "
            "document library, with citations to the source section."
        ),
        approved_up_to="internal",
    ),
    Tool(
        id="code_review",
        name="Code Review Assistant",
        description=(
            "Reviews pull requests in internal repositories, flags likely bugs, security issues "
            "and style problems, and suggests fixes as review comments."
        ),
        approved_up_to="internal",
    ),
    Tool(
        id="translate",
        name="Translation Service",
        description="Translates internal documents and messages between English and French.",
        approved_up_to="confidential",
    ),
)


def get_tool(tool_id: str) -> Tool | None:
    return next((tool for tool in CATALOG if tool.id == tool_id), None)
