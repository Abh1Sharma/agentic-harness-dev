"""The decision contract: the typed questions Jev answers about each request (SPEC §5).

Questions are plain dicts in the API's wire format rather than SDK classes, so that
reviewers can read them without Python, the vendor library stays inside engine.py, and
the exact contract can be hashed for replay recordings and audit entries.

Every question is answered independently and in parallel, so each one must make sense
on its own: none can refer to another question's answer.
"""

from reuse_router.catalog import CATALOG, NONE_ID, Tool
from reuse_router.models import Request

DATA_CLASSES = {
    "public": "Already published outside the bank, e.g. public website content or press releases.",
    "internal": (
        "Non-public business information with low impact if disclosed, e.g. internal wikis, "
        "meeting logistics, source code without secrets, internal policies."
    ),
    "confidential": (
        "Sensitive business information, e.g. strategy, financial forecasts, employee records, "
        "vendor contracts, audit findings."
    ),
    "restricted": (
        "Client personal or account information, credentials, or material non-public information, "
        "e.g. client names with account numbers, government IDs, balances, transactions, credit files."
    ),
}

# The four readiness elements, each paired with the open question the spec asks when it is missing.
READINESS_ELEMENTS = {
    "has_inputs": (
        "Does the request say what data or inputs the tool works from, and where they come from?",
        "What data does the tool read, and where does it come from?",
    ),
    "has_outputs": (
        "Does the request say what the tool should produce, and in what form?",
        "What exactly should the tool produce, and in what format?",
    ),
    "has_users": (
        "Does the request say who will use the tool or who receives its output?",
        "Who uses the tool, and who receives its output?",
    ),
    "has_acceptance": (
        "Does the request include testable acceptance criteria or a measurable definition of success?",
        "How will we know it works? List two or three testable acceptance criteria.",
    ),
}


def build_state(request: Request, catalog: tuple[Tool, ...] = CATALOG) -> dict:
    """The content every question refers to: the request plus the catalog to match against."""
    return {
        "request": request.to_dict(),
        "catalog": [tool.to_dict() for tool in catalog],
    }


def build_questions(catalog: tuple[Tool, ...] = CATALOG) -> dict[str, dict]:
    catalog_criteria = {tool.id: f"{tool.name}: {tool.description}" for tool in catalog}
    catalog_criteria[NONE_ID] = "No tool in the catalog performs the core task of this request."

    questions: dict[str, dict] = {
        "catalog_match": {
            "type": "choice",
            "instructions": (
                "Which tool in the catalog best covers the core task of this request? "
                "Choose 'none' if no catalog tool performs the core task, even if one shares minor features."
            ),
            "criteria": catalog_criteria,
        },
        "reuse_fit": {
            "type": "score",
            "instructions": "How much of this request is already covered by the best-matching tool in the catalog?",
            "criteria": [
                "Not covered: no catalog tool performs the core task.",
                "Partly covered: a tool shares some building blocks, but the core task needs new development.",
                (
                    "Mostly covered: a tool performs the core task, but the request needs an extension "
                    "such as a new input source, language, output format or integration."
                ),
                "Fully covered: a tool already does exactly this; the requester only needs access or onboarding.",
            ],
        },
        "data_class": {
            "type": "choice",
            "instructions": "What is the most sensitive class of data this tool would need to read, store or produce?",
            "criteria": DATA_CLASSES,
        },
        "client_data": {
            "type": "noul",
            "instructions": (
                "Will this tool read, store or produce personal information about the bank's clients, "
                "such as names, contact details, account numbers, balances, transactions or government IDs?"
            ),
        },
        "model_risk": {
            "type": "noul",
            "instructions": (
                "Will this tool produce scores, predictions or recommendations that are used to make decisions "
                "about clients, credit, pricing, fraud, or financial reporting?"
            ),
        },
        "external_transfer": {
            "type": "noul",
            "instructions": (
                "Does the request require sending data to, or relying on, a service outside the bank's approved "
                "internal environment, such as a public SaaS product, a third-party API or a personal account?"
            ),
        },
        "spec_readiness": {
            "type": "score",
            "instructions": (
                "How ready is this request to hand to a coding agent that must build it without asking "
                "any follow-up questions?"
            ),
            "criteria": [
                "A vague idea: the goal or problem is unclear.",
                "The goal is clear, but the inputs, outputs or users are missing.",
                "Goal, inputs, outputs and users are clear, but there are no testable acceptance criteria.",
                "Goal, inputs, outputs, users and testable acceptance criteria are all stated.",
            ],
        },
    }
    for name, (instructions, _open_question) in READINESS_ELEMENTS.items():
        questions[name] = {"type": "noul", "instructions": instructions}
    return questions
