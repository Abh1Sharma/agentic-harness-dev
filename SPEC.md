# Reuse Router — Spec

A demo of Jev (TypeSafe AI) as a cheap, auditable **decision layer** in front of
spec-driven development with Factory.

> **Synthetic data only.** Every request, catalog entry and label in this repo is
> made up. No RBC or client data is used or should be used with this demo.

---

## 1. Problem

A developer who wants a new internal AI tool has to answer a chain of questions
before anyone writes code:

- Does something in the AI tools catalog already do this (Emma, the WebEx note
  taker, …)? Should we reuse it, extend it, or build new?
- What class of data will it touch? Which reviews does that trigger (privacy,
  model risk, third-party risk)?
- Is the request specific enough to hand to a coding agent like Factory, or will
  the agent guess?

Today these get answered ad hoc — in meetings, by whoever is available, or by
asking a general-purpose LLM that replies in prose. Prose is slow, costs more,
varies run to run, and is hard to audit or test.

## 2. Goal

Turn each of those questions into a **typed decision** made by Jev, enforce the
consequences in **plain code**, and hand a spec to Factory **only when the
request is ready**.

**Non-goals**

- Writing code. That stays Factory's job.
- Replacing human review. The router says *which* reviews are needed; people do them.
- Handling real data. See §10.

## 3. User flow

1. A developer pastes a tool request (free text, optionally with a title and team).
2. In under a second the page shows:
   - the route: **reuse**, **extend**, or **build**, and which catalog tool matched;
   - required reviews and the data class;
   - a readiness checklist;
   - either a **Factory handoff spec** or the **open questions** blocking one.
3. A reviewer can drag the policy cutoffs and watch the verdict change instantly,
   without calling Jev again.

## 4. Architecture

```
            ┌──────────────────────────────┐
request ──► │ Jev: 11 typed questions,     │ ──► answers (numbers only)
            │ one call, answered in        │          │
            │ parallel                     │          ▼
            └──────────────────────────────┘   ┌──────────────┐
                        config/policy.toml ──► │ Policy       │ ──► verdict + trace
                          (cutoffs = data)     │ (plain code) │          │
                                               └──────────────┘          ▼
                                                               ┌──────────────────┐
                                                               │ Fixed template   │ ──► handoff spec
                                                               └──────────────────┘
                                                        every decision ──► audit log
```

**Design principles, and why**

| # | Principle | Why |
|---|---|---|
| 1 | **Jev decides, code enforces, nothing generates.** | Each step is testable on its own. No free text is produced, so nothing can be made up. |
| 2 | **One Jev call per request.** | All 11 questions go in one request and are answered in parallel, so latency and cost stay flat as questions are added. |
| 3 | **Cutoffs are data, not prompts.** | Compliance can tune a cutoff in a config file and see the effect immediately. No re-prompting, no retraining. |
| 4 | **Every verdict carries its trace.** | "Privacy review: client-data probability 0.91 ≥ cutoff 0.50." An auditor can check each step. |
| 5 | **The vendor library is isolated in one file** (`engine.py`). | Jev is weeks old. If the library changes or we switch vendors, policy, template and UI don't change. |
| 6 | **Offline first.** | Tests and development run with no network (sim mode); a recorded demo can replay without the internet (replay mode). |

## 5. Decision contract

The questions Jev answers. They live as plain data in `reuse_router/questions.py`
so a non-developer can read and review them.

**State sent to Jev:** the request (title, description, team) plus the catalog.

| Name | Type | Question (short form) | Drives |
|---|---|---|---|
| `catalog_match` | Choice | Which catalog tool best covers the core need? (or `none`) | route |
| `reuse_fit` | Score 0–3 | How much of the request does the best-matching tool already cover? | route |
| `data_class` | Choice | Most sensitive data class: public / internal / confidential / restricted | privacy review |
| `client_data` | Yes/no | Will it touch personal information about clients? | privacy review |
| `model_risk` | Yes/no | Will its scores or recommendations be used in decisions about clients, credit, pricing, fraud or financial reporting? | model risk review |
| `external_transfer` | Yes/no | Does it need a service outside the approved internal environment? | third-party review |
| `spec_readiness` | Score 0–3 | How ready is this for a coding agent to build without follow-up questions? | handoff gate |
| `has_inputs` | Yes/no | Are the inputs and their source stated? | open questions |
| `has_outputs` | Yes/no | Is the output and its format stated? | open questions |
| `has_users` | Yes/no | Is it clear who uses it? | open questions |
| `has_acceptance` | Yes/no | Are there testable acceptance criteria? | open questions |

What Jev returns per type:

- **Yes/no** (`noul`): probability of yes, 0–1.
- **Choice**: chosen label, its confidence, and a probability for every label.
- **Score**: expected score (probability-weighted, can fall between levels), confidence,
  and a probability per level.

## 6. Policy

Plain Python in `reuse_router/policy.py`; cutoffs in `config/policy.toml`.
Rules run in this order:

**Route**

1. If `catalog_match` is not `none` **and** its confidence ≥ `match_min_confidence`:
   - `reuse_fit` ≥ `reuse_min_fit` → **REUSE**
   - `reuse_fit` ≥ `extend_min_fit` → **EXTEND**
2. Otherwise → **BUILD**.

**Reviews**

| Review | Triggered when | Blocks handoff? |
|---|---|---|
| Privacy | `client_data` ≥ cutoff **or** `data_class` ∈ {confidential, restricted} **or** the route reuses/extends a tool not approved for that data class | No — becomes a constraint in the spec |
| Model risk | `model_risk` ≥ cutoff | Yes |
| Third-party risk | `external_transfer` ≥ cutoff | Yes |

**Status** (first match wins)

1. Route is REUSE → **REUSE_EXISTING** (point to the tool; no build needed).
2. Any blocking review → **NEEDS_REVIEW**.
3. `spec_readiness` < `ready_min_score` or any `has_*` below cutoff → **NEEDS_CLARIFICATION**
   (with one open question per missing element).
4. Otherwise → **READY_FOR_FACTORY**.

Starting cutoffs (to be tuned with the eval in §9):

| Cutoff | Value |
|---|---|
| `match_min_confidence` | 0.55 |
| `reuse_min_fit` | 2.5 |
| `extend_min_fit` | 1.5 |
| `review_min_p` (all three reviews) | 0.50 |
| `ready_min_score` | 2.0 |
| `element_min_p` | 0.50 |

## 7. Outputs

**Verdict** — route, matched tool, status, reviews, data class, open questions,
warnings (e.g. low-confidence match), and the trace of every rule that fired.

**Factory handoff spec** — Markdown built from a fixed template, no text generation:

1. Problem statement (the request, verbatim)
2. Routing decision (route, matched tool, reuse fit)
3. Data and compliance constraints (data class, reviews, required controls)
4. Readiness checklist
5. Open questions (if any)
6. Decision record (model, cutoffs used, request hash) for traceability

## 8. Engine modes

| Mode | What it does | When |
|---|---|---|
| `live` | Calls Jev through the TypeSafe library. Saves each response to `data/recordings/`. | Recording the Loom; running the real eval. |
| `replay` | Serves saved responses. Fails loudly on a request it hasn't seen. | Demoing where the network blocks TypeSafe. |
| `sim` | Keyword rules. **Not a model**; the page shows a banner saying so. | Tests and offline development only. Never demo in this mode. |

Mode is set by `JEV_MODE`. Default: `live` if `TYPESAFE_API_KEY` is set, otherwise `sim`.

## 9. Evaluation

- `data/eval_set.jsonl`: labelled synthetic requests covering every route and status,
  sensitive and non-sensitive data, and vague and complete requests.
- Metrics: route accuracy, status accuracy, data-class accuracy, and **review
  recall and precision**. Recall is reported separately because missing a required
  review is worse than a false alarm.
- **Cutoff sweep**: re-run the policy (not Jev) on the saved answers at review
  cutoffs from 0.1 to 0.9 and plot recall vs precision. Compliance picks the
  operating point; changing it costs nothing.
- Acceptance bar for the demo, to confirm after the first live run: review recall ≥ 0.9.

## 10. Compliance and risk

- **Synthetic data only.** TypeSafe is a US vendor whose model is weeks old; no
  vendor risk, model risk (OSFI E-23) or data-residency review has been done.
- **Secrets**: the API key is read from the `TYPESAFE_API_KEY` environment variable only;
  `.env` is git-ignored.
- **Audit log** (`data/audit.jsonl`) stores a hash of the request, not its text, plus
  every answer, the cutoffs used and the verdict.
- **Vendor figures** (speed, cost) are not quoted; the demo shows latency and token
  counts measured on each call.

## 11. Open questions for the team

1. Where does the real AI tools catalog live, and who maintains it?
2. What are RBC's actual data classification levels? (§5 uses a generic four-level scheme.)
3. Who owns the cutoffs: engineering, or compliance?
4. How should a handoff reach Factory: a file in the repo, a ticket, or an API call?
5. Which controls does each review actually require? (The template's controls are placeholders.)
