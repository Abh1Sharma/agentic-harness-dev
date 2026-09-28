"""Evaluate the whole decision system (Jev + policy) against labelled requests (SPEC §9).

    uv run python -m reuse_router.evaluate            # mode from JEV_MODE / key, as the app
    uv run python -m reuse_router.evaluate --mode live

One Jev call per labelled request. The cutoff sweep then re-runs only the policy on the
saved answers, so exploring cutoffs makes no extra Jev calls. In live mode every call is
also recorded, which makes the whole eval set (and the demo examples drawn from it)
replayable offline.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from reuse_router.engine import Engine, make_engine
from reuse_router.models import Request
from reuse_router.pipeline import RouteResult, estimate_cost, route_request
from reuse_router.policy import Policy, evaluate

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EVAL_SET_PATH = DATA_DIR / "eval_set.jsonl"
RESULTS_PATH = DATA_DIR / "eval_results.json"
REVIEWS = ("privacy", "model_risk", "third_party")
SWEEP_CUTOFFS = [round(0.1 * i, 1) for i in range(1, 10)]
RECALL_BAR = 0.9


def load_eval_set(path: Path = EVAL_SET_PATH) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def score(rows: list[dict]) -> dict:
    """Accuracy per decision, plus review recall/precision over (request, review) pairs."""
    n = len(rows)
    tp = fp = fn = 0
    per_review = {}
    for review in REVIEWS:
        r_tp = sum(review in r["predicted"]["reviews"] and review in r["expected"]["reviews"] for r in rows)
        r_fp = sum(review in r["predicted"]["reviews"] and review not in r["expected"]["reviews"] for r in rows)
        r_fn = sum(review not in r["predicted"]["reviews"] and review in r["expected"]["reviews"] for r in rows)
        per_review[review] = {"recall": _ratio(r_tp, r_tp + r_fn), "precision": _ratio(r_tp, r_tp + r_fp),
                              "missed": r_fn, "false_alarms": r_fp}
        tp, fp, fn = tp + r_tp, fp + r_fp, fn + r_fn

    def accuracy(key: str) -> float:
        return sum(r["predicted"][key] == r["expected"][key] for r in rows) / n

    return {
        "route_accuracy": accuracy("route"),
        "status_accuracy": accuracy("status"),
        "data_class_accuracy": accuracy("data_class"),
        "review_recall": _ratio(tp, tp + fn),
        "review_precision": _ratio(tp, tp + fp),
        "reviews_missed": fn,
        "review_false_alarms": fp,
        "per_review": per_review,
    }


def _predicted(verdict) -> dict:
    return {"route": verdict.route, "status": verdict.status, "data_class": verdict.data_class,
            "reviews": sorted(verdict.reviews)}


def sweep(rows: list[dict], results: list[RouteResult], policy: Policy) -> list[dict]:
    """Re-run policy only, at each review cutoff, on answers we already have."""
    points = []
    for cutoff in SWEEP_CUTOFFS:
        trial = policy.with_overrides({"review_min_p": cutoff})
        trial_rows = [
            {**row, "predicted": _predicted(evaluate(result.engine.answers, trial))}
            for row, result in zip(rows, results)
        ]
        metrics = score(trial_rows)
        points.append({"review_min_p": cutoff, **{k: metrics[k] for k in (
            "review_recall", "review_precision", "reviews_missed", "review_false_alarms", "status_accuracy")}})
    return points


def run(engine: Engine, policy: Policy | None = None, eval_set: list[dict] | None = None) -> dict:
    policy = policy or Policy.load()
    items = eval_set if eval_set is not None else load_eval_set()
    rows, results = [], []
    for item in items:
        request = Request(description=item["description"], title=item.get("title", ""), team=item.get("team", ""))
        result = route_request(request, engine, policy, audit_path=None)
        results.append(result)
        rows.append({
            "id": item["id"],
            "title": item.get("title", ""),
            "expected": {**item["expected"], "reviews": sorted(item["expected"]["reviews"])},
            "predicted": _predicted(result.decision.verdict),
            "latency_ms": result.engine.latency_ms,
            "input_tokens": result.engine.input_tokens,
        })

    costs = [estimate_cost(result.engine) for result in results]
    latencies = sorted(row["latency_ms"] for row in rows)
    return {
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": engine.mode,
        "model": results[0].engine.model if results else None,
        "n": len(rows),
        "policy_version": policy.version(),
        "policy": policy.to_dict(),
        "recall_bar": RECALL_BAR,
        "metrics": score(rows),
        "latency_ms": {"median": latencies[len(latencies) // 2], "max": latencies[-1]} if latencies else None,
        "total_cost_usd": sum(costs) if all(c is not None for c in costs) else None,
        "sweep": sweep(rows, results, policy),
        "rows": rows,
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--mode", choices=["live", "replay", "sim"], help="override JEV_MODE")
    args = parser.parse_args()

    report = run(make_engine(args.mode))
    RESULTS_PATH.write_text(json.dumps(report, indent=2))

    metrics = report["metrics"]
    if report["mode"] == "sim":
        print("SIMULATED: keyword rules, not Jev. These numbers say nothing about Jev's quality.\n")
    print(f"{report['n']} requests · mode {report['mode']} · model {report['model']}")
    print(f"  route accuracy       {_pct(metrics['route_accuracy'])}")
    print(f"  status accuracy      {_pct(metrics['status_accuracy'])}")
    print(f"  data class accuracy  {_pct(metrics['data_class_accuracy'])}")
    print(f"  review recall        {_pct(metrics['review_recall'])}  (bar {RECALL_BAR:.0%}, missed {metrics['reviews_missed']})")
    print(f"  review precision     {_pct(metrics['review_precision'])}  (false alarms {metrics['review_false_alarms']})")
    if report["latency_ms"]:
        print(f"  latency              median {report['latency_ms']['median']:.0f} ms, max {report['latency_ms']['max']:.0f} ms")
    if report["total_cost_usd"] is not None:
        print(f"  estimated cost       ${report['total_cost_usd']:.6f} for all {report['n']} calls")
    misses = [row for row in report["rows"] if row["predicted"] != row["expected"]]
    if misses:
        print(f"\n{len(misses)} request(s) with at least one wrong decision:")
        for row in misses:
            wrong = [k for k in row["expected"] if row["predicted"][k] != row["expected"][k]]
            print(f"  {row['id']} {row['title']}: " + "; ".join(
                f"{k} expected {row['expected'][k]} got {row['predicted'][k]}" for k in wrong))
    print(f"\nWrote {RESULTS_PATH.relative_to(DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
