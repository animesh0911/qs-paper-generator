# PRD: Question Paper Generator — CBSE Class 10 Science (MVP)

## Problem Statement

Teachers at a CBSE-affiliated school spend hours hand-crafting exam papers (unit tests,
half-yearlies, prelims) that must follow the rigid CBSE Class 10 Science board pattern. They have to
recall the blueprint, hunt for appropriate questions across years of past papers and the textbook,
balance chapter coverage and difficulty, write an answer key, and format everything to look like a
real board paper — every single time. It is slow, repetitive, error-prone, and the output quality
depends entirely on the individual teacher's effort and memory.

## Solution

A web application where a teacher selects which chapters to cover (with optional weighting) and an
overall difficulty, picks a paper preset (full board pattern or a shorter test), and receives a
ready-to-review draft paper that matches the CBSE Class 10 Science format. The draft is assembled
from a curated bank of real past-paper questions plus textbook-grounded AI-generated questions. The
teacher reviews the draft — seeing each question's source (real past question vs. AI-generated), its
answer key, and a confidence indicator — and can swap, regenerate, or edit any question before
approving. On approval, the system exports a print-ready PDF, an editable DOCX, and a separate answer
key/marking scheme, all carrying the school's own branding. The tool is an assistant: the teacher
remains in control and accountable for the final paper.

## User Stories

1. As a teacher, I want to log in securely, so that only authorized staff can create papers.
2. As a teacher, I want to start a new paper from a preset (full 80-mark board pattern, half-yearly, unit test, or custom marks), so that the structure matches the exam I'm setting.
3. As a teacher, I want to select which syllabus chapters are included, so that the paper only covers what I've taught.
4. As a teacher, I want to assign an optional weight to each selected chapter, so that I can emphasize certain chapters in the marks distribution.
5. As a teacher, I want to set an overall difficulty (e.g. Easy / Balanced / Hard), so that the paper matches my class's level.
6. As a teacher, I want the system to enforce the CBSE section structure (A: MCQs, B: VSA, C: SA, D: LA, E: case-based) with correct marks and question counts, so that the paper is board-faithful without me memorizing the blueprint.
7. As a teacher, I want the system to generate a complete draft paper automatically, so that I start from a near-finished product instead of a blank page.
8. As a teacher, I want each draft question labeled by source (real past-paper question vs. AI-generated), so that I know which items to scrutinize more closely.
9. As a teacher, I want to see the answer key / marking scheme for every question in the draft, so that I can verify correctness during review.
10. As a teacher, I want AI-generated questions to show a confidence indicator and a textbook citation, so that I can quickly judge whether to trust them.
11. As a teacher, I want to edit the text, options, or answer of any question inline, so that I can fix or tailor anything before finalizing.
12. As a teacher, I want to regenerate or swap out an individual question, so that I can replace one I dislike without rebuilding the whole paper.
13. As a teacher, I want the guarantee that no question repeats within a single paper, so that the paper is clean.
14. As a teacher, I want the system to avoid reusing questions I've used in recent papers, so that successive papers stay fresh.
15. As a teacher, I want to override the freshness preference and intentionally reuse a question, so that I keep control when I want a specific item.
16. As a teacher, I want questions that include diagrams (e.g. ray diagrams, pH scales, Lewis structures) to display their original figure faithfully, so that visual questions are usable.
17. As a teacher, I want to approve the draft when satisfied, so that the system produces final outputs.
18. As a teacher, I want to export a print-ready PDF of the paper, so that I can print and distribute it.
19. As a teacher, I want to export an editable DOCX, so that I can make last-mile tweaks in a word processor.
20. As a teacher, I want a separate answer key / marking scheme document, so that I or a colleague can grade consistently.
21. As a teacher, I want all exports to carry my school's logo, name, and exam header, so that the paper represents my school (not the CBSE board).
22. As a teacher, I want internal "OR" choices to appear where the blueprint expects them, so that the paper mirrors real board papers.
23. As a teacher, I want numerical and diagram-based questions to be drawn from the vetted question bank, so that the riskiest item types are reliable.
24. As a teacher, I want to see how much of each selected chapter's weight was actually satisfied, so that I understand the coverage of the generated paper.
25. As a content administrator, I want to ingest a past-paper PDF and have it parsed into structured question records, so that the bank grows without manual transcription.
26. As a content administrator, I want the ingestion to separate English text from Hindi, so that the English-only bank is clean.
27. As a content administrator, I want diagrams automatically cropped from source PDFs and attached to their questions, so that visual fidelity is preserved.
28. As a content administrator, I want official CBSE marking schemes matched to bank questions, so that answer keys are authoritative.
29. As a content administrator, I want each ingested question auto-tagged with chapter, cognitive level, marks, and section, so that selection has rich metadata.
30. As a content administrator, I want overlapping/duplicate questions across sets de-duplicated, so that the bank isn't bloated with near-identical items.
31. As a content administrator, I want to review and correct every ingested question before it becomes eligible, so that the bank that everything depends on is trustworthy.
32. As a content administrator, I want only verified questions to be usable in generated papers, so that unverified parse output never reaches a teacher.
33. As a content administrator, I want to manage the canonical chapter taxonomy, so that the syllabus stays correct as CBSE rationalizes content.
34. As the system, I want every AI-generated question's answer independently re-derived by a separate solver and required to agree, so that confidently-wrong answer keys are caught before review.
35. As the system, I want to drop or flag generated items whose solver disagrees, so that low-trust items don't silently enter a paper.
36. As a teacher, I want the paper generation to run as a background job with progress feedback, so that the UI stays responsive during a multi-step process.

## Implementation Decisions

**Scope:** CBSE Class 10 Science only; English only; single school (single-tenant); single teacher
role with no approval workflow. Architected to extend later (see seams below).

**Engine philosophy:** Hybrid — a curated bank of real past-paper questions plus textbook-grounded
generation. Bank questions are pre-vetted; generated questions must pass independent verification.
Numerical and diagram-requiring questions are bank-only in v1; no new diagrams are generated
(original figures are reused as cropped images).

**Core modules (deep, isolated interfaces):**
- **TemplateBuilder** — turns a preset + chapter weights + difficulty level into a declarative
  PaperTemplate: an ordered set of slots, each with section, question type, marks, target cognitive
  level, chapter allocation, diagram/numerical flags, and internal-choice grouping. Pure and
  deterministic.
- **QuestionPicker** — given a PaperTemplate, a candidate question pool, and usage history, selects
  bank questions to fill slots, enforcing chapter-weight allocation, cognitive-level distribution,
  no in-paper duplicates, and a less-recently-used preference. Reports filled vs. unfilled slots.
- **GenerationService** — fills remaining text slots with questions grounded in the NCERT textbook,
  producing question text, answer, and a textbook citation. Prompt assembly and response parsing are
  separable from the LLM call.
- **VerifierService** — independently solves a generated question with a separate model call and
  compares to the proposed answer; returns agreement, solver answer, and confidence. Disagreements
  are dropped or flagged.
- **IngestionPipeline** — staged transformation of past-paper PDFs into structured records: parse,
  split language, crop diagrams, match marking scheme, auto-tag (chapter/cognitive/marks/section),
  de-duplicate. Output requires human verification before becoming eligible.
- **Renderer** — produces print-ready PDF, editable DOCX, and a separate answer-key document from an
  approved paper, applying per-school branding and CBSE-style structure/typography.
- **UsageTracker** — records which questions appeared in which papers and answers recency queries.
- **SyllabusTaxonomy** — canonical chapter data with lookup/validation, admin-editable.

**Difficulty model:** Teacher sets a simple difficulty profile; internally every question carries a
Bloom/CBSE cognitive-level tag (Remember/Understand/Apply/Analyse) and the profile maps to a target
distribution across sections.

**Review model:** The system produces a `PaperDocumentV1` JSON (per `contracts/v1_contract.md`) that the frontend renders into a BlockNote block editor. The teacher reviews, edits text, swaps questions (using `alternateQuestionIds` from the document), regenerates, and approves from within the editor. Per-question edits are stored on the paper-question association and do not mutate the shared bank.

**Output & branding:** PDF + DOCX + answer key; CBSE-style section grammar, instruction blocks, and
typography, but with the school's header/branding rather than CBSE codes/barcodes. Branding is
per-school configuration.

**Repetition:** No duplicates within a paper; cross-paper usage tracked with a less-recently-used
preference that the teacher can override.

**Stack:** Django + DRF + Celery + Redis + PostgreSQL backend; React + Vite + TypeScript + Tailwind +
shadcn/ui frontend; Docker; Claude API for generation and a separate call for verification; Django
Admin as the bank verification and taxonomy-management tool. Chosen to be framework-compatible with
the Apptension SaaS boilerplate so its modules (auth, billing, multi-tenancy, GraphQL, IaC) can be
adopted later without a rewrite. REST (not GraphQL), plain folders (not Nx), and a simple PaaS deploy
(not AWS CDK) for the MVP.

**Extensibility seams:** nullable `school_id` on core tables; school-specific config kept in a
settings/school row rather than in code; no assumption of a single global user space. These keep
multi-tenancy an additive step.

**Asynchronous processing:** Paper assembly (selection → generation → verification → render) runs as
a Celery job with progress reported to the UI.

## Testing Decisions

Tests should verify **external behavior through public interfaces**, not internal implementation
details, so that refactors don't break tests. LLM-backed boundaries (generation, verification,
ingestion parsing) are exercised with mocked model responses and canned fixtures; deterministic logic
is tested directly.

Modules to be unit-tested in isolation:
- **TemplateBuilder** — highest-ROI target: fully deterministic. Tests assert that, for given
  presets/weights/difficulty, the produced PaperTemplate has the correct section structure, total marks,
  question counts, chapter allocations, cognitive-level targets, and internal-choice grouping. Edge
  cases: extreme weightings, presets with custom marks, all-Easy/all-Hard profiles.
- **QuestionPicker** — tests assert correct slot-filling against a synthetic candidate pool: chapter
  weights respected, cognitive distribution met within tolerance, no in-paper duplicates, recently
  used items deprioritized, and unfilled slots correctly reported when the pool is insufficient.
- **VerifierService** — tests assert that solver agreement passes an item, solver disagreement
  drops/flags it, and confidence is surfaced — using a mocked solver returning controlled answers.
- **Renderer** — tests assert structural correctness of outputs (section ordering, marks, question
  count, presence of answer key, school branding) via structural assertions and/or golden-file
  comparison for PDF/DOCX/answer-key formats.

Prior art: there is no existing codebase yet (greenfield); these tests establish the testing
conventions. Integration tests will cover the end-to-end generate→review→export flow and the
ingestion pipeline; the API, UI, and Celery orchestration are validated via integration rather than
isolated unit tests.

## Out of Scope

- Subjects other than Class 10 Science; classes/grades other than 10; boards other than CBSE.
- Bilingual (Hindi) output — architected for via language tagging, but not built in the MVP.
- Multi-tenant SaaS, user billing/subscriptions, and enterprise SSO/passkeys.
- Approval/sign-off workflows and multiple in-school roles (HOD/coordinator).
- AI-generated diagrams and programmatically redrawn figures; generation of numerical questions.
- Sub-topic-level syllabus selection (chapter-level only in the MVP).
- Student-facing features, online test delivery, auto-grading of student responses.

## Further Notes

- Source material on hand: NCERT Class 10 Science textbook PDF and three years (2024–2026) of CBSE
  board papers with multiple sets each. Sets within a year overlap heavily (CBSE rotates questions),
  hence the de-duplication requirement.
- The CBSE Class 10 Science board blueprint targeted: 80 marks, 39 questions, 3 hours — Section A
  (Q1–20, MCQ, 1 mark), B (Q21–26, VSA, 2 marks), C (Q27–33, SA, 3 marks), D (Q34–36, LA, 5 marks),
  E (Q37–39, case-based, 4 marks), with internal choices in some questions and no overall choice.
- Build order that de-risks fastest: foundations + taxonomy + blueprint config → clean verified bank
  → bank-only generator producing a board-faithful paper (key milestone) → grounded generation +
  verifier → polish + pilot.
- The primary product risk is trust in correctness; the verifier, bank-only restriction for risky
  types, and mandatory human review are the layered mitigations.
- Detailed design rationale and the full decision log live in `PLAN.md` in this repository.
