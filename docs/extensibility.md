# Extensibility reality — beyond CBSE Class 10 Science

**Status:** current-state assessment (2026-06-06). Not a plan or a decision — it
documents *where* the "CBSE / Class 10 / Science" reality is wired into the code
today, so a future multi-curriculum effort can be scoped against facts rather
than guesses. No code is proposed here.

The question this answers: how far is the codebase from generating papers for
*all CBSE subjects and classes (1–12)*, and after that for *other boards (ICSE,
state boards, IB, Cambridge)* — purely from a code-structure standpoint.

---

## 1. The core finding: one collapsed dimension

A fully general system needs four taxonomy axes — **board × grade × subject ×
syllabus** — plus a **paper pattern** (blueprint) that hangs off a chosen
(board, grade, subject). All five concepts are *present* in the code, but three
of the four axes are collapsed to compile-time constants, not data:

| Axis | Today | Where it lives |
|---|---|---|
| Board | implicit constant "CBSE" | nowhere — assumed everywhere |
| Grade | implicit constant "Class 10" | extraction prompt, renderer strings |
| Subject | implicit constant "Science" | prompt, renderer; sub-divided into Bio/Chem/Phys |
| Syllabus (chapters) | a flat closed 13-row list | `bank/migrations/0003_seed_chapters.py` |
| Paper pattern | 3 hardcoded Python slot-builders | `papers/template.py` |

`Chapter` (`backend/bank/models.py:107`) has **no FK to board/grade/subject** —
it *is* the Class-10-Science syllabus by assumption. Introducing a `Curriculum`
(or `Syllabus`) entity keyed by `(board, grade, subject)`, hanging `Chapter` off
it, and scoping `Preset`/blueprint to it is the single structural change
everything else depends on.

---

## 2. Backend — load-bearing CBSE assumptions (ranked)

The mechanical pipeline (extract → tag → bank → pick → assemble → render) was
built with real seams and is largely subject-agnostic. The CBSE-Science reality
concentrates in a small number of named constants:

1. **`MARKS_TO_SECTION = {1:"A", 2:"B", 3:"C", 4:"E", 5:"D"}`**
   (`backend/bank/ingestor.py:58`) — the single most overfit line. It encodes
   "mark value *is* the section key", a CBSE-Science-specific bijection. Drives
   section derivation at ingest, the `marks_section_mismatch` guardrail
   (`backend/bank/guardrails.py:240`), and is implicitly assumed by every
   slot-builder. In Math/English or any other board a 5-mark question is not
   "Section D". The general form inverts this: the **blueprint** declares
   section→(qtype, marks); ingest reads section from the paper.

2. **`Section` as a `TextChoices` enum A–E** (`backend/bank/models.py:24`) —
   baked into the DB schema, picker buckets, guardrails, document builder
   (`backend/papers/document.py:19`), and renderer. Other boards do not use A–E.
   Because it is an *enum*, not a *row*, changing section structure per
   curriculum is a migration + code change, not config. This is the rigid one.

3. **Blueprint constants** — `_BLUEPRINT_SECTIONS = {"A":20,"B":6,…}` /
   `_BLUEPRINT_TOTAL = 39` (`backend/bank/guardrails.py:71`) and the 20/6/7/3/3
   slot-builders (`backend/papers/template.py:35`). Pure CBSE-Science-board
   shape. Somewhat isolated, but the guardrail blueprint is a module constant,
   not tied to the selected preset.

4. **The extraction prompt** (`backend/bank/ingestor.py:319`) — literally
   `"CBSE Class 10 Science board paper"` plus **Hindi/English bilingual
   filtering** and a Bio/Chem/Phys mental model. Math (equation-dense, no
   subject_area), English (comprehension passages, essays), and primary classes
   (picture/oral) need materially different prompts. This is per-subject content,
   not a constant.

5. **`SubjectArea` = Biology/Chemistry/Physics** (`backend/bank/models.py:56`) —
   ironically the best evidence a real subject dimension is needed: "Science" is
   already a composite of three sub-subjects, hardcoded as an enum with the
   chapter-number ranges baked into `CONTEXT.md`. Meaningless for Math/English.

6. **Renderer strings** — `"Class 10 — Science"` and the General Instructions
   block are hardcoded (`backend/papers/pdf.py:98`,
   `backend/papers/document.py:181`). Cosmetic, easy, but currently constants.

### What already generalizes (backend)

- **`Extractor` / `LLMClient` / `DiagramCropper`** (`backend/bank/ingestor.py`)
  are clean adapter seams; nothing about them is CBSE-specific.
- **`build_question_schema(chapter_slugs)`** (`backend/bank/ingestor.py:292`)
  already *injects* the chapter list into the Gemini response schema per call —
  the one axis already data-driven end to end.
- **`resolve_chapter_slug`** (`backend/bank/guardrails.py:92`) takes
  `canonical_slugs` as an argument; works for any syllabus unchanged.
- **`Preset`** (`backend/papers/template.py:82`) is the right abstraction shape
  ("adding a preset = one literal in `_PRESETS`") — it just needs to be
  data-driven and curriculum-scoped.
- The ingestion-job + cron-drain + provenance + dedup +
  `parse_quality`/`review_flags` machinery is fully reusable as-is.

---

## 3. Frontend — agnostic render path, single-curriculum selection path

The frontend is **further along than the backend on extensibility**, with a
clear asymmetry:

**The render path is curriculum-agnostic by contract.** The editor and print
surfaces iterate `document.paper.sections` dynamically and never hardcode A–E or
question types. The Zod contract
(`frontend/src/types/paper-document.schema.ts`) treats `board` (line 216),
`subject`, `classLevel`, `examType`, `subjectArea`, and section
`title`/`subtitle`/`instructions` as **generic strings**, not enums, with
`.passthrough()` throughout. There is no qtype hardcoding in the editor
components.

**There is a deliberate, forward-looking extensibility seam:** the
format-renderer registry (`frontend/src/lib/paper-format-renderers.ts`) keyed by
contract `format.id`, which **fails loudly on unknown formats** "instead of being
interpreted as CBSE by accident". Exactly the right shape. Only one renderer is
registered today: `cbse_science_class_10_board_compact_2026_v1`
(`frontend/src/lib/paper-format-renderers/cbse-compact-renderer.ts`).

**The selection (input) path is single-curriculum by omission.** `AssembleRequest`
(`frontend/src/types/index.ts`) carries only `difficulty` + `chapter_slugs` +
`weights` (plus an unused optional `preset?`/`title?`). The coverage form
(`frontend/src/components/coverage/coverage-form/coverage-form.component.tsx`,
`frontend/src/hooks/useCoverageForm.hook.ts`) has **no board / grade / subject /
exam-type / preset selector** — it just `fetchChapters()` (which returns the
backend's single 13-chapter taxonomy) and lets the teacher pick difficulty,
chapters, and weights. `DIFFICULTIES = ['easy','standard','hard']` is hardcoded
but generic.

Net: the frontend rendering layer is ready for multiple curricula; the frontend
has **no UI concept of choosing one** because there is only one to choose.

---

## 4. Effort gradient

**Tier 1 — other CBSE subjects & upper classes (9–12 Math, SST, English, …).**
A refactor-then-data exercise, not a rewrite. Introduce the `Curriculum` entity;
scope `Chapter`/`Preset`/blueprint to it; invert `MARKS_TO_SECTION` into
per-blueprint section definitions; author per-subject extraction prompts; add a
curriculum/preset selector to the coverage form. CBSE is fairly uniform on the
A–E section idea across upper-class subjects, so the `Section` enum survives
longer here than feared. **Sharpest edges within CBSE:** primary classes (1–5)
have no formal sections/marks scheme, breaking the section/marks model entirely;
and Math/English diverge most from the Science prompt and paper logic.

**Tier 2 — other Indian boards (ICSE, state boards).** Now `Section`-as-enum and
the marks↔section coupling break for real. Section *structure itself* must become
data (rows scoped to curriculum), and the guardrail blueprint must read from the
selected preset. Larger, but the contract and pipeline still hold, and the
frontend render path already accepts arbitrary sections/strings.

**Tier 3 — international (IB, Cambridge).** Closer to a second product than a
config change. IB's Paper 1/2/3 + command terms + criterion mark-bands, or
Cambridge's structure, do not map onto "Sections A–E, marks-drive-everything".
The `PaperDocumentV1` contract itself — fundamentally section-based — would need
generalizing. Ingestion and bank layers still reuse cleanly; the
template/picker/blueprint/contract layer largely does not.

---

## 5. Bottom line

The repo is **better positioned than "tightly fitted" suggests**. The expensive
parts — the I/O seams (extractor, cropper, LLM client, dynamic chapter-schema
injection, preset abstraction) and the frontend render path / renderer registry —
were deliberately built as injection points. The work is **not spread
everywhere**; it concentrates in **one missing entity** (the curriculum/syllabus
dimension) and **~6 named backend constants** that should become that entity's
attributes, plus a thin selection-UI gap on the frontend.

Get the `Curriculum` axis in and invert `MARKS_TO_SECTION`, and "all CBSE
subjects/classes" becomes mostly data-entry + prompt-authoring + a UI selector.
International boards are a genuine re-modeling of the section/blueprint/contract
layer and should be scoped as a separate phase rather than assumed to fall out of
the same abstraction.
