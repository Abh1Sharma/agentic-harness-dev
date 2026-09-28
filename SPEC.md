# SafeAI Marketplace POC — Spec

A proof of concept for the AI Marketplace, where teams publish AI repos and services
that Pantheon evaluates for SafeAI approval. It adds two things:

- **Discover** (§1–§9): Jev reads a plain-English need and plain code decides whether
  a certified asset can be reused or extended, or something new must be built.
- **SafeAI Passport** (§12): a signed, tamper-evident certificate for each asset. No AI.

**Principle: AI reads, rules decide, people approve, evidence is automatic.**

> **Synthetic data only.** Every request, catalog entry and label in this repo is
> made up. No RBC or client data is used or should be used with this demo.

---

## 1. Problem

A developer who wants a new internal AI tool has to answer a chain of questions
before anyone writes code:

- Does a SafeAI-certified asset in the marketplace already do this (EMMA, Notetaker,
  Docvision, …)? Should we reuse it, extend it, or build new?
- What class of data will it touch? Which reviews does that trigger (privacy,
  model risk, third-party risk)?
- Is the request specific enough to build, or will the builder (a team or a coding
  agent) have to guess?

Today these get answered ad hoc — in meetings, by whoever is available, or by
asking a general-purpose LLM that replies in prose. Prose is slow, costs more,
varies run to run, and is hard to audit or test.

## 2. Goal

Turn each of those questions into a **typed decision** made by Jev, enforce the
consequences in **plain code**, and produce a build brief **only when the request is
ready**. Reusing a certified asset avoids a new build *and* a new certification.

**Non-goals**

- Writing code. The build brief can go to any team or coding agent (e.g. Factory).
- Replacing human review. The router says *which* reviews are needed; people do them.
- Handling real data. See §10.

## 3. User flow

1. A developer pastes a tool request (free text, optionally with a title and team).
2. In under a second the page shows:
   - the route: **reuse**, **extend**, or **build**, and which catalog tool matched;
   - required reviews and the data class;
   - a readiness checklist;
   - the matched asset's SafeAI Passport status, with a link to verify it;
   - either a **build brief** or the **open questions** blocking one.
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
4. Otherwise → **READY_TO_BUILD**.

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

**Build brief** — Markdown built from a fixed template, no text generation:

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
- **Audit log** (`audit.jsonl` in the runtime directory) stores a hash of the request, not its text, plus
  every answer, the cutoffs used and the verdict.
- **Vendor figures** (speed, cost) are not quoted; the demo shows latency and token
  counts measured on each call.

## 11. Open questions for the team

1. Where does the real AI tools catalog live, and who maintains it?
2. What are RBC's actual data classification levels? (§5 uses a generic four-level scheme.)
3. Who owns the cutoffs: engineering, or compliance?
4. How should a build brief reach the builder: a ticket, a repo file, or an API call?
5. Which controls does each review actually require? (The template's controls are placeholders.)
6. What does Pantheon actually check, and in what form are its results? (§12 mocks them.)
7. Who holds the passport signing key, and who may issue or revoke passports?

## 12. SafeAI Passport

A signed certificate for each certified asset, in `reuse_router/passport.py`. No AI, by
design: proof should be plain cryptography a risk team can reason about.

**Contents** (`safeai-passport/v0`): asset id, name, version, owner, repo, the certified
commit, risk tier, the most sensitive data class it's certified for, each Pantheon check
with its suite version, result and an evidence hash, who evaluated and approved it, and
issue and expiry dates (one year).

**Signing.** Ed25519 over canonical JSON (sorted keys, no whitespace). Only the
marketplace holds the private key (`PASSPORT_SIGNING_KEY`); any system with the public
key can verify a passport without calling the marketplace. Signing is deterministic, so
passports are recomputed from the catalog on demand and the POC needs no database.
Without a configured key the app uses a public demo key and labels it on screen.

**Verification**, in order (first failure decides the status):

| Status | Meaning |
|---|---|
| `TAMPERED` | The signature doesn't match the content, or the passport is malformed. Nothing else is checked. |
| `EXPIRED` | Past its expiry date: re-certification required. |
| `SUSPENDED` | The repo has moved past the certified commit: re-certify before reuse. |
| `VALID` | Issued by this marketplace, unaltered, in date, and matching the certified code. |

**Mocked in this POC:** the Pantheon checks and their evidence hashes, the approver, and
the repo head (the demo's "simulate new commit" button stands in for a webhook).

## 13. Deployment and access

- **Local:** `uv run python -m reuse_router.server`, no password.
- **Vercel:** `api/index.py` serves the same app; `vercel.json` routes every path to it.
  Secrets are Vercel environment variables: `TYPESAFE_API_KEY`, `DEMO_PASSWORD`,
  `PASSPORT_SIGNING_KEY`.
- **Password gate:** when `DEMO_PASSWORD` is set, every page and API route requires
  signing in. The cookie holds a token derived from the password, never the password.
- **Runtime files** (audit log, eval results, live recordings) go to `/tmp` on Vercel and
  do not persist between instances. The committed eval set and recordings are read-only.
- **Routes:** `/` intro slides, `/app` the demo, `/login` sign-in.
