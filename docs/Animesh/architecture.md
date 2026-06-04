# Architecture

How the question paper generator hangs together. Read this first if you're new to the codebase.

## Stack

- **Backend**: Django 5 + Django REST Framework. Postgres (also backs the Django cache via `DatabaseCache`).
- **Frontend**: Vite + React 18 + TypeScript. Tailwind. shadcn-style UI primitives.
- **Dev**: Docker Compose (`docker-compose.yml`) runs db, web, frontend together.

## The paper-assembly pipeline

```
HTTP POST /api/papers/assemble
        │
        ▼
AssemblePaperView           ← validates payload (AssembleRequestSerializer)
        │
        ▼
PaperAssembler.assemble()   ← coordinator: build plan → select → persist
        │
        ├──▶ BlueprintEngine.build(preset)     → PaperSpec (ordered Slots, OR-groups)
        │
        ├──▶ SelectionEngine.select(input)     → SelectionResult
        │           │
        │           ├──▶ _fetch_candidates()   → CandidatePool (one query per bucket)
        │           └──▶ _select_from_pool()   → pure allocator (chapter weights + cog mix)
        │
        └──▶ _persist()                        → Paper + PaperQuestion rows + report
        │
        ▼
PaperSerializer            → JSON {id, title, total_marks, report, items}
```

Then, when the teacher hits "Download PDF":

```
HTTP GET /api/papers/{id}/pdf/
        │
        ▼
PaperPdfView               ← cache lookup by paper id
        │
        ├──▶ paper_to_layout(paper)    → PaperLayout (flat, ORM-free)
        └──▶ render_paper_pdf(layout)  → bytes
```

## Seams (where behaviour can be altered without editing in place)

| Seam | Defined by | Why it exists |
|---|---|---|
| `PaperSpec` | `papers.blueprint` | Decouples "what kind of paper" (preset) from "what questions go in it" (selection). Add a new preset → no selection-engine change. |
| `SelectionInput` / `SelectionResult` | `papers.selection` | Decouples teacher inputs (chapters, weights, difficulty) from algorithm and persistence. |
| `CandidatePool` (internal) | `papers.selection` | Decouples ORM fetch from pure allocation. Algorithm is testable with hand-built pools, no DB. |
| `SelectionReport` | `papers.selection` | Single source of truth for the report shape — persisted on Paper, returned in API responses, mirrored in TS types. |
| `PaperLayout` | `papers.layout` | Decouples PDF rendering from ORM. Renderer needs no model imports. |
| `AssembleRequestSerializer` | `papers.serializers` | Declarative input contract for `POST /papers/assemble`. New fields accrete here. |
| `useCoverageForm` | `frontend/hooks` | Owns the teacher's form state and builds the assemble payload. Page never constructs payloads inline. |

## Slice progression (vertical features)

The product ships in vertical slices defined in `docs/PLAN.md`. Each slice cuts through model → engine → API → UI → tests so the system is always demoable.

| Slice | Status | What it adds |
|---|---|---|
| 1 — Walking skeleton | done | Auth, Question bank, fixed paper, PDF download. |
| 2 — Blueprint + presets | done | `BlueprintEngine`, `PaperSpec`, OR-groups, board/half_yearly/unit_test presets. |
| 3 — Selection engine | this PR | Chapter taxonomy + cognitive level + `SelectionEngine` + teacher form. |
| 4 — Ingestion A (PDF parse) | next | Extract questions from `content/science_*` PDFs; auto-tag chapter + level. |
| 5 — Ingestion B | upcoming | Diagrams, marking scheme, de-dup, human verification. |
| 6 — Review / edit / approve | upcoming | Provenance on `PaperQuestion`. |
| 7 — Async generation | upcoming | Postgres-backed jobs drained by a cron management command (no Celery/Redis — see #105), progress. |
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
