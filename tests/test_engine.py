from types import SimpleNamespace

import pytest
from typesafe_sdk import ChoiceAnswer, NoulAnswer, ScoreAnswer, TypeSafeAPIConnectionError

from reuse_router.engine import EngineError, LiveEngine, ReplayEngine, resolve_mode
from reuse_router.models import Request
from reuse_router.questions import build_questions, build_state
from reuse_router.sim import SimEngine

STATE = build_state(Request(description="Summarize my inbox every morning."))
QUESTIONS = {
    "client_data": {"type": "noul", "instructions": "Client data?"},
    "catalog_match": {"type": "choice", "criteria": {"emma": None, "none": None}},
    "reuse_fit": {"type": "score", "criteria": ["no", "some", "most", "all"]},
}


def sdk_response() -> SimpleNamespace:
    """A response shaped like SystemOneResponse, built from the SDK's real answer types."""
    return SimpleNamespace(
        model="jev-1.13",
        usage=SimpleNamespace(input_tokens=812, output_tokens=40),
        answers={
            "client_data": NoulAnswer.model_validate({"type": "noul", "noul": 0.08}),
            "catalog_match": ChoiceAnswer.model_validate(
                {"type": "choice", "choice": "emma", "confidence": 0.93,
                 "probabilities": {"emma": 0.93, "none": 0.07}}
            ),
            # Parsed from JSON, as the SDK does with real responses: its strict score model only
            # coerces the string keys of a JSON object into integer levels.
            "reuse_fit": ScoreAnswer.model_validate_json(
                '{"type": "score", "score": 2.9, "confidence": 0.9,'
                ' "legend": {"0": "no", "1": "some", "2": "most", "3": "all"},'
                ' "probabilities": {"0": 0.0, "1": 0.02, "2": 0.06, "3": 0.92}}'
            ),
        },
    )


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response, self.error = response, error

    def system_one(self, state, questions):
        if self.error:
            raise self.error
        return self.response


def test_live_converts_sdk_answers_and_replay_returns_the_same(tmp_path):
    live = LiveEngine(recordings_dir=tmp_path, client=FakeClient(sdk_response())).decide(STATE, QUESTIONS)

    assert live.answers["client_data"].p == 0.08
    assert live.answers["catalog_match"].label == "emma"
    assert live.answers["reuse_fit"].probabilities[3] == 0.92
    assert live.input_tokens == 812

    replayed = ReplayEngine(recordings_dir=tmp_path).decide(STATE, QUESTIONS)
    assert replayed.answers == live.answers
    assert replayed.mode == "replay"
    assert replayed.model == "jev-1.13"


def test_replay_refuses_unseen_request(tmp_path):
    with pytest.raises(EngineError, match="No recording"):
        ReplayEngine(recordings_dir=tmp_path).decide(STATE, QUESTIONS)


def test_live_reports_missing_answers(tmp_path):
    response = sdk_response()
    del response.answers["reuse_fit"]
    with pytest.raises(EngineError, match="reuse_fit"):
        LiveEngine(recordings_dir=tmp_path, client=FakeClient(response)).decide(STATE, QUESTIONS)


def test_live_wraps_sdk_errors_with_next_step(tmp_path):
    client = FakeClient(error=TypeSafeAPIConnectionError("connection refused"))
    with pytest.raises(EngineError, match="JEV_MODE=replay"):
        LiveEngine(recordings_dir=tmp_path, client=client).decide(STATE, QUESTIONS)


def test_sim_answers_every_question_in_the_contract():
    questions = build_questions()
    result = SimEngine().decide(STATE, questions)
    assert set(result.answers) == set(questions)
    assert result.answers["catalog_match"].label == "emma"


@pytest.mark.parametrize(
    ("env", "expected"),
    [({}, "sim"), ({"TYPESAFE_API_KEY": "k"}, "live"), ({"TYPESAFE_API_KEY": "k", "JEV_MODE": "replay"}, "replay")],
)
def test_resolve_mode_defaults(monkeypatch, env, expected):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_MODE", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert resolve_mode() == expected


def test_real_sdk_client_end_to_end_over_a_mock_network(tmp_path):
    """The real TypeSafeClient, with only the network faked: checks the request we send and
    that a response in the API's shape flows through the whole pipeline, then replays."""
    import json

    import httpx2
    from typesafe_sdk import RetryPolicy, TypeSafeClient

    from reuse_router.pipeline import route_request
    from tests.helpers import POLICY

    sent = {}

    def api(request):
        sent["path"], sent["body"] = request.url.path, json.loads(request.content)
        answers = {}
        for name, question in sent["body"]["questions"].items():
            if question["type"] == "noul":
                answers[name] = {"type": "noul", "noul": 0.9 if name.startswith("has_") else 0.05}
            elif question["type"] == "choice":
                labels = list(question["criteria"])
                top = "webex_notes" if name == "catalog_match" else "internal"
                answers[name] = {"type": "choice", "choice": top, "confidence": 0.9,
                                 "probabilities": {label: 0.9 if label == top else 0.1 / (len(labels) - 1) for label in labels}}
            else:
                levels = {str(i): (0.9 if i == 3 else 0.1 / 3) for i in range(4)}
                answers[name] = {"type": "score", "score": 2.8, "confidence": 0.9,
                                 "legend": dict(zip(levels, question["criteria"])), "probabilities": levels}
        return httpx2.Response(200, json={"model": "jev-1.13", "usage": {"input_tokens": 900, "output_tokens": 30},
                                          "answers": answers})

    client = TypeSafeClient(api_key="apikey_test", retry=RetryPolicy(max_retries=0),
                            http_client=httpx2.Client(transport=httpx2.MockTransport(api)))
    request = Request(title="Sprint notes", description="Summarize our WebEx sprint planning meetings.")
    result = route_request(request, LiveEngine(recordings_dir=tmp_path, client=client), POLICY, audit_path=None)

    assert sent["path"] == "/v1/systemone"
    assert len(sent["body"]["questions"]) == 11
    assert result.decision.verdict.status == "REUSE_EXISTING"
    assert result.engine.model == "jev-1.13"

    replayed = route_request(request, ReplayEngine(recordings_dir=tmp_path), POLICY, audit_path=None)
    assert replayed.engine.answers == result.engine.answers
