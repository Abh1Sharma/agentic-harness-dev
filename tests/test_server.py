import pytest
from fastapi.testclient import TestClient

from reuse_router import evaluate, server
from reuse_router.sim import SimEngine

REQUEST = {
    "title": "Credit limit recommender",
    "description": "Build a model that reads a client's credit file and recommends whether to approve a credit limit increase.",
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_engine", SimEngine())
    monkeypatch.setattr(server, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(server, "RESULTS_PATH", tmp_path / "eval_results.json")
    return TestClient(server.app)


def test_index_and_meta(client):
    assert "Reuse Router" in client.get("/").text
    meta = client.get("/api/meta").json()
    assert len(meta["questions"]) == 11
    assert len(meta["examples"]) == len(server.EXAMPLES)
    assert set(meta["cutoff_ranges"]) <= set(meta["policy"])


def test_route_then_reapply_with_a_stricter_cutoff(client):
    routed = client.post("/api/route", json=REQUEST).json()
    assert routed["mode"] == "sim"
    assert routed["verdict"]["status"] == "NEEDS_REVIEW"
    assert client.get("/api/audit").json()[0]["request_id"] == routed["request_id"]

    # Raise the review cutoff above every yes/no answer: no review can fire.
    what_if = client.post("/api/reapply", json={
        "request": REQUEST, "answers": routed["answers"], "model": routed["model"],
        "cutoffs": {"review_min_p": 0.99},
    }).json()
    assert what_if["verdict"]["blocking_reviews"] == []
    assert what_if["policy_version"] != routed["policy_version"]
    assert len(client.get("/api/audit").json()) == 1  # what-ifs are not logged


def test_bad_input_is_rejected(client):
    assert client.post("/api/route", json={"description": "short"}).status_code == 422
    assert client.post("/api/route", json={**REQUEST, "cutoffs": {"bogus": 1}}).status_code == 422


def test_eval_run_then_read(client):
    assert client.get("/api/eval").json() == {"available": False}
    report = client.post("/api/eval/run").json()
    assert report["n"] == len(evaluate.load_eval_set())
    assert client.get("/api/eval").json()["ran_at"] == report["ran_at"]
