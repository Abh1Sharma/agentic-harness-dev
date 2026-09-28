# Loom script: SafeAI Marketplace (~5 minutes)

Audience: a senior leader focused on regulatory risk and on showing something new that fits the
bank's architecture and innovation agenda. The message: **the marketplace can prove what
it certifies, and stop people rebuilding what's already certified.**

## Before you record

- [ ] Header on `/app` shows **Live · jev-latest**, not Simulated. Never record in sim mode.
- [ ] Run the live eval: `uv run --env-file .env python -m reuse_router.evaluate --mode live`.
      Fill in the table below from its output.
- [ ] Click each demo button once. If Jev routes one differently from this script, follow
      what it actually does or skip that button. Don't hide a miss.
- [ ] If recording from Vercel: set `PASSPORT_SIGNING_KEY` so the Passports tab doesn't
      show the demo-key warning.
- [ ] `rm data/audit.jsonl` for a clean audit tab (local only).
- [ ] Browser zoom 110–125%, light mode, other tabs closed. Start on `/` (slide 1).

| Metric (live eval, jev-1.13.0, 28 Sep 2026) | Value |
|---|---|
| Route accuracy | 88% |
| Review recall (bar 90%) | 100% (0 missed) in both live runs; precision 69–72% (7–8 false alarms) |
| Median latency | 179 ms (max 530 ms) |
| Cost for all 25 calls | $0.0018 |
| Keyword-rules baseline (sim): route accuracy / review recall | 60% / 78% |

## Shot list

### 0:00–1:30 · Slides (about 15 seconds each)
1. **Title.** "This is a proof of concept for the AI Marketplace: certify once, reuse everywhere, prove it any time."
2. **Problem.** "We're building more AI assets every quarter, and supervisors expect an inventory, risk ratings, documentation and monitoring. Every duplicate is one more thing to certify and watch."
3. **What we have.** "The marketplace and Pantheon already certify assets without using AI to judge AI. Two gaps: people can't find what's certified, so they rebuild it. And an approval is just a status: nothing else can check it, and it doesn't notice when the code changes."
4. **The idea.** "Two additions under one principle: AI reads, rules decide, people approve, evidence is automatic. Discover uses Jev. The Passport deliberately uses no AI."
5. **Jev.** "Jev is a decision model: text in, numbers out, in one fast call. It doesn't write anything, so there's nothing invented to review, and every decision can be tested. It isn't the certifier: Pantheon and people are."
6. **Demo steps.** Read them in one breath, then click **Start the demo**.

### 1:30–2:10 · Discover: reuse
**Click** "Reuse: invoice extraction".
**Say:** "Someone needs invoice fields pulled from scanned PDFs. Jev matches Docvision and scores it as covering the need, so the verdict is reuse: no build, no new certification. Here's its SafeAI status, and the measured time and cost of that decision."

### 2:10–2:50 · Discover: the compliance catch
**Click** "Catch: client letters".
**Say:** "Translating outgoing client letters. Jev matches the Translation Service with full confidence and says reuse, but it also classifies client letters as restricted data, and that service is only certified up to confidential. So reuse isn't automatic: a privacy review is attached, and the trace shows the number behind every rule."
Optional, if time allows: drag **Review probability** until the verdict flips, then **Reset**. "Cutoffs are plain code that risk owns, not a prompt."

### 2:50–4:20 · The Passport
**Click** "Reuse: invoice extraction" again, then **View passport**.
**Say:** "Docvision's SafeAI Passport: its version, certified commit, risk tier, data approval and every Pantheon check, signed by the marketplace. The signature is valid, it's in date, and the code matches what was certified. Any system with this public key can check it without calling us."
**Click** "Tamper test: edit JSON", change `"risk_tier": "medium"` to `"low"`, **Verify**.
**Say:** "Someone quietly downgrades the risk tier. The signature fails and nothing in it is trusted."
**Click** **Reset**, then **Simulate new commit**.
**Say:** "Now the team pushes new code. The passport is suspended automatically until the asset is re-certified. That's change management with proof attached."

### 4:20–5:00 · Close and ask
**Say:** "Two pieces: Discover stops us rebuilding what's certified, and the Passport makes every certification provable and aware of change. Three asks: feed Pantheon's real results into passports; agree with the AI risk office who holds the signing key; and pilot with EMMA, Notetaker and Docvision listed with passports and Discover on the intake page. Discover would also need a vendor review of TypeSafe before real data touches it."

## Lines to avoid

- Vendor claims like "200× cheaper": quote only the numbers measured on screen.
- "AI certifies the asset": Pantheon and people certify; Jev only reads the request.
- Anything implying real data or real Pantheon results: say "synthetic" and "mocked" once.
