# Reuse Router

A demo of **Jev** (TypeSafe AI) as a cheap, auditable decision layer in front of
spec-driven development with Factory.

A developer describes an internal AI tool they want. In under a second the router
decides whether to **reuse**, **extend** or **build**, which **reviews** the request
triggers, and whether it's specific enough to hand to a coding agent. If it is, it
writes a Factory handoff spec from a fixed template.

**Jev decides, code enforces, nothing generates.** Jev answers 11 typed questions
in one call and returns numbers only. Plain Python applies the cutoffs and records
why. A fixed template writes the spec. No model writes any text.

> **Synthetic data only.** All requests, catalog entries and labels are made up.
> Do not paste real RBC or client data: no vendor, model risk or data-residency
> review of TypeSafe has been done. See [SPEC.md §10](SPEC.md#10-compliance-and-risk).

Full design: [SPEC.md](SPEC.md) · Recording guide: [docs/LOOM_SCRIPT.md](docs/LOOM_SCRIPT.md)

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env        # then put your key in .env: TYPESAFE_API_KEY=...
uv run --env-file .env python -m reuse_router.server
```

Open <http://127.0.0.1:8000>. The header shows the mode: **Live** means real Jev calls.

Without a key the app runs in **Simulated** mode (keyword rules, clearly bannered),
which is enough to explore the UI but says nothing about Jev.

## Before you demo

```bash
uv run --env-file .env python -m reuse_router.evaluate --mode live
```

This runs all 23 labelled requests through Jev (23 calls, a fraction of a cent),
prints accuracy and review recall, and writes `data/eval_results.json` for the
Evaluation tab. It also **records** every response, so the demo examples work in
replay mode afterwards:

```bash
JEV_MODE=replay uv run python -m reuse_router.server   # no network needed
```

Use replay if the network you record on blocks `api.typesafe.ai`. Replay only serves
requests previously run live with identical text.

## Engine modes

| `JEV_MODE` | What it does | Use for |
|---|---|---|
| `live` | Calls Jev; records each response to `data/recordings/` | Recording the demo, real evals |
| `replay` | Serves recorded responses; refuses anything unseen | Demoing offline |
| `sim` | Keyword rules, **not a model** | Tests and UI development |

Default: `live` if `TYPESAFE_API_KEY` is set, otherwise `sim`. Pin a model version with
`TYPESAFE_DEFAULT_MODEL=jev-1.13`.

## Layout

| Path | What it is |
|---|---|
| `SPEC.md` | The design: problem, decision contract, policy, eval plan, risks |
| `reuse_router/questions.py` | The decision contract: the 11 typed questions Jev answers |
| `reuse_router/catalog.py` | The AI tools catalog (illustrative: replace with the real one) |
| `config/policy.toml` | Policy cutoffs, as data. Change these, not code, to tune decisions |
| `reuse_router/policy.py` | Pure function: answers + cutoffs → verdict + trace |
| `reuse_router/spec_template.py` | Fixed Factory handoff template |
| `reuse_router/engine.py` | The only module that imports the TypeSafe SDK |
| `reuse_router/sim.py` | Offline stand-in for tests (not a model) |
| `reuse_router/pipeline.py` | Wires request → Jev → policy → template → audit log |
| `reuse_router/evaluate.py` | Scores the system against `data/eval_set.jsonl`; cutoff sweep |
| `reuse_router/server.py`, `static/index.html` | Demo server and page (no build step, no CDN) |

## Tests

```bash
uv run pytest
```

Tests run fully offline. They include a check that the decision contract is accepted
by the API's own request schema, and a record → replay round trip through the live
engine with a fake client.

## Adapting it

1. **Catalog**: replace the entries in `reuse_router/catalog.py` with the real tools.
2. **Labels**: review `data/eval_set.jsonl`. The labels encode policy judgments
   (e.g. "client-service email is restricted data"), so the owners of that policy
   should agree with them.
3. **Controls**: replace the placeholder controls in `reuse_router/spec_template.py`
   with the actual requirements of each review.
4. **Cutoffs**: run the eval live, read the sweep chart, set `config/policy.toml`.

## Security

- The API key is read from the `TYPESAFE_API_KEY` environment variable only. `.env` is
  git-ignored. Never commit a key or paste one into chat or tickets.
- The audit log (`data/audit.jsonl`, git-ignored) stores a hash of each request, not
  its text.
- Recordings in `data/recordings/` contain the request text and Jev's answers. They are
  safe to commit only because the data is synthetic.
