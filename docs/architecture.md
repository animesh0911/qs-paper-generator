# Architecture

How the question paper generator hangs together. Read this first if you're new to the codebase.

> Visual diagrams (Mermaid): [`architecture-diagrams.md`](architecture-diagrams.md).

## Stack

- **Backend**: Django 5 + Django REST Framework. Postgres. Celery + Redis (workers not exercised until Slice 7).
- **Frontend**: Vite + React 18 + TypeScript. Tailwind. shadcn-style UI primitives.
- **Dev**: Docker Compose (`docker-compose.yml`) runs db, redis, web, worker, frontend together.

## The paper-assembly pipeline

```
HTTP POST /api/papers/assemble
        │
        ▼
AssemblePaperView           ← validates payload (AssembleRequestSerializer)
        │
        ▼
PaperBuilder.assemble()     ← single entry: build template → pick → persist → map document
        │
        ├──▶ TemplateBuilder.build(preset)     → PaperTemplate (Preset + ordered Slots)
        │
        ├──▶ QuestionPicker.select(opts)       → FilledTemplate
        │           │
        │           ├──▶ _fetch_candidates()   → QuestionPool (one query per bucket)
        │           └──▶ _select_from_pool()   → pure allocator (chapter weights + cog mix)
        │
        ├──▶ _persist()                        → Paper + PaperQuestion rows + report
        │
        └──▶ PaperDocumentBuilder.build()      → PaperDocumentV1 dict (saved on Paper.document)
        │
        ▼
AssemblyResult{paper, document}  →  Response(document)
```

Then, when the teacher hits "Download PDF":

```
HTTP GET /api/papers/{id}/pdf/
        │
        ▼
PaperPdfView               ← cache lookup by paper id
        │
        └──▶ render_paper_pdf(paper.document)  → bytes
                (renderer reads PaperDocumentV1 directly — no PaperLayout)
```

## The ingestion pipeline (Slice 4)

```
HTTP POST /api/bank/ingest/   (admin-only, multipart PDF)
        │
        ▼
Ingestor.ingest(pdf_bytes)
        │
        ├──▶ Parser.parse(pdf_bytes)       → str            (default: PdfplumberParser)
        ├──▶ strip_hindi(text)             → str            (pure)
        ├──▶ segment_questions(text)       → list[dict]     (pure)
        ├──▶ Tagger.tag(raw, chapters)     → list[dict]     (default: LLMTagger)
        │           │
        │           └──▶ LLMClient.complete(prompt)         (default: make_llm_client())
        │                       ↓
        │                   LiteLLMClient (ai_services.llm)
        │
        └──▶ Question.objects.bulk_create(... verified=False)
        │
        ▼
IngestResult{created: N}
```

## Seams (where behaviour can be altered without editing in place)

| Seam | Defined by | Why it exists |
|---|---|---|
| `Preset` | `papers.template` | Bundles slot layout + display metadata (template_name, exam_type, duration). Adding a preset is one literal. |
| `PaperTemplate` | `papers.template` | Decouples "what kind of paper" (preset) from "what questions go in it" (picking). |
| `PaperOptions` / `FilledTemplate` | `papers.picker` | Decouples teacher inputs (chapters, weights, difficulty) from algorithm and persistence. |
| `QuestionPool` (internal) | `papers.picker` | Decouples ORM fetch from pure allocation. Algorithm is testable with hand-built pools, no DB. |
| `CoverageReport` | `papers.picker` | Single source of truth for the coverage report shape. |
| `PaperDocumentV1` | `papers.document` | Single render-time contract. Frontend and PDF renderer both consume the same dict from `Paper.document`. |
| `Parser` / `Tagger` | `bank.ingestor` | Two adapter seams of the Ingestor. Tests inject `StubParser` / `StubTagger`. |
| `LLMClient` | `ai_services.llm` | Provider-agnostic LLM call (`complete(prompt) → str`). One `LiteLLMClient` adapter over `litellm.completion` spans OpenAI / Anthropic / Gemini. Model chosen via `LLM_MODEL` (or `LLM_PROVIDER` fallback). |
| `AssembleRequestSerializer` | `papers.serializers` | Declarative input contract for `POST /papers/assemble`. New fields accrete here. |
| `useCoverageForm` | `frontend/hooks` | Owns the teacher's form state and builds the assemble payload. |

## Slice progression (vertical features)

The product ships in vertical slices defined in `docs/PLAN.md`. Each slice cuts through model → engine → API → UI → tests so the system is always demoable.

| Slice | Status | What it adds |
|---|---|---|
| 1 — Walking skeleton | done | Auth, Question bank, fixed paper, PDF download. |
| 2 — Blueprint + presets | done | `TemplateBuilder`, `PaperTemplate`, OR-groups, board/half_yearly/unit_test presets. |
| 3 — Selection engine | done | Chapter taxonomy + cognitive level + `QuestionPicker` + teacher form. |
| 3b — Document contract | done | `PaperDocumentV1`, draft/approve lifecycle, document-driven PDF rendering. |
| 4 — Ingestion A (PDF parse) | done | `Ingestor` + `Parser`/`Tagger` adapters + provider-agnostic `LLMClient`. Auto-tags chapter + cognitive level. |
| 5 — Ingestion B | next | Diagrams, marking scheme, de-dup, human verification. |
| 6 — Review / edit / approve | upcoming | Provenance on `PaperQuestion`. |
| 7 — Async generation | upcoming | Celery jobs, progress. |
| 8 — Grounded gen + verifier | upcoming | LLM with HITL. |
| 9 — Export suite | upcoming | DOCX, answer key, branding. |
| 10 — Cross-paper usage | upcoming | Freshness tracking. |

## Where to find things

- Domain glossary → [`CONTEXT.md`](../CONTEXT.md)
- Coding standards → [`docs/coding-standards.md`](./coding-standards.md)
- Per-module overviews → [`docs/modules/backend.md`](./modules/backend.md), [`docs/modules/frontend.md`](./modules/frontend.md)
- Operating reference (URLs, commands, env) → [`docs/commands.md`](./commands.md)
- Product requirements → [`docs/PRD.md`](./PRD.md)
- Slice plan → [`docs/PLAN.md`](./PLAN.md)
