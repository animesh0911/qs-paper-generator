# Pre-Demo Review: Prompts, Guardrails, Code, Copy, and OCR

**Date:** 2026-07-06 · **Scope:** full codebase + live-app functionality pass before the product demo.
**Explicitly out of scope (per request):** concurrency and security reviews.

All fixes below are **applied in the working tree** (uncommitted) and verified:

- Backend: **559/559 pytest pass** (in Docker), ruff/black clean on every touched file.
- Frontend: **292/292 vitest pass**, `tsc --noEmit` clean, eslint clean on touched files.
- Live app: paper #83 assembled end-to-end; diagrams verified in editor, print route, and a real
  655 KB PDF download rendered through the backend's Chromium; candidate flags verified on batch #13.
- **Full end-to-end Playwright pass of every flow — see §10.** Auth, generate (partial + full),
  editor (swap/edit/undo/lock/preview/download-zip), approve-conflict, upload OCR extraction,
  AI Q&A generation + support-flagging + import, bank filters, and the grounded editor chat all
  pass against the running app with real (minimal-cost) paid LLM calls.

---

## 1. Executive summary

1. **Diagrams were invisible on every surface** — editor, preview, print, and PDF — even though the
   backend cropped, stored, and referenced them correctly. Fixed end-to-end (four stacked causes).
2. **The hallucination screen existed but was dead code.** `bank/citation_support.py` was never
   called. It is now wired into the candidate API + review UI and flags 14/30 candidates on the
   live batch — including exactly the un-self-contained "according to the experimental data" MCQ.
3. **Guardrails hardened**: server-side upload validation, contract validation on draft saves,
   picker tenancy scoping, picker skip for diagram-dependent questions without a stored crop,
   and a hermetic-test fix that stops pytest from calling the real Mistral API.
4. **Prompts improved on all five surfaces** (extraction, OCR, generation, answers, editor chat)
   with no contract changes and ~zero token growth; the editor chat now receives real paper facts
   instead of only the title.
5. **Copy pass**: internal jargon ("candidates"), broken labels ("Open choose chapters",
   "30accepted ·0rejected"), a mislinked "Question bank" chip, and one off-design-system
   glassmorphism card fixed.

---

## 2. Demo-critical: diagram rendering (fixed)

**Symptom:** Q1 of a generated paper read *"Observe the given figure and select the statement…"*
with no figure — in the editor and in the downloaded PDF. The document itself carried
`{"type": "image", "assetId": "diagrams/8c37675e-0.png"}`; the asset existed on disk.

Four stacked causes, all fixed:

| # | Cause | Fix |
|---|-------|-----|
| 1 | No frontend surface rendered `image` items — they flattened to empty text | `<img>` rendering in `paper-document-view` (print/PDF/preview) and `math-content` (editor regions, alternatives, info drawer), with a visible `[Diagram]` fallback when no URL resolves |
| 2 | Editor-draft endpoint resolved URLs via `request.build_absolute_uri` behind the Vite proxy → `http://web:8000/media/…`, a Docker-internal host browsers cannot reach | `papers/views.py:_asset_url` returns root-relative `/media/…`; absolute (S3/CDN) URLs pass through untouched |
| 3 | Vite proxied only `/api` | Added `/media` proxy (`vite.config.ts`) — works from the host browser and the backend's print Chromium alike |
| 4 | Print routes set `data-print-ready` before images loaded — a PDF could snapshot half-loaded figures | Both print pages now gate readiness on `waitForDocumentImages()` (`lib/print-paper.ts`) |

Supporting changes: paper-detail GET now resolves asset URLs (the print route reads it); the legacy
paper PATCH now strips resolved URLs before persisting (contract §13); `.paper-content-image` /
`.qpg-question-image` print-sized CSS.

**Editing caveat (deliberate):** BlockNote flattens region content to plain text, so *editing* an
image-bearing region would silently drop the image from the committed override. Image-bearing
regions therefore render as read-only typeset previews — the same existing rule as math regions.
Making them text-editable while preserving images is a post-demo task.

**Data-quality note:** the stored crop for Q1 contains a stray text line ("btain nutrition.") —
the extraction bbox was too tall at ingest time. The extraction prompt now demands a tight bbox
(see §5); existing crops keep the artifact unless the paper is re-extracted.

---

## 3. Guardrails and validation (applied)

- **Upload validation** (`bank/serializers.py`): the dropzone promised "PDF only · up to 25 MB"
  but the server accepted anything. Now rejects >25 MB and non-`%PDF-` files at upload time with
  actionable copy, instead of queueing a job the drain worker fails minutes later.
- **Draft-save contract validation** (`papers/views.py`): both PATCH endpoints validate the saved
  document against the v1 JSON schema (the same one generated from the frontend Zod schema) →
  a clean 400 with details instead of persisting a document that later breaks the editor as the
  opaque "Unable to open paper". Test fixtures upgraded to contract-valid documents via the new
  shared `papers/tests/contract_documents.py`.
- **Picker tenancy** (`papers/picker.py`): `_fetch_candidates` had no school filter — a paper
  could select another school's uploaded questions. Now mirrors the bank views' visibility
  (global bank + requesting teacher's school). *(The earlier `agy-backend-api-auth-review` also
  flagged this; it is now fixed.)*
- **Picker diagram guard** (`papers/picker.py`): rows with `primary_form=diagram_based` and no
  stored crop are excluded from automatic selection (still visible in the bank). Uses
  `primary_form` rather than the broader `has_diagram` so "Draw a labelled diagram…" questions
  (which need no source figure) remain pickable.
- **Hermetic tests** (`backend/conftest.py`): `.env` carries `EXTRACTION_PIPELINE=mistral-ocr-markdown`
  and a live Mistral key, which the compose files pass into every backend container — so the drain
  tests were **calling the real Mistral OCR API** during pytest (observed live; the call 400'd on a
  fake PDF, so no tokens were consumed). An autouse fixture now strips
  `EXTRACTION_PIPELINE`/`MISTRAL_API_KEY`/`MISTRAL_OCR_API` for every test. Note: that env var is
  still the *live* extraction path for demo uploads — intended, just be aware.
- **N+1 fix**: the polled generation-batch list issued one `COUNT` per batch;
  `list_generation_batches` now annotates the count and the serializer falls back only for
  single-object use.
- Fixed a **pre-existing broken test** on `main`: `GenerationBatch.objects.create(candidate_count=3)`
  passed a nonexistent field (TypeError).

---

## 4. Hallucination catching for generated Q&A (applied)

`bank/citation_support.py` (lexical citation-support review) was **defined and tested but never
invoked** by any production path.

- `GeneratedQuestionCandidateSerializer` now computes a `support_review` field per grounded
  candidate at serialization time (no migration, no drain change): question/answer lexical overlap
  with the cited NCERT excerpts + formula/diagram-shaped-prompt flags.
- The review UI (`candidate-review-panel`) shows an amber **"Check against NCERT before accepting"**
  chip with a per-issue tooltip. It is a review aid, never auto-rejection — the teacher decides.
- **Live result on batch #13:** 30/30 candidates screened, 14 flagged — including exactly the
  visually-suspect *"lowest melting point according to the experimental data of their physical
  properties"* MCQ (`low_lexical_citation_overlap`).

---

## 5. Prompt improvements (all surfaces; non-breaking; ~zero token growth)

**Editor chat** (`ai_editor/assistant.py`) — the highest-impact one. The chat prompt contained
*only the paper title*, so "how many marks is Section C?" could only be hallucinated. It now gets
`paper_snapshot(document)`: ~100 tokens of derived facts (total marks, duration, per-section
question counts, filled slots, marks) plus an instruction to ground every number in those facts and
say when a detail is not visible rather than guessing.

**Question generation** (`bank/generation.py`):
- `Difficulty targets (percent of candidates, easy/medium/hard)` — the bare `{'easy': 30, …}` dict
  was ambiguous between counts and percents.
- The hardcoded *"for a 30-question batch this should include about 5 long_answer items"* is now
  computed from the actual final distribution (correct at every batch size; omitted when the batch
  has no long-answer target).
- Self-containment ban list extended with the phrasings observed slipping through:
  *"according to the experimental data"*, *"as shown/seen above"*.
- MCQ options pinned to **exactly four, labelled A, B, C, D**.

**Extraction** (`bank/extraction_prompt.py`):
- `rawText` must exclude the printed question number (previously only regex-stripped afterwards).
- Figure bboxes must be **tight around the artwork** — include internal labels, exclude question
  text/option lines/mark digits (root cause of the text-bleed crops, §2).

**Answer generation** (`bank/answer_generation.py`): CBSE marking-scheme style (≈one key point per
mark), numericals must show formula → substitution → final value with SI unit, and "never invent
labels or values for a diagram you cannot see".

**OCR structuring** (`bank/ocr_extractor.py`):
- Prompt: no question numbers/marks digits in rawText; never invent option labels/text/marks or
  missing halves of a truncated question.
- `_is_visual_question` was over-broad: bare `\bdiagram\b`, `\bfigure\b`, `given below`,
  `following experiment` dropped *legitimate* questions ("Draw a labelled diagram of…",
  case-based "Answer the questions given below"). Patterns are now **reference-anchored**
  ("shown in the figure", "the given circuit", "observe the diagram", …) — hallucination guard
  kept, recall recovered. `primary_form`/`figures` remain the primary gates.

---

## 6. Copy and UX (applied)

| Surface | Before | After |
|---------|--------|-------|
| Generate page launcher buttons | "Open choose chapters" / "Open choose sources" | "Choose chapters" / "Choose sources" |
| Scope panel, nothing selected | "All chapters" (while Generate stayed disabled — contradictory) | "None selected yet" |
| Paper-structure tile | "Chapters: 0" | "Chapters: None yet" |
| Marks-by-type expander | raw codes (`very_short_answer`) | teacher labels ("Very short answer") |
| Generate-page header chip | "Question bank" **linking to `/ai-qa`** with a sparkles icon | links to `/question-bank` with the nav's library icon |
| Welcome cards | "Create candidates." / "Add PDFs." / "Build from the bank." | "Draft new questions with AI." / "Add questions from past-paper PDFs." / "Assemble a CBSE-style paper from your bank." |
| Welcome eyebrow/subtitle | "Exam desk", "Upload and AI Q&A feed the bank. Generate uses it." | "Exam Desk", "Grow the question bank by upload or AI, then generate a paper from it." |
| Candidate review chip | "30accepted ·0rejected" (flex whitespace collapse) | "30 accepted · 0 rejected" |
| Candidate review count | "30 candidates ready" (internal jargon) | "30 questions ready for review" |
| AI Q&A header | "Review candidates before they enter your bank." + glassmorphism card | de-jargoned copy + flat card per DESIGN.md |

---

## 7. Flagged, deliberately not changed (owner decisions)

1. **Generate requires explicit chapter/source selection.** Documented as deliberate in
   `useCoverageForm` ("so teachers do not accidentally use all"); the backend supports empty =
   all chapters. If one-click generation is wanted for the demo it is a two-line frontend change.
2. **Cross-school ingest dedupe**: `source_hash` dedupe is global, so a second school uploading the
   same paper gets "skipped duplicates" and owns no rows. Irrelevant for a single-school demo;
   revisit for multi-tenancy.
3. **Batch-progress page** (`bulk-question-generation.component`) still uses `white/70` glass
   styling — off-system per DESIGN.md, but pervasive in that component; deserves its own pass.
4. **Design-hook findings** in `index.css` (paper-ink `#333`, hairline rgb values, 3px radius) are
   pre-existing, deliberate exam-paper print styling — left alone. Two "broken image" hook findings
   were false positives on code comments.
5. **Auth/session issues** (non-expiring tokens, no logout endpoint, print-URL tokens) — known from
   the earlier auth review; excluded here per the "no security review" instruction.

---

## 8. Easy wins before the demo (suggested, not implemented)

- **"Download answer key" button** in the editor header — backend zip endpoint
  `/api/papers/{id}/pdf-package/` already exists; only a button is missing.
- **Chapter coverage summary** in the editor's left rail — `Paper.report.coverage` is already
  persisted and returned.
- **"Reject all flagged"** bulk action in candidate review, powered by the new `support_review`.
- **"Missing diagram" filter** in the question bank (`has_diagram` + empty `diagram`) to triage
  crop gaps.
- **"Use demo account"** one-click button on login (credentials are already prefilled).

---

## 9. Files changed

**Backend:** `ai_editor/assistant.py`, `ai_editor/views.py`, `bank/answer_generation.py`,
`bank/extraction_prompt.py`, `bank/generation.py`, `bank/generation_batches.py`,
`bank/ocr_extractor.py`, `bank/serializers.py`, `papers/picker.py`, `papers/views.py`,
`conftest.py`, `papers/tests/contract_documents.py` (new), `papers/tests/test_answer_document.py`,
`papers/tests/test_answer_key_view.py`, `bank/tests/test_generation_batch.py`.

**Frontend:** `vite.config.ts`, `index.css`, `types/index.ts`,
`components/math/math-content.component.tsx`,
`components/coverage/paper-document-view/paper-document-view.component.tsx`,
`components/coverage/coverage-form/coverage-form.component.tsx` (+ its test),
`components/editor/question-region-editor.component.tsx`,
`components/question-generation/candidate-review-panel.component.tsx` (+ bulk test),
`lib/print-paper.ts`, `pages/print-paper.page.tsx`, `pages/print-answer-key.page.tsx`,
`pages/welcome.page.tsx` (+ test), `pages/ai-qa.page.tsx`.

---

## 10. End-to-end flow verification (Playwright, live app)

Every user flow was driven through the running app with Playwright. Paid LLM calls
(upload OCR extraction, AI Q&A generation, editor chat) were exercised with the owner's
consent at minimum cost (a 1-page PDF and a 4-candidate batch instead of the UI's default 30).
All flows **pass**. New IDs created during this run: papers #83/#85/#86, ingestion job #21,
generation batch #15, bank questions #481/#482.

### Results by flow

| Flow | Steps exercised | Result |
|------|-----------------|--------|
| **Auth** | sign out (token cleared → `/login`), wrong password → "Invalid email or password.", register new account → welcome, re-login | **Pass** |
| **New-account tenancy** | new teacher (own school) can read the global bank and assemble a paper (6/6 filled) | **Pass** — confirms the picker tenancy fix doesn't hide the seeded bank |
| **Generate (single chapter)** | Electricity only → editor with **7/39 filled, 37 unfilled-slot warnings** listed | **Pass** — partial-fill path works |
| **Generate (all chapters)** | select-all → **39/39 filled, no structural warnings**, diagrams render | **Pass** |
| **Editor — swap** | Swap overlay (38 slot-safe options, Easier/Harder tabs) → "Use this question" → row updates, header goes "Unsaved" | **Pass** |
| **Editor — save + answer reconcile** | Save draft → "Saved"; editor-draft API shows the swapped slot's answer entry `questionId` matches the new selected question (no stale answer) | **Pass** — validates the #125 reconcile path |
| **Editor — text edit** | click stem → BlockNote activates → type → blur commits, "Modified" badge + "Unsaved" | **Pass** |
| **Editor — Undo** | Undo reverts the edit, returns to "Saved" | **Pass** |
| **Editor — Lock** | Lock → "Locked 1"; a locked question's Swap is correctly disabled | **Pass** |
| **Editor — Preview** | Preview runs the mocked sample-paper review card ("Reviewed … 3 sections, 39 questions, 80 marks, no structural warnings") | **Pass** (note: Preview is a *review* action, not a print preview — see improvements) |
| **Editor — Download PDF** | produces a **zip** (`question-paper.pdf` 16pp + `answer-key.pdf` 3pp) in ~2.5 s; a separate diagram-bearing paper's single PDF embeds **5 images** at 655 KB | **Pass** |
| **Approve → stale edit** | approve paper #86 (200) → an editor still on the draft that tries to save hits **409 Conflict** (revision guard), no silent overwrite | **Pass** |
| **Upload — bad file** | non-PDF via API → **400** "This file is not a PDF. Export or scan the paper as a PDF, then try again." | **Pass** — the new server guardrail |
| **Upload — real extraction** | 1-page PDF → queued → Mistral OCR + structuring drain → **done: 3 created, 1 skipped (dedupe), 1/1 pages**; review card shows correctly-tagged, verbatim questions | **Pass** — validates the OCR prompt/ filter changes on real output |
| **AI Q&A — generate** | grounded batch (count 4, 1 topic) → **ready_for_review, 4 candidates** | **Pass** |
| **AI Q&A — support flags** | 2/4 candidates flagged ("graphite structure", "fullerenes" — both diagram/structure-dependent); 2 clean MCQs pass. Amber "Check against NCERT" chip renders | **Pass** — the previously-dead hallucination screen, live on fresh output |
| **AI Q&A — reject/undo + import** | reject the 2 flagged → "2 accepted · 2 rejected" → Import → batch **accepted**, 2 questions (#481/#482) in the bank and searchable | **Pass** |
| **Question bank — filters** | chapter=electricity → 23, section A → 201, qtype=mcq → 173, source=ai_generated → 112, search "graphite" → 2, combined → 2; pagination "Showing 1–50 of 473", Prev disabled / Next enabled | **Pass** |
| **Editor AI chat (grounded-prompt fix)** | see below | **Pass** — the highest-value verification |

### Editor AI chat — the grounded-prompt fix, proven

The chat prompt previously received only the paper *title*. After the `paper_snapshot()` change it
receives derived facts. Live results on paper #86:

- **"How many marks is Section C worth, and how many questions?"** →
  *"Section C (Physics) is worth **25 marks**. It has **10 questions** (12/12 slots filled)."*
  Cross-checked against the document: Section C marks = 25 ✓. (The "10 questions / 12 slots" gap is
  correct — two case-based OR-pairs collapse to one question each; the snapshot counts logical
  questions, not raw slots.)
- **Grounding honesty:** "What is the exact wording of question 4 in Section B?" →
  *"I cannot see the exact wording of the questions or any of the sourced question text. I can only
  see the overall structure, section distribution, and marks."* — exactly the anti-hallucination
  behavior the change targets; pre-fix it would have invented a stem.
- **Off-topic guard:** "What is the capital of France?" → intent route `off_topic`. ✓

### Flow issues found during verification (new; not yet fixed)

1. **`paperId` type mismatch, frontend vs API.** The AI intent/chat serializers require an integer
   `paperId`, but the editor elsewhere uses the `"paper_86"` string form. Passing the string yields a
   silent **400**. The editor's own chat UI sends the right shape, but the inconsistency is a
   footgun — normalise on one form (prefer accepting both `86` and `"paper_86"` in the serializer).
2. **Unfilled-slot warnings don't aggregate.** A single-chapter paper listed 32 near-identical
   "Slot N has no selected question." lines in the left rail. Collapse to
   *"32 slots have no question — not enough Biology MCQs in the selected chapters"* with an expander.
3. **Upload review copy is contradictory.** A prior upload card read *"0 questions extracted · 18
   skipped"* above *"The questions are in your bank."* — when 0 usable questions were added, that
   second line misleads. Say *"No new questions — all 18 were duplicates already in your bank."*
4. **"Preview" button is mislabeled.** In the editor header it runs the AI *review* card, not a
   print preview — but "Preview" next to "Download PDF" reads as "preview the PDF". Rename to
   **"Review"** (matches the card it opens) or make it an actual document preview.
5. **Welcome page has no "Sign out".** Only inner pages carry it; a teacher who lands on `/` after
   login cannot sign out without first navigating into a workflow. Add it to the welcome header.

### Suggested flow improvements (beyond the issues above)

- **Generate:** allow "generate with all chapters" in one click (the backend already treats empty =
  all); today the button stays disabled until a selection, which contradicts the "All chapters"
  scope hint. This was flagged in §7.1 and the live run confirmed the friction.
- **Editor:** surface an explicit **"Approve & lock"** action in the header. Approval currently has
  no button in the editor (only reachable via API/other routes), yet it is the paper's terminal
  state and the moment freshness/verified flags are written.
- **Upload:** show the **per-chapter extracted breakdown inline** on the active status card (already
  present on the "recent papers" card) so a teacher sees what landed without re-opening review.
- **AI Q&A:** add a **"Reject all flagged"** bulk button driven by the new `support_review` field —
  in this run I rejected the 2 flagged candidates by hand; one click would scale to a 30-batch.
- **AI Q&A:** the UI hard-codes `count: 30`. Expose a small **count selector (10/20/30)** so a
  teacher (and a demo) can run a cheaper batch; the backend already accepts 1–50.
- **Bank:** add a **"needs diagram" / "flagged" filter** (backend `has_diagram` + empty `diagram`,
  and generated-with-unsupported-citation) so teachers can triage the questions most likely to need
  attention — complements the picker's new skip-uncropped-diagrams guard.
- **Global:** the live **"N extracted" / "Q&A imported" header badges** (seen during this run) are a
  nice touch — extend the same pattern to a generation-in-progress badge so a teacher who navigates
  away from AI Q&A still sees the batch maturing.

### Verification method note

Paid flows were kept minimal per the owner's cost instruction: a 1-page PDF (derived from an
existing fixture) for upload, and a 4-candidate single-topic batch for generation. The frontend's
fixed `count: 30` was bypassed by calling the generation API directly with `count: 4` — the same
code path the drain worker and validation run, so the `support_review` result is representative.
No demo data was destroyed; batch #13 (the pre-existing 30-candidate prop) was left untouched.
