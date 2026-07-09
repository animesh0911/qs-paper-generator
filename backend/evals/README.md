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

# 3. Scoring phase (no candidate-model spend; judge = claude CLI by default)
docker compose exec web python -m evals.run score \
    --records /content/eval/results/generation-<ts>.jsonl --judge claude

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

Pluggable via `--judge` on the score command:

- `claude` (default) — shells out to `claude -p --output-format json`; needs an
  authenticated Claude Code CLI. Subscription-covered: scoring is free.
- `codex` — `codex exec` subprocess (cross-family second opinion).
- `seam` — pinned API model through the production seam, for unattended CI.

Rubrics live in `evals/judges/rubrics/*.md`, are versioned
(`rubric_version:`), and every verdict records its rubric version and judge id
so scores from different rubric revisions are never silently mixed. The judge
is never the model under test.

Accuracy per scenario:

- **generation** — deterministic: yield (delivered/requested), qtype mix,
  near-duplicate rate; judged (NCERT excerpts as ground truth): fidelity,
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
| API keys in container env: `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `MISTRAL_API_KEY` | paid runs per provider | compose already passes them through |
| Verified pricing in `evals/registry.py` (7 models + Mistral OCR marked UNVERIFIED) | priced runs / cost report | **issue** |
| Corpus seeded for fixture chapters (chapter maps + chunks; today only jesc104/jesc110) | generation grounding, answers judging | **issue** (expand coverage) |
| Generation fixtures with pinned `chapter_map_node_ids` (`datasets/fixtures/generation_requests.json`; runtime selector works meanwhile) | generation | **issue** |
| 2–3 more hand-labeled truth manifests + fidelity extension (`figures`, `equations` per question) | extraction accuracy | **issue** (1 paper labeled today) |
| Scale bundles built (`python -m evals.datasets.build_scale_bundles --pages 50 500`) | extraction 50/500-page runs | builder ready; segment-aware scoring **issue** |
| A completed extraction (`--ingestion-job <id>`) or the artifact-seeding path | answers runs | **issue** |
| Hand-verified golden answers (`/content/eval/golden/`) | judge calibration (judge–human agreement) | **issue** |
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

- **#218 registry** — verify pricing + model ids (7 UNVERIFIED entries,
  Mistral OCR $/page, OpenRouter ids for gpt-oss/qwen); keep `PRICING_AS_OF`
  honest.
- **#219 generation end-to-end** — seed corpus for fixture chapters, pin node
  ids, citation-scoped judge context, codex CLI flag verification, first
  recorded batch-30/15 smoke.
- **#220 extraction ground truth** — 2–3 more truth manifests with the
  fidelity extension (`figures`, `equations`); per-page judge attribution +
  page-image rendering for scanned papers.
- **#221 extraction scale + free arms** — segment-aware bundle scoring
  (provenance-based), OCR-batch graph arm metering, real docling parse stats
  + the page-cap guardrail policy.
- **#222 answers seeding + calibration** — load stored extraction artifacts
  through the production ingest tail under a dedicated eval school/user;
  hand-verified golden sets + judge–human agreement reporting.
- **#223 v1 baseline run** — the consent-gated benchmark matrix; commit the
  scored records + report as the regression baseline (blocked by the above).

## Why no Langfuse/LangGraph tracing (for now)

The metering callback captures everything the brief needs (per-call tokens,
cache reads, latency; per-run cost/wall) directly at the seam every call
passes through, with zero new infrastructure. If deeper tracing is wanted
later, a Langfuse callback can be appended in exactly the same
`init=` seam (`evals/metering.py`) without touching production or scenarios.
