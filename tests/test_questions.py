"""The decision contract must be accepted by the API's own request schema.

This validates offline against the SDK's generated wire models, so a malformed
question fails here instead of on a live call.
"""

from typesafe_sdk._schemas.models import SystemOneRequest

from reuse_router.catalog import CATALOG, NONE_ID
from reuse_router.models import Request
from reuse_router.questions import READINESS_ELEMENTS, build_questions, build_state


def test_contract_matches_api_schema():
    request = SystemOneRequest.model_validate(
        {
            "state": build_state(Request(description="Summarize my emails.")),
            "model": "jev-latest",
            "questions": build_questions(),
        }
    )
    assert len(request.questions) == 11


def test_catalog_match_offers_every_tool_and_none():
    criteria = build_questions()["catalog_match"]["criteria"]
    assert set(criteria) == {tool.id for tool in CATALOG} | {NONE_ID}


def test_every_readiness_element_is_asked():
    questions = build_questions()
    assert all(questions[name]["type"] == "noul" for name in READINESS_ELEMENTS)
