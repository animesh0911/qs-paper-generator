# Upload extraction eval

Lean live eval for the upload AI feature:

```text
PDF -> Mistral OCR -> OCR markdown -> structuring LLM -> extracted Questions
```

The eval uses real API keys, caches OCR once, then tests any LLM model/batch-size matrix against the same OCR output.

## Code paths

- Shared production/eval module: `backend/bank/upload_extraction/pipeline.py`
- Live eval runner: `backend/bank/upload_extraction/live_eval.py`
- External script: `backend/scripts/eval_upload_extraction_live.py`
- Production OCR-batch graph also uses the same module: `backend/workflows/extraction.py`

## Prereqs

Set keys in `.env` or environment:

```bash
MISTRAL_API_KEY=...
OPENROUTER_API_KEY=...   # if --provider openrouter
```

Default OCR model:

```bash
MISTRAL_OCR_MODEL=mistral-ocr-latest
```

## Run checks

```bash
cd backend

uv run ruff check \
  bank/upload_extraction \
  bank/ocr_extractor.py \
  workflows/extraction.py \
  scripts/eval_upload_extraction_live.py \
  scripts/mistral_ocr_batch_poc.py \
  bank/tests/test_upload_extraction_pipeline.py

DJANGO_DEBUG=1 uv run pytest bank/tests/test_upload_extraction_pipeline.py -q
```

## Dry run

No API calls:

```bash
cd backend

uv run python scripts/eval_upload_extraction_live.py \
  media/ingestion_uploads/2025_science_paper6.pdf \
  --provider openrouter \
  --models google/gemini-3.5-flash,qwen/qwen3.7-plus \
  --batch-sizes 1,5,all \
  --out-dir ../content/eval/upload-runs/test-001
```

## Live run

Adds `--yes`, so this calls Mistral OCR and LLM APIs:

```bash
cd backend

uv run python scripts/eval_upload_extraction_live.py \
  media/ingestion_uploads/2025_science_paper6.pdf \
  --provider openrouter \
  --models model-a,model-b,model-c,model-d,model-e \
  --batch-sizes 1,5,all \
  --out-dir ../content/eval/upload-runs/test-001 \
  --yes
```

Notes:

- OCR runs once per `--out-dir` and writes `ocr.json`.
- Re-running with the same `--out-dir` reuses OCR by default.
- Use `--no-reuse-ocr` to force a new OCR call.
- Use `--max-batches 1` for a cheap smoke test.

## Output

Main report:

```text
<out-dir>/results.csv
```

Columns:

```csv
pdf_pages,ocr_model,ocr_cost,ocr_latency,ocr_output_size,llm_model,batch_size,llm_cost,llm_latency,total_cost,questions
```

Artifacts:

```text
<out-dir>/ocr.json
<out-dir>/ocr.md
<out-dir>/ocr_meta.json
<out-dir>/results.jsonl
<out-dir>/artifacts/<model>/batch-<batch_size>/structured_batches.json
<out-dir>/artifacts/<model>/batch-<batch_size>/questions.json
```

## Production smoke path

The production upload drainer can use the OCR-batch path:

```bash
cd backend

uv run python manage.py drain_ingestion_jobs \
  --extractor mistral-ocr-batch \
  --batch-pages 999 \
  --dry-run
```

Remove `--dry-run` only when you want to process queued `IngestionJob`s with live API spend.
