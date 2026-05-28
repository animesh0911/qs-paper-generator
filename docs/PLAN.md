# Question Paper Generator — Product & Build Plan

_CBSE Class 10 Science · MVP · single school · stack-compatible with Apptension SaaS boilerplate_

Last updated: 2026-05-28

---

## 1. Vision

A web tool that lets a school teacher generate a **CBSE Class 10 Science** question paper that
looks and reads like a real board paper. The teacher chooses **which chapters to cover** (with
weighting) and an **overall difficulty**; the system assembles a full board-pattern paper from a
**curated bank of past-paper questions plus textbook-grounded AI-generated questions**, lets the
teacher **review/edit/approve** a draft, and exports a **print-ready PDF + editable DOCX + answer
key** on the school's branding.

It is an **assistant**, not an oracle: the teacher stays in control and accountable.

---

## 2. Locked decisions (the design tree)

| # | Decision | Choice |
|---|----------|--------|
| 1 | MVP scope | **CBSE Class 10 Science only** |
| 2 | Question engine | **Hybrid**: curated bank from past papers + textbook-grounded generation |
| 3 | Review model | **Assistive draft** → teacher reviews / edits / regenerates / approves |
| 4 | Language | **English only** (architected so language is a tag → bilingual later) |
| 5 | Paper types | **Full 80-mark board blueprint + presets** (half-yearly, unit test, custom marks) |
| 6 | Syllabus input | **Chapter-level selection + optional per-chapter weight** |
| 7 | Difficulty | **Simple teacher slider** (Easy/Balanced/Hard) → mapped to **Bloom/CBSE cognitive tags** internally |
| 8 | Validation | **Verify-and-flag**: independent solver model must agree; show confidence + textbook citation; **numericals & diagram items are bank-only in v1** |
| 9 | Diagrams | **Reuse cropped images** from source PDFs; **no new diagrams generated**; tables may be generated as text |
| 10 | Bank ingestion | **AI-assisted extraction + human verification** (Django Admin); ingest **official CBSE marking schemes** for authoritative keys; de-dup overlapping sets |
| 11 | Output | **Print-ready PDF + editable DOCX + separate answer key** |
| 12 | Layout/branding | **CBSE-style structure & typography, with SCHOOL branding** (no board impersonation); per-school header config |
| 13 | Tenancy | **Single-tenant MVP**, but leave seams: nullable `school_id` columns, config in a settings row, no global-user assumptions |
| 14 | Roles | **Single teacher role**, no approval workflow |
| 15 | Repetition | **No duplicates within a paper**; **track question usage across papers** and prefer less-recently-used; teacher can override |
| 16 | Stack | **Stack-compatible minimalism** with Apptension boilerplate (see §7) |

**Assumed defaults (override if needed):** LLM = Claude API (capable model for generation + a
*separate* call as verifier/solver); auth = Django email/password (no SSO); hosting =
Render/Railway/Fly + managed Postgres/Redis; Docker from day one.

---

## 3. The CBSE Class 10 Science blueprint (80 marks, 39 Q)

| Section | Questions | Type | Marks each | Section marks | Answer length |
|---------|-----------|------|-----------|---------------|----------------|
| A | Q1–20 | MCQ (4 options) | 1 | 20 | — |
| B | Q21–26 | Very Short Answer | 2 | 12 | 30–50 words |
| C | Q27–33 | Short Answer | 3 | 21 | 50–80 words |
| D | Q34–36 | Long Answer | 5 | 15 | 80–120 words |
| E | Q37–39 | Source/case-based (sub-parts) | 4 | 12 | — |
| **Total** | **39** | | | **80** | 3 hours |

Internal choices appear in some questions ("OR"); no overall choice. Encode this as a **declarative
blueprint config** so presets are just scaled variants reusing the same section grammar.

---

## 4. System architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite + Tailwind + shadcn/ui)              │
│  - Paper builder wizard (chapters+weights, difficulty, preset)│
│  - Draft review/edit screen (per-question: source, key,       │
│    confidence, swap/regenerate/edit)                          │
│  - Export (PDF / DOCX / answer key)                           │
└───────────────┬─────────────────────────────────────────────┘
                │ REST (DRF) + React Query
┌───────────────▼─────────────────────────────────────────────┐
│  Backend (Django + DRF)                                       │
│  apps: accounts · bank · papers · generation · rendering      │
│  - Django Admin = bank verification & taxonomy management     │
└───────┬───────────────────────────┬─────────────────────────┘
        │                           │
┌───────▼────────┐         ┌────────▼─────────────────────────┐
│ PostgreSQL      │         │ Celery workers (Redis broker)     │
│ - syllabus tree │         │ - paper assembly job              │
│ - question bank │         │ - generation + verifier pipeline  │
│ - papers/usage  │         │ - PDF/DOCX render job             │
│ - school config │         └────────┬─────────────────────────┘
└─────────────────┘                  │
                              ┌───────▼────────┐   ┌──────────────┐
                              │ Claude API     │   │ Object storage│
                              │ gen + verifier │   │ diagram crops │
                              └────────────────┘   │ exported files│
                                                    └──────────────┘
```

---

## 5. Data model (core entities)

- **School** — branding, header config, settings. (`id` referenced as nullable `school_id` elsewhere.)
- **User** — teacher; belongs to a school.
- **Chapter** — canonical Class 10 Science syllabus node (name, subject-strand P/C/B, order).
  _(Sub-topics deferred per decision #6.)_
- **Question** — the heart of the bank:
  - `text`, `options` (for MCQ), `answer`, `marking_scheme`
  - `section_type` (A/B/C/D/E), `marks`
  - `chapter_id`, `cognitive_level` (Remember/Understand/Apply/Analyse)
  - `difficulty` (derived band), `language` (`en`)
  - `source` (`bank` | `generated`), `source_ref` (year/set/QP-code or textbook page citation)
  - `has_diagram`, `diagram_image_ref`
  - `is_numerical`, `verified` (human/auto), `verifier_confidence`
  - `internal_choice_group` (for OR pairs)
- **Paper** — `school_id`, `created_by`, `preset`, `chapters+weights` (JSON), `difficulty_profile`,
  `status` (draft/approved), `blueprint` snapshot, list of chosen questions.
- **PaperQuestion** — join row preserving order, section, chosen-vs-OR, and any teacher edits
  (so edits don't mutate the shared bank).
- **QuestionUsage** — `(question_id, paper_id, used_at)` → powers cross-paper exposure tracking.

---

## 6. Two pipelines

### 6a. Bank ingestion (offline, one-time + per new year)
1. **Parse PDF** (vision/LLM) → split English from Hindi, segment into questions, capture
   section/marks/options, crop diagrams to images.
2. **Match official marking scheme** → attach authoritative answer/marking scheme.
3. **Auto-tag** chapter + cognitive level + difficulty band.
4. **De-duplicate** across sets within a year (CBSE rotates questions).
5. **Human verification** in Django Admin → correct tags/keys, approve. Only `verified` questions
   are eligible for papers.

### 6b. Paper generation (online, Celery job)
1. **Resolve blueprint** from preset → required questions per section/marks/cognitive mix.
2. **Translate difficulty slider** → target cognitive-level distribution per section.
3. **Allocate** questions to chapters by weight.
4. **Bank-first selection**: pull verified bank questions matching (section, chapter, cognitive
   level), excluding recently-used (per `QuestionUsage`); never duplicate within paper.
   Numerical/diagram slots are **bank-only**.
5. **Generate to fill gaps**: for remaining text slots, generate grounded in NCERT textbook →
   produce question + answer + page citation.
6. **Verify** each generated item: a *separate* solver call must independently produce the same
   answer; mismatch → drop or flag low-confidence.
7. **Assemble** draft with internal-choice ("OR") pairs where the blueprint expects them.
8. **Return `PaperDocumentV1`** — section-wise, slot-based JSON with selected + alternate questions, per `contracts/v1_contract.md`. Frontend renders into BlockNote editor.
9. On **approve** → render PDF + DOCX + answer key; record `QuestionUsage`.

---

## 7. Tech stack & repo layout (boilerplate-compatible)

**Keep identical to Apptension (so code/concepts transfer):** Django 5.2 + DRF + Celery + Redis +
PostgreSQL; React 19 + Vite + TypeScript + Tailwind + shadcn/ui; Docker.

**Skip for v1 (add later by adopting boilerplate modules):** GraphQL (use DRF REST + React Query),
Nx (plain folders), AWS CDK (simple PaaS deploy), Stripe, Contentful, SSO/passkeys.

```
qs_paper_generator/
├─ backend/                 # Django project
│  ├─ accounts/  bank/  papers/  generation/  rendering/
│  ├─ config/               # settings, celery app
│  └─ Dockerfile
├─ frontend/                # React + Vite + Tailwind + shadcn/ui
│  └─ Dockerfile
├─ docker-compose.yml       # web, worker, postgres, redis
├─ data/                    # source PDFs + textbook (gitignored if large)
└─ PLAN.md
```

**Extensibility seams (cheap now, save weeks later):** nullable `school_id` on core tables;
school-specific config in a `School`/settings row, not in code; DRF REST endpoints (survive a later
GraphQL addition); shadcn UI (copy-paste compatible); Docker (matches their containerization).

---

## 8. Phased roadmap

**Phase 0 — Foundations (skeleton)**
- Repo, docker-compose (web/worker/postgres/redis), Django + React + Tailwind/shadcn, basic auth.
- Seed the **canonical Class 10 Science chapter taxonomy**.
- Encode the **blueprint config** + the board preset.

**Phase 1 — Bank (the foundation of trust)**
- Build the ingestion pipeline on the 2024–2026 PDFs + marking schemes.
- Django Admin verification tool; tag + de-dup; reach a clean verified bank.

**Phase 2 — Bank-only generator (prove format fidelity)**
- Selection engine (blueprint + chapter weights + difficulty + no-repeat).
- `POST /api/papers/assemble` returns `PaperDocumentV1` (section-wise, slot-based JSON per `contracts/v1_contract.md`).
- BlockNote-based frontend editor consumes the document: teachers review, swap slots, and edit questions.
- PDF + DOCX + answer-key renderer with school branding.
- _Milestone: a teacher can produce a real, board-faithful paper entirely from vetted questions._

**Phase 3 — Grounded generation + verifier**
- Textbook-grounded generation for text slots; independent-solver verification; provenance +
  confidence in the UI. Numericals/diagrams stay bank-only.

**Phase 4 — Polish & pilot**
- Presets (half-yearly/unit test/custom), usage tracking UI, error handling, deploy, pilot with the
  client; gather teacher feedback.

**Later (post-MVP):** bilingual (Hindi), more subjects, multi-tenant + billing (graduate into the
Apptension boilerplate), programmatic diagram generation, approval workflows.

---

## 9. Key risks & mitigations

| Risk | Mitigation |
|------|------------|
| Generated answer key is confidently wrong | Independent verifier must agree; textbook citation; human review; risky types bank-only |
| Finite bank → repetition / staleness | Usage tracking + less-recently-used preference; generation fills gaps |
| PDF parsing errors poison the bank | Human verification pass; only `verified` questions are eligible |
| Diagram fidelity | Reuse original cropped images; no AI-drawn figures in v1 |
| Syllabus drift (CBSE rationalization) | Taxonomy is data, not code; admin-editable |
| Scope creep into multi-tenant/bilingual too early | Explicit seams + phased roadmap keep them as additive later steps |

---

## 10. Open items to confirm with the client (the school)

- Medium of instruction = English? (confirms decision #4)
- Which exact NCERT chapters are *in syllabus* for their current academic year?
- Branding assets: logo, school name, standard exam header text/instructions.
- Typical paper needs beyond the board pattern (unit-test marks/duration) → tune presets.
- Do they want the **answer key/marking scheme** for every paper, or only on request?
