import json

from reuse_router.models import NoulAnswer, Request
from reuse_router.pipeline import decide, route_request
from reuse_router.sim import SimEngine
from tests.helpers import POLICY, make_answers

REQUEST = Request(title="Inbox digest", description="Summarize my email inbox\n\nevery morning.", team="Ops")


def test_spec_quotes_the_request_verbatim_and_says_no_model_wrote_it():
    spec = decide(REQUEST, make_answers(), POLICY, model="jev-test").spec_markdown
    assert "> Summarize my email inbox\n>\n> every morning." in spec
    assert "No text in this spec was written by a model" in spec
    assert "READY_FOR_FACTORY" in spec


def test_spec_lists_open_questions_for_missing_elements():
    answers = make_answers(has_acceptance=NoulAnswer(0.1))
    spec = decide(REQUEST, answers, POLICY, model="jev-test").spec_markdown
    assert "## 5. Open questions" in spec
    assert "testable acceptance criteria" in spec


def test_route_request_logs_a_hash_not_the_text(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    result = route_request(REQUEST, SimEngine(), POLICY, audit_path=audit_path)

    entry = json.loads(audit_path.read_text())
    assert entry["request_id"] == result.request_id
    assert entry["status"] == result.decision.verdict.status
    assert "Summarize" not in audit_path.read_text()
    assert len(entry["request_sha256"]) == 64


def test_route_request_can_skip_audit(tmp_path):
    route_request(REQUEST, SimEngine(), POLICY, audit_path=None)
    assert not list(tmp_path.iterdir())
