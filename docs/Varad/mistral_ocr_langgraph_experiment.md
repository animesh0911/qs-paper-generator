# Mistral OCR + LangGraph Extraction Experiment

## Goal

Test whether we can extract **questions only** from CBSE previous-year paper PDFs by inserting a cheap OCR step before the existing LLM-based question structuring and ingestion pipeline.

The experiment should reuse the current codebase as much as possible:

- Keep the existing `IngestionJob` ledger.
- Keep the existing LangGraph resumable extraction flow.
- Keep the existing question schema and coercion helpers.
- Keep the existing `Ingestor.ingest_extracted(...)` persistence tail.
- Keep the existing source selector behavior: persisted upload sources should appear as `upload:<job_id>`.

The only intended change is the page extraction strategy:

```text
Current production path:
PDF page -> Gemini native-PDF structured extraction -> { questions: [...] }

Experiment path:
PDF page -> Mistral OCR markdown -> LLM markdown-to-question structuring -> { questions: [...] }
```

## Current extraction architecture

The current resumable extraction graph lives in:

```text
backend/workflows/extraction.py
```

Current graph shape:

```text
plan
  -> extract_page
      -> extract_page ... until all pages are done
  -> persist
```

### `plan`

- Loads the uploaded PDF from the `IngestionJob` row.
- Counts pages with `count_pages(pdf_bytes)`.
- Updates `IngestionJob.total_pages` and resets `pages_done`.

### `extract_page`

- Loads the PDF from the job row.
- Slices one page using `slice_page(pdf_bytes, next_page)`.
- Calls `SeamExtractor.extract_page(page_bytes)`.
- The current `SeamExtractor` sends the single-page PDF to the configured extraction LLM and expects a structured payload:

```json
{
  "questions": []
}
```

- Appends the page payload to graph state.
- Updates `IngestionJob.pages_done`.

### `persist`

- Merges page payloads with:

```py
merge_page_payloads(state["payloads"])
```

- Persists through:

```py
Ingestor().ingest_extracted(
    questions,
    source_file_name=job.source_file_name,
    source_type=job.source_type,
    school=job.school,
    pdf_bytes=pdf_bytes,
    ingestion_job=job,
)
```

This tail already performs:

- question coercion
- internal-choice splitting
- parse quality computation
- guardrails
- deduplication by `source_hash`
- diagram cropping, when `pdf_bytes` is provided
- `Question` row creation
- `ingestion_job` linking

## Existing source selector behavior

The source selector endpoint lives in:

```text
backend/bank/views.py
```

It includes uploaded sources from `IngestionJob` rows:

```py
IngestionJob.objects.filter(school=request.user.school)
```

and emits items shaped like:

```json
{
  "key": "upload:<job_id>",
  "kind": "upload",
  "title": "31-2-1.pdf",
  "detail": "Previous-year paper",
  "question_count": 42,
  "matching_question_count": 42,
  "status": "done"
}
```

Therefore, the experiment does not need a source-selector change. If questions are persisted with `ingestion_job=job`, the source should appear automatically.

## Proposed experiment flow

```text
Teacher/sample PDF
  -> IngestionJob
  -> LangGraph plan
  -> per-page PDF slice
  -> Mistral OCR
  -> page markdown
  -> LLM structures markdown into existing question JSON shape
  -> merge_page_payloads
  -> Ingestor.ingest_extracted
  -> Question rows linked to IngestionJob
  -> /api/bank/sources/ shows upload:<job_id>
```

## Mistral OCR step

Mistral OCR endpoint:

```text
POST /v1/ocr
```

Example request body from docs:

```json
{
  "model": "mistral-ocr-latest",
  "document": {
    "type": "document_url",
    "document_url": "https://arxiv.org/pdf/2201.04234"
  }
}
```

Expected response includes pages:

```json
{
  "pages": [
    {
      "index": 0,
      "markdown": "..."
    }
  ]
}
```

For the experiment, each page slice can be OCRed independently, matching the current page-at-a-time graph design.

Open implementation question:

- Does Mistral OCR accept `data:application/pdf;base64,...` URLs in `document_url`?
- If not, we need one of:
  - Mistral file upload/FileChunk support,
  - a temporary signed URL for the uploaded page/PDF,
  - or OCR the whole original PDF once and map returned markdown pages to graph pages.

The existing POC script currently tries the base64 data URL approach:

```text
backend/scripts/mistral_ocr_poc.py
```

## Markdown-to-question structuring step

Mistral OCR returns markdown, not our application question schema. We still need a structuring LLM call.

Input:

```text
OCR markdown for one page
```

Output:

```json
{
  "questions": [
    {
      "section": "A",
      "qtype": "mcq",
      "marks": 1,
      "rawText": "...",
      "options": [
        { "label": "A", "text": "..." }
      ],
      "content": {
        "stem": [
          { "type": "paragraph", "text": "..." }
        ]
      },
      "chapter_slug": null,
      "cognitive_level": "R",
      "topic_names": [],
      "primary_form": "none",
      "figures": []
    }
  ]
}
```

We should reuse the existing schema builder:

```py
build_question_schema(Chapter.objects.values_list("slug", flat=True))
```

For this POC, we intentionally scope down to **questions only**:

- Extract English questions from previous-year papers.
- Extract MCQ options where present.
- Extract marks where visible.
- Infer/emit qtype.
- Emit `content.stem` minimally.
- Prefer `figures: []` for now.
- Do not attempt diagram cropping in the first pass.
- Do not extract answers or marking schemes.

## LangGraph integration options

### Option A: Minimal-change extractor swap

Keep the graph shape unchanged:

```text
plan -> extract_page -> persist
```

Add a new extractor implementing the same page-level interface as `SeamExtractor`:

```py
class MistralOcrMarkdownExtractor:
    def extract_page(self, page_bytes: bytes) -> dict:
        markdown = self.ocr_page(page_bytes)
        return self.structure_markdown(markdown)
```

Then make `build_extraction_graph(...)` accept an extractor or extractor factory.

Current:

```py
extractor = SeamExtractor(make_model=make_model)
ingestor = Ingestor(extractor=extractor)
```

Possible POC shape:

```py
def build_extraction_graph(checkpointer, make_extractor=None, make_model=make_chat_model):
    extractor = make_extractor() if make_extractor else SeamExtractor(make_model=make_model)
    ingestor = Ingestor(extractor=extractor)
```

The existing `extract_page` node can remain largely unchanged:

```py
payload = extractor.extract_page(page)
```

Advantages:

- Smallest code change.
- Reuses existing graph state.
- Reuses existing checkpointing.
- Reuses existing persist node.
- Easy to remove if the experiment fails.

Disadvantage:

- OCR output markdown is not separately checkpointed unless the extractor includes it in the returned payload or writes artifacts elsewhere.

### Option B: Explicit OCR and structure nodes

Change the graph to:

```text
plan
  -> ocr_page
  -> structure_page
      -> ocr_page ... until all pages are done
  -> persist
```

Possible state:

```py
class OcrExtractionState(TypedDict, total=False):
    job_id: int
    total_pages: int
    next_page: int
    ocr_pages: Annotated[list[dict], operator.add]
    payloads: Annotated[list[dict], operator.add]
    created: int
    skipped: int
```

`ocr_page`:

```py
def ocr_page(state):
    _, pdf_bytes = _load_job_pdf(state["job_id"])
    page = slice_page(pdf_bytes, state["next_page"])
    markdown = mistral_ocr(page)
    return {
        "ocr_pages": [{"index": state["next_page"], "markdown": markdown}],
    }
```

`structure_page`:

```py
def structure_page(state):
    markdown = state["ocr_pages"][-1]["markdown"]
    payload = structure_markdown(markdown)
    pages_done = state["next_page"] + 1
    IngestionJob.objects.filter(pk=state["job_id"]).update(pages_done=pages_done)
    return {
        "payloads": [payload],
        "next_page": pages_done,
    }
```

`persist` still uses:

```py
questions = merge_page_payloads(state["payloads"])
```

Advantages:

- OCR output is first-class graph state.
- Better observability.
- Easier to inspect and compare OCR vs structured output.
- If structuring fails, OCR pages are already checkpointed.

Disadvantages:

- Larger change than Option A.
- More state to manage.

## Recommended POC approach

Start with **Option A**.

Reason: the experiment is primarily about whether Mistral OCR markdown plus a structuring LLM produces acceptable question JSON. The existing graph already has the right lifecycle and persistence model.

After the POC proves useful, we can decide whether to promote OCR markdown to first-class graph state using Option B.

## POC implementation plan

### 1. Run the existing standalone script first

Use:

```text
backend/scripts/mistral_ocr_poc.py
```

This already performs:

```text
PDF -> Mistral OCR -> page markdown -> Mistral chat JSON -> Ingestor.ingest_extracted
```

Run without persistence first:

```bash
cd backend
MISTRAL_API_KEY=... python scripts/mistral_ocr_poc.py media/ingestion_uploads/31-2-1.pdf --max-pages 2
```

Expected artifacts:

```text
/tmp/mistral-ocr-poc/ocr.json
/tmp/mistral-ocr-poc/ocr.md
/tmp/mistral-ocr-poc/structured_page_payloads.json
/tmp/mistral-ocr-poc/questions.json
```

Then run with persistence:

```bash
cd backend
MISTRAL_API_KEY=... python scripts/mistral_ocr_poc.py media/ingestion_uploads/31-2-1.pdf \
  --persist \
  --teacher-email teacher@example.com \
  --source-type previous_year_paper \
  --max-pages 2
```

Success criteria:

- `questions.json` contains extracted questions.
- Database has new `Question` rows.
- Rows are linked to the created `IngestionJob`.
- `/api/bank/sources/` includes `upload:<job_id>`.

### 2. Add a reusable Mistral OCR client

Candidate location:

```text
backend/ai_services/mistral_ocr.py
```

Responsibilities:

- Read `MISTRAL_API_KEY`.
- Call `POST /v1/ocr`.
- Return page markdown.
- Hide transport details from ingestion code.

### 3. Add markdown structuring adapter

Candidate location:

```text
backend/bank/ocr_extractor.py
```

or inside `backend/bank/ingestor.py` if kept small for the POC.

Responsibilities:

- Take OCR markdown.
- Use existing schema from `build_question_schema(...)`.
- Call the configured structuring LLM.
- Return `{ "questions": [...] }`.

### 4. Add `MistralOcrMarkdownExtractor`

Interface:

```py
class MistralOcrMarkdownExtractor:
    def extract_page(self, page_bytes: bytes) -> dict:
        ...

    def extract(self, pdf_bytes: bytes) -> list[dict]:
        return merge_page_payloads(
            self.extract_page(page_bytes)
            for page_bytes in split_pages(pdf_bytes)
        )
```

### 5. Wire into LangGraph behind an explicit experiment flag

Avoid changing default production behavior.

Possible env var:

```text
EXTRACTION_PIPELINE=gemini_native_pdf | mistral_ocr_markdown
```

or command option:

```bash
python manage.py drain_ingestion_jobs --extractor=mistral-ocr
```

For the POC, a separate management command is also acceptable.

### 6. Compare output quality

For the same previous-year paper/sample pages, compare:

- OCR markdown quality
- number of questions extracted
- malformed payload count
- duplicate count
- parse quality distribution
- chapter tagging usefulness
- source selector registration

## Scope exclusions for first POC

Do not solve these yet:

- diagram cropping
- image placeholders
- exact source page number
- answer extraction
- marking scheme extraction
- perfect chapter tagging
- Hindi translation
- full production feature flag UX

## Success criteria

The POC is successful if:

1. Mistral OCR returns readable markdown for a previous-year paper PDF.
2. The structuring LLM converts that markdown into valid question payloads.
3. `merge_page_payloads(...)` accepts the payloads.
4. `Ingestor.ingest_extracted(...)` persists questions without custom persistence code.
5. Persisted questions are linked to an `IngestionJob`.
6. `/api/bank/sources/` shows the uploaded paper as `upload:<job_id>`.
7. The extracted questions are usable enough for manual review in the bank.

## Experimental issues to create

Suggested issue breakdown:

1. **Run Mistral OCR standalone POC on previous-year paper**
   - Use `backend/scripts/mistral_ocr_poc.py`.
   - Capture OCR markdown and structured payload artifacts.
   - Do not persist initially.

2. **Persist OCR-structured questions through existing ingestor**
   - Run POC with `--persist`.
   - Verify `Question` rows and `IngestionJob` linkage.
   - Verify `/api/bank/sources/` includes `upload:<job_id>`.

3. **Extract reusable Mistral OCR client and markdown structurer**
   - Move POC transport/structuring code into reusable modules.
   - Keep the existing question schema and ingestion tail.

4. **Wire Mistral OCR extractor into LangGraph behind experiment flag**
   - Add `MistralOcrMarkdownExtractor`.
   - Keep production default as Gemini/native-PDF.
   - Run through existing `drain_ingestion_jobs` flow or a dedicated experimental command.

5. **Evaluate extraction quality vs current Gemini path**
   - Compare count, correctness, malformed rows, parse quality, and source selector behavior.
