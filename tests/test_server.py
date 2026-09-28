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
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    monkeypatch.setattr(server, "_engine", SimEngine())
    monkeypatch.setattr(server, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(server, "RESULTS_PATH", tmp_path / "eval_results.json")
    return TestClient(server.app)


def test_index_and_meta(client):
    assert "Start the demo" in client.get("/").text
    assert "SafeAI Marketplace" in client.get("/app").text
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


def test_passports_list_all_assets_as_valid(client):
    data = client.get("/api/passports").json()
    assert len(data["items"]) == len(server.CATALOG)
    assert {item["verification"]["status"] for item in data["items"]} == {"VALID"}
    assert data["public_key"]["algorithm"] == "Ed25519"


def test_verify_detects_tampering_and_new_commits(client):
    item = client.get("/api/passports").json()["items"][0]
    edited = {**item["passport"], "payload": {**item["passport"]["payload"], "risk_tier": "low"}}
    assert client.post("/api/passports/verify", json={"passport": edited}).json()["status"] == "TAMPERED"
    moved = client.post("/api/passports/verify", json={"passport": item["passport"], "current_commit": "f" * 40})
    assert moved.json()["status"] == "SUSPENDED"
    assert client.post("/api/passports/verify", json={"passport": "not json"}).json()["status"] == "TAMPERED"


def test_password_gate(client, monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "open-sesame")
    page = client.get("/app", follow_redirects=False)
    assert page.status_code == 303 and page.headers["location"] == "/login?next=/app"
    assert client.get("/api/meta").status_code == 401
    assert client.get("/login").status_code == 200

    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    ok = client.post("/api/login", json={"password": "open-sesame"})
    assert ok.status_code == 200
    assert "open-sesame" not in ok.headers["set-cookie"]  # cookie holds a derived token only
    assert client.get("/api/meta").status_code == 200  # TestClient keeps the cookie


def test_runtime_files_move_to_tmp_on_vercel(monkeypatch):
    from reuse_router.paths import DATA_DIR, runtime_dir

    monkeypatch.delenv("RUNTIME_DIR", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    assert runtime_dir() == DATA_DIR
    monkeypatch.setenv("VERCEL", "1")
    assert str(runtime_dir()).startswith("/tmp/")
