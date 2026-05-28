# Backend modules

Per-module overview. Source is authoritative; this is a map. Open the file and read its module docstring for the full story.

## `accounts/`

Custom user model + auth endpoints.

| File | Purpose |
|---|---|
| `models.py` | `School` and `User` (email-based auth). |
| `serializers.py` | Login, register, user payloads. |
| `views.py` | Auth endpoints. |
| `urls.py` | `/api/auth/...` routes. |

## `bank/`

The question bank: Questions, Chapters, taxonomy endpoints.

| File | Purpose |
|---|---|
| `models.py` | `Section`, `QuestionType`, `CognitiveLevel`, `Chapter`, `Question` (with `verified` flag). |
| `serializers.py` | `QuestionSerializer` (no answer), `QuestionWithAnswerSerializer`, `ChapterSerializer`. |
| `views.py` | `metadata` (enums), `chapters` (list), `ingest` (admin-only PDF upload). |
| `urls.py` | `/api/bank/metadata/`, `/api/bank/chapters/`, `/api/bank/ingest/`. |
| `ingestor.py` | `Ingestor` coordinator; `Parser` / `Tagger` Protocols; default adapters `PdfplumberParser` + `LLMTagger`; pure helpers `strip_hindi`, `segment_questions`. |
| `llm.py` | `LLMClient` Protocol + `AnthropicClient` / `OpenAIClient` / `GeminiClient` adapters + `make_llm_client()` factory. |
| `policy.py` | `answer_visible(user)` — single rule for who sees answer keys. |
| `admin.py` | Django admin for Question + Chapter. |
| `management/commands/seed_questions.py` | Demo seed: school + teacher + ~11 sample questions across chapters and levels. |
| `migrations/0003_seed_chapters.py` | Data migration seeding the 13 NCERT Cl.10 Science chapters. |
| `migrations/0004_question_verified.py` | Adds `Question.verified`; backfills existing rows to `True`. |

## `papers/`

The paper-assembly pipeline.

| File | Purpose | Seam? |
|---|---|---|
| `template.py` | `TemplateBuilder`, `PaperTemplate`, `Slot`, `Preset` (bundled metadata), three presets. | ✅ |
| `picker.py` | `QuestionPicker`, `PaperOptions`, `FilledTemplate`, `CoverageReport`, `QuestionPool`, difficulty levels. Filters on `Question.verified=True`. | ✅ |
| `builder.py` | `PaperBuilder` + `AssemblyResult`. Single `assemble(...)` builds template → picks → persists → maps document. | |
| `models.py` | `Paper` (with `report` + `document` JSON, `status` draft/approved), `PaperQuestion`. | |
| `document.py` | `PaperDocumentBuilder` — maps domain objects to `PaperDocumentV1` dict. Reads preset metadata from `template.preset`. | ✅ |
| `serializers.py` | `AssembleRequestSerializer` (input contract), `PaperSerializer`. | ✅ |
| `views.py` | `AssemblePaperView`, `PaperDetailView` (GET/PATCH), `PaperApproveView`, `PaperPdfView`. | |
| `urls.py` | `/api/papers/...` routes. | |
| `pdf.py` | `render_paper_pdf(document) → bytes`. Reads `PaperDocumentV1` dict directly — no model imports. ReportLab. | |

## `config/`

Django project root.

| File | Purpose |
|---|---|
| `settings.py` | Settings (DB, Redis, DRF, CORS). |
| `urls.py` | Top-level URL routing. |
| `celery.py` | Celery app (unused until Slice 7). |
| `asgi.py` / `wsgi.py` | Standard Django entry points. |

## Reading order for a new dev

1. `CONTEXT.md` (domain vocabulary).
2. `papers/template.py` (the smallest engine; sets the seam shape).
3. `papers/picker.py` (the algorithm + how it tests).
4. `papers/builder.py` + `document.py` (how the assembly composes).
5. `papers/views.py` + `serializers.py` (the HTTP surface).
6. `papers/pdf.py` (rendering directly from `PaperDocumentV1`).
7. `bank/ingestor.py` + `bank/llm.py` (the ingestion pipeline + LLM seam).
