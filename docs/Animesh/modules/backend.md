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
| `models.py` | `Section`, `QuestionType`, `CognitiveLevel`, `Chapter`, `Question`. |
| `serializers.py` | `QuestionSerializer` (no answer), `QuestionWithAnswerSerializer`, `ChapterSerializer`. |
| `views.py` | `metadata` (enums), `chapters` (list). |
| `urls.py` | `/api/bank/metadata/`, `/api/bank/chapters/`. |
| `policy.py` | `answer_visible(user)` — single rule for who sees answer keys. |
| `admin.py` | Django admin for Question + Chapter. |
| `management/commands/seed_questions.py` | Demo seed: school + teacher + ~11 sample questions across chapters and levels. |
| `migrations/0003_seed_chapters.py` | Data migration seeding the 13 NCERT Cl.10 Science chapters. |

## `papers/`

The paper-assembly pipeline.

| File | Purpose | Seam? |
|---|---|---|
| `blueprint.py` | `BlueprintEngine`, `PaperSpec`, `Slot`, three presets. | ✅ |
| `selection.py` | `SelectionEngine`, `SelectionInput`, `SelectionResult`, `SelectionReport`, `CandidatePool`, difficulty profiles. | ✅ |
| `assembler.py` | `PaperAssembler` — coordinator. `_build_plan` → `_select` → `_persist`. | |
| `models.py` | `Paper` (with `report` JSON), `PaperQuestion`. | |
| `serializers.py` | `AssembleRequestSerializer` (input contract), `PaperSerializer`. | ✅ |
| `views.py` | `AssemblePaperView`, `PaperDetailView`, `PaperPdfView`. | |
| `urls.py` | `/api/papers/...` routes. | |
| `layout.py` | `PaperLayout`, `paper_to_layout()`. PDF renderer's input shape. | ✅ |
| `pdf.py` | `render_paper_pdf(layout) → bytes`. ReportLab renderer. | |

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
2. `papers/blueprint.py` (the smallest engine; sets the seam shape).
3. `papers/selection.py` (the algorithm + how it tests).
4. `papers/assembler.py` (how they compose).
5. `papers/views.py` + `serializers.py` (the HTTP surface).
6. `papers/layout.py` + `pdf.py` (rendering).
