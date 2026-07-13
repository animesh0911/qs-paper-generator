# Evals — in-place benchmarks for the three paid AI workflows

This package benchmarks the **actual production code paths** (no re-implemented
prompts, no parallel clients) across candidate models, and reports **cost,
accuracy, latency, and batch size** per run plus a **per-user monthly cost**
roll-up.

| # | Scenario | Production entry point under test | batch_size means |
|---|----------|------------------------------------|------------------|
| 1 | `generation` | `bank.generation.LangChainQuestionGenerator.generate` (grounded via the production corpus assembler) | requested question count (30 / 15; larger = premium lever) |
| 2 | `extraction` | `bank.extraction.SeamExtractor.extract` and `bank.ocr_extractor.MistralOcrMarkdownExtractor.extract`, plus a free `docling_guardrail` arm | pages per document (real papers, 50/500-page synthetic bundles) |
| 3 | `answers` | `bank.answer_generation.BankAnswerGenerator.generate`, chunked | extracted questions answered per run (250–2500 via `--question-limit`) |

**How it stays "in place":** every workflow already exposes an injection seam
(`make_model=` / `chat_model=`), so `evals.metering` attaches a token+latency
recorder through `make_chat_model(purpose, init=...)` without touching
production code, and model routing is applied with the same
`LLM_<PURPOSE>_PROVIDER/MODEL` env vars a deploy would set
(`evals.metering.seam_env`). What the eval measures is exactly what that
configuration would ship.

## Quickstart (everything runs in the web container)

```bash
# 0. See the model matrix + which prices still need verification
docker compose exec web python -m evals.run list-models

# 1. DRY RUN (default — prints unit matrix + cost forecast, no API calls)
docker compose exec web python -m evals.run generation \
    --models google/gemini-3.5-flash,deepseek-v4-flash --batch-sizes 30,15

# 2. Paid phase (explicit consent + budget cap; records + raw artifacts saved)
docker compose exec web python -m evals.run generation ... --yes --max-usd 2

# 3a. Deterministic scoring (free, no LLM: yield, shape, citation support)
docker compose exec web python -m evals.run score \
    --records /content/eval/results/generation-<ts>.jsonl

# 3b. Judged scoring — THE one judged path (consent-gated judge billing)
docker compose exec web python -m evals.run deepeval-score \
    --records /content/eval/results/generation-<ts>.jsonl --yes

# 4. Report (pure aggregation: tables + per-user monthly cost)
docker compose exec web python -m evals.report \
    --records /content/eval/results/generation-<ts>.scored.jsonl \
    --usage-profile brief_defaults --out /content/eval/results/report.md
```

Phase separation is deliberate: paid outputs are stored once
(`/content/eval/results/artifacts/`) and can be re-scored/re-reported forever
for free. Costs are re-priced at report time from recorded token counts, so
verifying a price later fixes past reports without re-running.

## Consent & budget rules (non-negotiable)

- Dry-run is the default; paid calls require `--yes` (project rule: a human
  consents before anything bills an LLM API).
- `--max-usd` (default $5, env `EVALS_MAX_RUN_USD`) is enforced against the
  forecast **and** against metered spend after every unit.
- Models with unverified pricing refuse to run unless
  `--allow-unverified-pricing` (tokens still recorded; cost computed later).

## Judges (accuracy harness)

There is exactly **one judged scoring path**: `deepeval-score` (below).
`score` is deterministic-only, so "which number is the number" never has two
answers. The Judge-protocol backends in `evals/judges/` (`claude -p`,
`codex exec`, seam) are retained as a *library* for cross-family second
opinions on golden sets — they are no longer a CLI scoring lane.

Rubrics live in `evals/judges/rubrics/*.md`, are versioned
(`rubric_version:`), and every verdict records its rubric version and judge id
so scores from different rubric revisions are never silently mixed. The judge
is never the model under test.

**deepeval suite** (`evals/deepeval_suite/`, Phase 1 — generation): the
decomposed measurement layer on top of the same stored artifacts. One G-Eval
per subjective rubric dimension (calibration lessons written into the
evaluation steps: fidelity enforces the citation contract, difficulty
penalizes verbatim lifts), claim-level `Faithfulness` against the excerpts a
candidate cites, and pure-code metrics for structure (`question_shape`) and
production's lexical screen (`citation_support`). The judge is any registry
model through the seam (`SeamJudgeLLM` — metered, priced, consent-gated):

```bash
docker compose exec web python -m evals.run deepeval-score \
    --records /content/eval/results/generation-<ts>.jsonl        # dry-run
docker compose exec web python -m evals.run deepeval-score \
    --records ... --yes                                          # judge bills
```

Sampling defaults to the verified golden items, so runs stay cheap and
directly comparable with human grades (agreement printed per dimension).
TestRun JSONs land under `/content/eval/deepeval-runs/<records-stem>/` with
per-run hyperparameters — the local experiment history. First calibrated run
(2026-07-13, judge $0.25): fidelity/self-containedness/answer within-1 of
humans ≥85%; `difficulty_plausibility` overshoots after the anti-verbatim
steps (judge 2.62 vs human 4.50) — re-tuning tracked in **#225**. Notes:
deepeval is pinned (4.0.9) in requirements; its pytest plugin imports
settings at collection, so compose defaults `OPENROUTER_BASE_URL`; telemetry
is opted out in the package `__init__`. Follow-ups: #225 regression gate,
#226 retriever/answers metrics, #227 agentic tracing, #228 experimentation.

**Regression gate** (`evals/tests/test_golden_gate.py`, #225): two layers.
The deterministic layer runs on every plain `pytest` — structural + lexical
grounding metrics over the 20 golden cases against a frozen per-case
baseline (deliberate behaviour changes update the baseline in the same
commit). The judged layer asserts judge–human agreement holds (mad ≤ 0.75,
within-1 ≥ 80% per dimension — #225's uniform target, with headroom over the
2026-07-13 measurements of 0.10–0.53 mad — plus Faithfulness pass rate ≥
0.90) and is consent-gated behind an env var because cache misses bill the
judge:

```bash
docker compose exec -e EVALS_GOLDEN_GATE=1 web \
    pytest evals/tests/test_golden_gate.py -q
```

deepeval's disk cache (`backend/.deepeval-cache.json`, gitignored, persists
via the bind mount) makes unchanged re-runs free — verified: a second gate
run reports $0.00 judge spend. Changing a metric's steps/rubric invalidates
only that metric's cache entries, so a tuning change re-bills cents, not the
suite.

**Judge calibration** (`evals/golden.py`): `python -m evals.run draft-goldens
--records <run>.jsonl` freezes a sample of a stored run's payloads+contexts
into `/content/eval/golden/<scenario>-<run_id>.golden.json` with *unscored*
`human_scores` (never judge-prefilled — an anchored human cannot calibrate).
A human scores every dimension (0–5, `-1` = n/a) and sets
`verified_by`/`verified_at`; from then on `score` re-judges those frozen items
and reports per-dimension judge–human agreement (`mean_abs_diff`, `within_1`)
as `judge_agreement` on the record. Goldens record their rubric version and
agreement refuses to compare across rubric revisions.

Accuracy per scenario:

- **generation** — deterministic: yield (delivered/requested), qtype mix,
  near-duplicate rate, citation-support rate (production's lexical screen
  from `bank.citation_support`, run over every candidate — a judge-independent
  grounding floor); judged (NCERT excerpts as ground truth, scoped to each
  candidate's `question_citation_ids`/`answer_citation_ids`): fidelity,
  self-containedness, qtype conformity, answer correctness.
- **extraction** — deterministic: the existing `score_extraction.score`
  (recall/precision/section/qtype/structure — comparable with the committed
  baselines in `/content/eval/results/`), plus verbatim-equation checks from
  the truth-manifest fidelity extension; judged: text/equation/diagram
  fidelity against the source page (rubric `extraction_fidelity`).
- **answers** — textbook-grounded: NCERT excerpts retrieved per question
  through the production corpus retriever are the ground truth
  (correctness/groundedness/marks-depth); corpus **coverage** is recorded and
  uncovered chapters are flagged `no_textbook_context`, reported separately.

## Inputs checklist (what a run needs before it can execute)

| Input | Needed by | Status |
|---|---|---|
| `OPENROUTER_API_KEY` in container env (all chat candidates route via OpenRouter; `MISTRAL_API_KEY` only for the OCR arm, `GEMINI_API_KEY` only for the unlisted gemini-2.5-flash-lite) | paid runs | key present; compose passes it through |
| Verified pricing in `evals/registry.py` | priced runs / cost report | 8 of 9 chat models verified from the live OpenRouter listing (2026-07-10); still open: gemini-2.5-flash-lite (not on OpenRouter) + Mistral OCR $/page — remainder of **#218** |
| Corpus seeded for the 2 generation fixture chapters (jesc104 `carbon-and-its-compounds`, jesc110 `human-eye-and-the-colourful-world`) | generation grounding | done — `corpus_coverage` reports 1.0; broader coverage for answers judging is still **issue #222** |
| Generation fixtures with pinned `chapter_map_node_ids` (`datasets/fixtures/generation_requests.json`; runtime selector stays as fallback) | generation | done |
| 2–3 more hand-labeled truth manifests + fidelity extension (`figures`, `equations` per question) | extraction accuracy | **issue** (1 paper labeled today) |
| Scale bundles built (`python -m evals.datasets.build_scale_bundles --pages 50 500`) | extraction 50/500-page runs | builder ready; segment-aware scoring **issue** |
| A completed extraction (`--ingestion-job <id>`) or the artifact-seeding path | answers runs | **issue** |
| Hand-verified goldens (`/content/eval/golden/*.golden.json`; draft with `python -m evals.run draft-goldens`, human scores + marks verified) | judge calibration (judge–human agreement) | tooling done; verified goldens pending — needs first stored runs, then human grading |
| Authenticated `claude` (and optionally `codex`) CLI on the machine running `score` | judged accuracy | operator setup |

## Harness contract for agents (Claude Code / Codex)

An agent driving this framework should:

1. Run the dry-run first and show the human the forecast; never add `--yes`
   without the human explicitly approving spend in the conversation.
2. After a paid run, immediately run `score` (CLI judge — free), then
   `report`, and read back the written file paths from stdout.
3. Treat exit code 1 + `ERROR:` on stderr as a refused/failed run — fix the
   named input (see checklist) rather than retrying blindly.
4. Never edit records JSONL by hand; re-run `score`/`report` instead.

## Implementation issues (the placeholder map)

Placeholders raise `EvalNotImplemented` naming their area; the tracked issues
(label `eval`):

- **#218 registry** — mostly done 2026-07-10: all chat candidates rerouted
  via OpenRouter, ids + rates verified against the live models listing
  (fixed two guessed-wrong qwen ids; deepseek-v4-flash is cheaper routed than
  native), `PRICING_AS_OF` bumped. Remaining: Mistral OCR $/page and
  gemini-2.5-flash-lite (not listed on OpenRouter — price natively or drop).
- **#219 generation end-to-end** — done: corpus seeded + node ids pinned for
  both fixture chapters, judge context scoped to each candidate's
  `question_citation_ids`/`answer_citation_ids` (unit-tested with a fake
  judge). Remaining: codex CLI flags are unverified — no `codex` binary was
  available in this environment to check `codex exec`'s non-interactive flags
  against (`evals/judges/codex_cli.py` is unchanged; verify before relying on
  the `codex` judge backend) — and the first recorded batch-30/15 smoke on two
  verified models is still consent-gated, not yet run. Also: the fixture
  chapter originally named `light-reflection-and-refraction` in this issue is
  jesc109, which has no canonical extraction artifact committed anywhere in
  the repo; the second fixture was repointed to
  `human-eye-and-the-colourful-world` (jesc110's actual chapter) instead.
  Sourcing/extracting jesc109 is a separate, unscoped follow-up if
  light-reflection-and-refraction grounding is wanted later.
- **#220 extraction ground truth** — 2–3 more truth manifests with the
  fidelity extension (`figures`, `equations`); per-page judge attribution +
  page-image rendering for scanned papers.
- **#221 extraction scale + free arms** — segment-aware bundle scoring
  (provenance-based), OCR-batch graph arm metering, real docling parse stats
  + the page-cap guardrail policy.
- **#222 answers seeding + calibration** — seeding still open: load stored
  extraction artifacts through the production ingest tail under a dedicated
  eval school/user. Calibration half done: golden draft → human-verify →
  judge–human agreement pipeline (`evals/golden.py`, the `draft-goldens`
  command, `judge_agreement` in the score phase); committed verified goldens
  still pending — they need the first stored runs plus human grading.
- **#223 v1 baseline run** — the consent-gated benchmark matrix; commit the
  scored records + report as the regression baseline (blocked by the above).

## Why no Langfuse/LangGraph tracing (for now)

The metering callback captures everything the brief needs (per-call tokens,
cache reads, latency; per-run cost/wall) directly at the seam every call
passes through, with zero new infrastructure. If deeper tracing is wanted
later, a Langfuse callback can be appended in exactly the same
`init=` seam (`evals/metering.py`) without touching production or scenarios.
