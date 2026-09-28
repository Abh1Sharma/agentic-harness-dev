from reuse_router.evaluate import SWEEP_CUTOFFS, load_eval_set, run, score
from reuse_router.sim import SimEngine
from tests.helpers import POLICY


def row(expected_reviews, predicted_reviews, status=("READY_FOR_FACTORY", "READY_FOR_FACTORY")):
    base = {"route": "BUILD", "data_class": "internal"}
    return {
        "expected": {**base, "status": status[0], "reviews": expected_reviews},
        "predicted": {**base, "status": status[1], "reviews": predicted_reviews},
    }


def test_review_recall_and_precision_count_request_review_pairs():
    metrics = score([
        row(["privacy", "model_risk"], ["privacy"]),                 # 1 hit, 1 miss
        row([], ["third_party"], ("NEEDS_REVIEW", "NEEDS_REVIEW")),  # 1 false alarm
        row(["privacy"], ["privacy"]),                                # 1 hit
    ])
    assert metrics["review_recall"] == 2 / 3
    assert metrics["review_precision"] == 2 / 3
    assert metrics["reviews_missed"] == 1
    assert metrics["per_review"]["model_risk"]["recall"] == 0
    assert metrics["per_review"]["third_party"]["recall"] is None  # never expected


def test_eval_set_labels_use_known_values():
    for item in load_eval_set():
        expected = item["expected"]
        assert expected["route"] in {"REUSE", "EXTEND", "BUILD"}
        assert expected["status"] in {"REUSE_EXISTING", "NEEDS_REVIEW", "NEEDS_CLARIFICATION", "READY_FOR_FACTORY"}
        assert expected["data_class"] in {"public", "internal", "confidential", "restricted"}
        assert set(expected["reviews"]) <= {"privacy", "model_risk", "third_party"}


def test_run_reports_metrics_and_a_full_sweep():
    report = run(SimEngine(), POLICY, eval_set=load_eval_set()[:3])
    assert report["n"] == 3
    assert report["mode"] == "sim"
    assert [point["review_min_p"] for point in report["sweep"]] == SWEEP_CUTOFFS
