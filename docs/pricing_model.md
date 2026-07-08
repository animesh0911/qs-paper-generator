# Exam Desk — Pricing Model (v1)

**Status:** Proposal for review
**Date:** 2026-07-08
**Inputs:** [question_generation_model_cost_report.md](common/question_generation_model_cost_report.md),
[issue_177_grounded_generation_acceptance_report.md](common/issue_177_grounded_generation_acceptance_report.md),
[ADR-0004](adr/0004-gemini-native-pdf-ingestion.md), [PRD](PRD.md)
**FX assumption:** ₹88 / USD. All INR figures rounded.

---

## 1. Summary — recommended launch pricing

| | **Free** | **Teacher Pro** |
|---|---|---|
| Price | ₹0 | **₹499 / month** or **₹3,999 / year** (~2 months free) |
| Papers / month | 2 | 25 (fair-use soft cap; overage below) |
| Regenerate / swap per paper | 3 | Unlimited (fair use) |
| Exports | PDF with "Made with Exam Desk" watermark | PDF + DOCX + answer key, no watermark |
| School branding on exports | — | ✅ |
| AI editor assistant | 5 messages / paper | ✅ |
| Question freshness history (cross-paper LRU) | — | ✅ |
| Generation model | Economy (`gemini-3.1-flash-lite`) | Economy by default; premium model routing reserved as a future fence |
| Overage | Hard stop | ₹25 / paper beyond 25 |

**Blended contribution margin at these prices: ~75–80%** after LLM + hosting costs
(math in §4), meeting the 70–80% target. International (Gulf CBSE schools) can be
priced later at $9/mo with zero product change.

The **value metric is "papers"**, not tokens, credits, or API calls. A teacher
thinks in papers; a paper is where the value lands (3–6 hours of manual work
replaced by ~30–45 minutes of review). Never expose tokens to users.

---

## 2. Cost per run — LLM unit economics

### 2.1 What a "run" is

One paper-generation run (the async job in the PRD) triggers these LLM calls:

| Step | Calls | Model | Basis |
|---|---|---|---|
| Grounded question generation | 1 per selected major topic (~5 for an average 3–5 chapter paper) | `gemini-3.1-flash-lite`, count=15 | Measured in #177: **$0.034 for a 5-topic pass** (~$0.007/call, ~6–10k in / ~5–8k out tokens) |
| Verifier / solver (PRD story 34) | 1 small call per kept candidate (~20/paper) | economy model | ~2k in / ~0.5k out → ~$0.0006/call → **~$0.012** |
| Regenerate / swap during review | ~3 events → ~1 extra topic call + verifs | economy model | **~$0.010** |
| AI editor assistant | ~8 short turns | economy model | **~$0.008** |

**Base case: ≈ $0.065 → round to $0.07 (₹6) per paper.**
Planning range **$0.05–0.10 (₹4.5–9)** to absorb heavier regeneration, retries on
invalid payloads (cost report caveat 4), and OpenRouter routing markup.

Premium-stack sensitivity: the same run on `gemini-3.5-flash` end-to-end costs
**~$0.45 (₹40)/paper** (5 × $0.061 generation + ~$0.09 verification + overhead).
That is 6–7× the economy stack — which is why "premium model" is kept as a future
paid fence, not a default.

### 2.2 PDF ingestion cost (the "average PDF" question)

Ingestion (ADR-0004) sends the source PDF natively to Gemini 3.5 Flash. An average
CBSE past paper is ~25–35 pages:

- Input: ~12–18k tokens (page images + prompt + schema) → ~$0.02
- Output: ~12–18k tokens of structured questions → ~$0.14
- **≈ $0.15–0.25 (₹13–22) per past-paper PDF**

Today this is a **platform content cost, not a per-user cost**: a one-time-per-year
batch of ~51 papers ≈ **~$10/year** — negligible. It only enters the per-tenant
model if/when B2B customers upload their own PDFs; then meter it (e.g. N PDF
ingestions included per school plan, ₹49/PDF beyond) because it is 2–4× the cost
of a whole paper run.

### 2.3 Per-user monthly LLM cost

| Persona | Papers/mo | LLM cost/mo |
|---|---:|---:|
| Free (capped) | 2 | ~$0.14 (₹12) |
| Paid, median | 6 | ~$0.42 (₹37) |
| Paid, heavy (P90) | 20 | ~$1.40 (₹123) |
| Paid, at soft cap | 25 | ~$1.75 (₹154) |

## 3. Deployment costs

Hosting is a simple PaaS (Render/Railway/Fly + managed Postgres, per PLAN):

| Scale | Monthly infra | Allocation per **paying** user |
|---|---:|---:|
| MVP / pilot (≤100 MAU) | ~$50 (web $25 + Postgres $20 + cron/assets $5) | dominated by fixed cost |
| Growth (~500–1,000 MAU, ~200 paying) | ~$150–300 | **~$0.30–0.75 (₹26–66)/mo** |

Infra is effectively fixed at this stage; LLM spend is the only true marginal
cost. Use **₹26/paying user/mo** as the planning allocation.

## 4. Margin model at ₹499/month

Assume a **4:1 free-to-paid ratio** (each paying user "carries" four active free
users at ₹12/mo each = ₹48 subsidy).

| Scenario | LLM | Infra | Free-tier subsidy | Total cost | Margin on ₹499 |
|---|---:|---:|---:|---:|---:|
| Median paid user (6 papers) | ₹37 | ₹26 | ₹48 | ₹111 | **78%** |
| Heavy user (20 papers) | ₹123 | ₹26 | ₹48 | ₹197 | **61%** |
| At soft cap (25 papers) | ₹154 | ₹26 | ₹48 | ₹228 | **54%** |
| Blended (usage mix ~70% median / 25% heavy / 5% cap) | | | | ~₹135 | **~73%** |

Read on this:

- The **median and blended cases land inside the 70–80% target**. Heavy users
  dilute margin but stay contribution-positive by a wide distance — the cap +
  ₹25/paper overage exists so the tail can never invert the model (overage itself
  carries ~75% margin: ₹25 price vs ~₹6 cost).
- The two biggest margin levers, in order: **(1) free-tier generosity** (cutting
  free from 2 → 1 paper/mo adds ~5pts blended margin; do this before ever raising
  price), **(2) model routing** (staying on flash-lite vs 3.5 Flash is the
  difference between 73% and negative margin — treat a model upgrade as a pricing
  event, not an engineering toggle).
- Annual plan ₹3,999 (₹333/mo effective) still yields ~65–70% blended margin and
  is worth it: it smooths India's exam-season usage spikes (see §6.2) and
  pre-pays CAC.

## 5. Tier design rationale (what fences which tier)

- **Watermarked PDF on Free** — the export is the artifact teachers share in
  staff rooms and WhatsApp groups; the watermark is the growth loop. DOCX +
  answer key + school branding are the conversion fences because they map to the
  moment of real institutional use (printing a branded paper for an actual exam).
- **Do not fence trust.** Verification quality, source labels, confidence
  indicators, and citations are identical on both tiers. A free tier that
  produces less-trustworthy papers poisons the brand (PRODUCT.md: "calm, precise,
  trustworthy") and the watermark loop.
- **2 papers/mo free is a real taste, not a trial** — enough for one unit test
  cycle, not enough for exam season. Time-boxed trials fit B2B later, not
  teacher B2C in a seasonal market.
- **Answer key behind Pro** is the single strongest converter: the key is half
  the manual labor and is needed exactly when the paper is actually used.

## 6. Alternative pricing approaches considered

### 6.1 Pure pay-per-paper (usage-based credits)
₹49/paper or 10-pack for ₹399. **Pros:** perfectly matches seasonal usage; zero
commitment; ~85%+ margin per unit. **Cons:** meter anxiety suppresses the
regenerate/swap/editor behavior that makes output quality good (users "save"
credits by under-iterating); revenue is spiky and LTV unpredictable.
**Verdict:** rejected as the primary model, **adopted as the overage mechanism**
inside Pro — best of both.

### 6.2 Exam-season pass
₹999 for a 3-month pass timed to the Indian academic calendar (Sep–Oct
half-yearlies, Dec–Feb prelims/boards). **Pros:** matches when teachers feel the
pain; easy impulse purchase. **Cons:** churns by design; trains users to lapse.
**Verdict:** hold as a **promotional SKU** for seasons 1–2 to convert fence-
sitters, not a core tier. The annual plan is the structural answer to
seasonality.

### 6.3 Free for teachers, schools pay (B2B2C)
Teachers use free; the school buys a site license that unlocks branding, admin,
shared bank, and analytics for its staff. **Pros:** schools have the budget and
the branding requirement is inherently institutional; single buyer, many users.
**Cons:** needs a sales motion, admin/roles, and multitenancy that don't exist
yet (single-tenant MVP). **Verdict:** this is the **likely end-state** — see §8 —
but B2C-first builds the bottom-up wedge and the usage data to price B2B well.

### 6.4 Per-export pricing (charge at the moment of value)
Generation free, pay on export/approval. **Pros:** purest value alignment.
**Cons:** we pay LLM costs for every abandoned draft; invites generate-and-
screenshot workarounds. **Verdict:** rejected; the watermark achieves the same
alignment more safely.

### 6.5 Content add-ons / marketplace
Sell additional verified banks (more subjects/classes) as add-ons on top of a
cheaper base subscription. **Pros:** monetizes the curation moat (the verified
bank is the defensible asset, more than the LLM calls); natural expansion
revenue. **Cons:** meaningless while scope is Class 10 Science only.
**Verdict:** revisit at multi-subject expansion — likely as Pro bundling
("all subjects") vs à-la-carte.

### 6.6 Token/credit metering
**Rejected outright.** Teachers cannot reason about tokens; it violates the
"understandable meter" principle and imports our cost structure into the user's
mental model. Costs stay our problem; papers stay their unit.

## 7. Pricing principles applied (senior-PM checklist)

1. **Value-based, not cost-plus.** Cost sets the floor (~₹6/paper); the ceiling
   is 3–6 teacher-hours saved per paper. At ₹499/mo and 6 papers, we charge
   ~₹83/paper against hundreds of rupees of implied time value — deliberately
   capturing a small slice to maximize adoption in a price-sensitive segment.
2. **One value metric, aligned with value delivery:** papers. It scales with
   value received, is predictable for the user, and we can meter it precisely.
3. **Simplicity:** two tiers, one number each, one overage rate. No matrix.
4. **Segmentation via fences, not SKUs (yet):** watermark/branding/DOCX fence
   individual-casual from individual-professional; admin/multi-seat will fence
   individual from institution later. Fences are features buyers self-select on,
   so we don't need to identify the segment at signup.
5. **Margin protected structurally, not hopefully:** free cap, soft cap +
   overage, economy-model default, and prompt/context caching (DeepSeek 98% /
   Gemini 90% cache-hit discounts) are all in the design, not the roadmap.
6. **Price to learn, anchor high enough:** launch is labeled introductory; it is
   far easier to grandfather ₹499 down than to raise a ₹199 anchor. Do not
   launch below ₹299 under any pilot pressure.
7. **Growth loop priced in:** the free tier is a marketing expense with a known
   unit cost (~₹12/user/mo) and a built-in distribution channel (watermarked
   exports circulating between teachers).
8. **Charge in the buyer's currency and calendar:** INR pricing, annual plan
   aligned to the academic year, seasonal SKU held in reserve.
9. **Unit-economics discipline:** every tier decision above is expressed as
   its effect on blended contribution margin; the model has named levers
   (§4) rather than a single break-even point.

### Validation plan before locking price

- Van Westendorp survey (~30–50 CBSE teachers) around the ₹299/499/799 band.
- Pilot-school WTP interviews for the B2B anchor (per-teacher vs per-school).
- Instrument papers/user/month from day one — the entire margin model keys off
  the median (6) and P90 (20) assumptions; replace them with real data in the
  first pricing review (90 days post-launch).

## 8. Future: multitenant B2B + B2C

The `school_id` seam (PRD extensibility) makes this additive. Target
architecture when B2B opens:

| | Free | Teacher Pro | **School** |
|---|---|---|---|
| Buyer | Teacher | Teacher | Principal / admin |
| Price | ₹0 | ₹499/mo | **₹2,999/teacher/year, min 5 seats** (≈₹15k/school entry) — or flat ₹25k–60k/school/year for large schools |
| Fences | — | Branding, DOCX, key | Central branding control, shared school bank, teacher roles/approval workflow, usage analytics, own-PDF ingestion (metered, N included), priority support |

Design rules for that step:

- **Per-seat, billed annually** is the default B2B metric — schools budget
  annually and per-seat scales with value; flat site license only for
  negotiated large accounts.
- B2C Pro at ₹3,999/yr must stay **more expensive per seat** than the school
  rate (₹2,999) so procurement has a reason to centralize — the classic
  bottom-up → top-down conversion path.
- Own-PDF ingestion (₹13–22 real cost/PDF) becomes a **metered B2B feature**
  (e.g. 25 ingestions/year included, ₹49 each beyond), never unlimited.
- Gulf/international CBSE schools: same product, USD price list (~$9/mo B2C,
  ~$79/seat/yr B2B) — 5–8× ARPU for identical cost. Keep price lists per
  region from day one of B2B.

## 9. Risks & open items

| Risk | Exposure | Mitigation |
|---|---|---|
| Model price changes / OpenRouter markup | Direct hit to the ₹6/paper base | Provider seam already exists (`LLM_PROVIDER`); DeepSeek V4 Flash is a 10× cheaper fallback at ~$0.003/call; re-run cost report quarterly |
| Invalid-payload retries inflate calls | Cost report caveat 4 | Count retries in the per-paper cost meter; alert if paper cost P95 > ₹12 |
| Free-tier abuse (multi-account) | Free cost is small but not zero | Verified email + device heuristics; free tier requires no card, so keep the cap the real control |
| Regeneration-heavy users | P90 assumptions wrong | Instrument regenerations/paper; the ₹25 overage backstops the tail |
| Underpricing anchor in pilots | Hard to raise later | "Introductory pricing" label + grandfathering policy stated at launch |
| FX drift on Gemini billing (USD) vs INR revenue | ~±10%/yr | Priced with headroom (blended 73% vs 70% floor); annual plans hedge partially |
