# Loom script: Reuse Router (~5 minutes)

Audience: senior director. Goal: show that Jev makes the decisions before a build
**cheap, fast and auditable**, and that it fits alongside Factory rather than replacing it.

## Before you record

- [ ] Header shows **Live · jev-latest**, not Simulated. Never record in sim mode.
- [ ] Run the live eval first: `uv run --env-file .env python -m reuse_router.evaluate --mode live`.
      Fill in the numbers table below from its output. **Use your numbers, not guesses.**
- [ ] Run each example chip once and check the outcome. If Jev routes an example
      differently from what the script expects, either adjust the script to what it
      actually does, or pick another example. Don't hide a miss; the eval tab shows them anyway.
- [ ] Clear the audit log for a tidy Audit tab: `rm data/audit.jsonl`.
- [ ] Browser zoom 110–125%, light mode, other tabs closed. Have SPEC.md open in a second tab.
- [ ] If the recording network blocks `api.typesafe.ai`: record the eval live elsewhere,
      then run with `JEV_MODE=replay` and say "replaying recorded Jev responses" on camera.

**Your numbers (from the live eval):**

| Metric | Value |
|---|---|
| Review recall (bar 90%) | ___ |
| Review precision | ___ |
| Status accuracy | ___ |
| Route accuracy | ___ |
| Median latency | ___ ms |
| Cost for all 23 calls | $___ |
| Keyword-rules baseline route accuracy (sim) | 61% |

## Shot list

### 0:00–0:30 · The problem
**Show:** the empty page with "How it works".
**Say:** "Every request for a new internal AI tool hits the same questions before
anyone writes code: does Emma or the note taker already do this? What data does it
touch, and which reviews does that trigger? Is it specified well enough to hand to
Factory? Today that's meetings, or an LLM writing paragraphs nobody can audit. This
turns each question into a typed decision in under a second."

### 0:30–1:00 · The idea
**Show:** point at the three steps.
**Say:** "Jev decides, code enforces, nothing generates. Jev answers eleven typed
questions in one call and returns only numbers. Plain code applies our cutoffs, and a
fixed template writes the handoff. No model writes any text, so there's nothing to
hallucinate and every decision can be tested."

### 1:00–1:40 · Reuse
**Show:** click **Reuse: sprint notes**.
**Say:** "Weekly sprint notes. Jev matches the WebEx Note Taker, look at the probability
bars, and scores it fully covered. Verdict: reuse, no build. That's the reuse
capability paying for itself."
**Point at:** the metrics line: latency, tokens, cost.

### 1:40–2:30 · Extend, with a compliance catch
**Show:** click **Extend: French emails**.
**Say:** "French client-service emails. Jev matches Emma and says extend. But it also
classifies the data as restricted, and Emma is only approved to confidential, so reuse
isn't automatic. A privacy review is attached as a constraint."
**Scroll to:** the handoff spec. "Requester's words verbatim, the routing decision, the
constraints, a readiness checklist, and a decision record with the model and policy
version. That's what Factory receives."

### 2:30–3:00 · Blocked
**Show:** click **Blocked: credit model**.
**Say:** "A credit limit recommender. Model risk probability is high, so it's blocked
for model risk review before anything is built. That's OSFI E-23 territory, caught
at intake instead of at deployment."
**Point at:** the decision trace: "every rule, with the number that fired it."

### 3:00–3:30 · The cutoff is ours, not the model's
**Show:** scroll down slightly so the banner and the sliders are both on screen, drag **Review probability** up until the verdict flips, then **Reset**.
**Say:** "These cutoffs are plain code. Moving one re-runs the policy on the same
answers: no new Jev call, and it's labelled a what-if and not logged. Compliance owns
this number, in a config file, not a prompt."

### 3:30–4:15 · Evidence, not anecdotes
**Show:** Evaluation tab.
**Say:** "Twenty-three labelled requests covering every outcome. Review recall is ___
against a 90% bar; for comparison, simple keyword rules get 61% of routes right. This
chart re-runs the policy at every cutoff on the saved answers, so we choose the
trade-off between missed reviews and false alarms with data, for free."
**Point at:** one miss in the table, honestly: "This is where we'd refine the question wording."

### 4:15–4:35 · Audit
**Show:** Audit log tab.
**Say:** "Every decision is logged with the model, the policy version and the answers.
Just a hash of the request, never its text."

### 4:35–5:00 · Close and ask
**Say:** "Median ___ ms and $___ for all twenty-three calls. The same pattern works
anywhere an agent harness makes a small decision: routing, safety gates, eval
grading. It sits in front of Factory, not instead of it.
Three asks: the real tools catalog and data classification; a vendor and model risk
path for TypeSafe; and one team's intake queue for a pilot."

## Lines to avoid

- Vendor claims like "200× cheaper": quote only the numbers measured on screen.
- "Replaces Factory": it decides what Factory builds, and whether it's ready.
- Anything implying real data was used: say "synthetic" at least once on camera.
