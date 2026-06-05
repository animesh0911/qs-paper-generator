# Backend and Frontend Editor Integration Plan

## Summary

The editor is the post-generation workspace. Backend assembly creates saved,
paper-local JSON snapshots. The frontend edits local working copies of those
snapshots, then persists them back to the backend before final preview or
download.

The product invariant is:

> Editor edits are paper-local by default. Bank mutation only happens through a
> future explicit "Fix in bank" action.

## Canonical Documents

The backend owns assembly from database rows into editor-ready documents. The
frontend must not query database-shaped resources or rebuild paper documents from
raw rows.

V1 uses two paper-local documents:

- `Paper.document`: existing `paper_document.v1` student paper document.
- `Paper.answer_document`: new `paper_answer_document.v1` answer-key document.

`Question.answer` remains the bank-level source answer. `Paper.answer_document`
is the editable answer-key snapshot for one paper. Editing an answer in the
editor updates only `Paper.answer_document`, never `Question.answer`.

Answers are keyed by stable Slot id. The Slot is the paper-local review unit;
the selected Question supplies the source answer, but the saved answer belongs
to the Slot and carries the selected Question id for traceability.

Target editor draft payload:

```json
{
  "document": { "schemaVersion": "paper_document.v1" },
  "answer_document": {
    "schemaVersion": "paper_answer_document.v1",
    "paperId": "paper_123",
    "answersBySlotId": {
      "slot_C_03": {
        "slotId": "slot_C_03",
        "questionId": "q_45",
        "content": [
          { "type": "paragraph", "text": "Model answer text." }
        ],
        "source": "source",
        "modified": false
      }
    }
  },
  "status": "draft"
}
```

Answer `content` always uses the same rich `ContentItem[]` family as question
content. Plain bank answers are wrapped as one paragraph. Missing answers still
produce entries for selected Slots, with empty or missing `content` and no
`source`.

Answer `source` is editor-facing provenance only:

- `generated`
- `source`

## Backend Contract

Keep the existing raw paper detail route compatible:

- `GET /api/papers/{id}/` returns the saved `PaperDocumentV1`.

Add a dedicated editor draft lane:

- `GET /api/papers/{id}/editor-draft/`
- `PATCH /api/papers/{id}/editor-draft/`

The editor draft payload is `{ document, answer_document }`. Draft save persists
both fields atomically while the paper is draft. Existing drafts that have
`Paper.document` but no `Paper.answer_document` should lazily build and persist
an answer document on first editor-draft load.

Asset content keeps canonical `assetId` and also carries a backend-issued
render URL. The frontend treats the URL as opaque so storage can later move to
signed S3 or CDN URLs without changing editor logic.

Backend validation between `document` and `answer_document` is still an open
decision tracked separately. The current recommended direction is to reject
stale answer documents when Slot ids or selected Question ids do not match.

## Generate Flow

When the teacher clicks Generate:

1. Frontend posts coverage, difficulty, and format inputs to
   `POST /api/papers/assemble`.
2. Backend validates the request.
3. `PaperBuilder` chooses the `PaperFormat` and `PaperTemplate`.
4. `QuestionPicker` selects bank Questions using slot shape, chapter weights,
   cognitive mix, parse quality, and teacher-specific freshness.
5. Backend persists `Paper` and `PaperQuestion` rows.
6. Backend builds and saves `Paper.document`.
7. Backend builds and saves `Paper.answer_document` from selected Slot answers.
8. Frontend opens the saved paper in `/editor/:paperId`.

The editor, not the dashboard, is the review surface after generation.

## Editor Save Model

The browser edits local working copies of:

- `document`
- `answer_document`

Every editor action updates local document state. The backend remains canonical
for persistence and PDF generation. Final outputs always render from the saved
database snapshots, so dirty editor state must be saved before preview or
download.

Topbar V1 actions:

- `Undo`
- `Save draft`
- `Preview`
- `Download PDF`

No visible `Approve`, `Review paper`, separate answer-key button, or PDF menu in
V1.

`Save draft` calls the editor-draft PATCH endpoint with both documents.

`Preview` silently saves first only when dirty, then opens a lightweight preview
route.

`Download PDF` is the final checkpoint. It silently saves first only when dirty,
then downloads one package containing:

- `question-paper.pdf`
- `answer-key.pdf`

The frontend should not open two PDF tabs directly; browsers can block multiple
tabs or multiple downloads from one click.

## Preview and PDF Rendering

The current question-paper PDF path uses backend-triggered browser print:

1. Frontend/backend opens `GET /api/papers/{id}/pdf/`.
2. Backend creates a tokenized frontend print URL.
3. Backend opens `/editor/{paperId}/print?token=...` in Chromium.
4. Frontend fetches saved paper JSON and renders a print-only surface.
5. Backend prints that route to PDF.

Answer-key PDF should follow the same primary browser-print strategy. ReportLab
fallback can remain lower fidelity, but the primary path should render from a
frontend answer-key print surface and saved `Paper.answer_document`.

Add a lightweight preview route, for example:

- `/editor/{paperId}/preview`

The preview route shows browser-rendered print surfaces, not embedded generated
PDF files. It should use a compact tab or segmented control:

- Question Paper
- Answer Key

The screen should feel like the current print tab: clean, print-focused, and
without editor rails, inspector, chat, overlays, or editing controls.

Backend should add one package endpoint, for example:

- `GET /api/papers/{id}/download-package/`

That endpoint returns a ZIP with both final PDFs and fails loudly instead of
returning a partial package if one PDF render fails.

## Answer Display and Editing

Answers do not appear inside the student paper canvas by default. They are
opened from editor chrome.

Entry points:

- Per-question tray: `Show answer`.
- Question edit overlay: `Review answer`.

The answer pane is a large focused overlay surface similar to the alternatives
overlay. Missing answers show a quiet `Missing answer` state in the editor and
print as `Answer not available` in the answer key.

Question overlay answer review is part of the same overlay transaction:

1. Teacher edits a question.
2. Teacher may open `Review answer`.
3. `Use this answer` returns the answer draft to the question overlay.
4. Final `Use this question` applies both drafts locally.
5. Canceling the question overlay discards both drafts.

Direct answer edits from the per-question tray apply locally on
`Use this answer`.

There is no answer-review lock, checklist, persistent reviewed state, or
`Answer edited` chip in V1. Review is teacher-controlled.

When a Slot swaps to a different selected Question, the Slot answer resets to
the new Question's source answer or to the missing-answer state. Locally edited
answers from the previous selected Question must not carry over.

## Rich Editor Direction

Reuse BlockNote's React/Mantine UI rather than building a custom rich-text
toolbar.

Use one focused BlockNote overlay system for:

- instruction blocks
- question edits
- answer edits

For question editing, do not use one freeform plain BlockNote blob. Use one
normal-feeling BlockNote surface backed by QPG semantic blocks:

- `qpgStem`
- `qpgPassage`
- `qpgAssertion`
- `qpgReason`
- `qpgOption`
- `qpgSubpart`
- `qpgChoiceOption`
- `qpgImage`
- `qpgTable`

These custom blocks keep region identity in block props such as `regionKey`,
`label`, `choiceGroupIndex`, and `assetId`. Teachers edit in one surface, but
save can map blocks back into `PaperDocumentV1.content`.

Existing backend image and diagram assets must be movable and deletable in the
question overlay. Moving/deleting an asset is paper-local: it changes the saved
paper draft, not the backend asset or bank question. Uploading or replacing
images is out of scope for V1.

If a question edit cannot be converted back into valid `PaperDocumentV1`
content, apply should fail loud at `Use this question` time with a teacher-facing
message such as:

> Editing the question this way is not supported yet. Reverting back to the
> original question.

Then discard the unsupported overlay draft. Do not silently flatten, drop
content, or save partial output.

## Risks

- Answer leakage: do not add answers to normal `PaperDocumentV1` or student paper
  PDF rendering.
- Bank mutation: do not write editor answer or question edits back to `Question`
  rows in V1.
- Provenance blur: keep source-backed answer ingestion separate from generated
  answers. GitHub issue #87 tracks bank answer population.
- Format drift: backend and frontend renderers must preserve structured
  `ContentItem` values, including images and tables.
- Editor mismatch: BlockNote rich styles and semantic blocks must map into
  contract content or be rejected before apply.
- Stale answers: question swaps must reset the Slot answer to the newly selected
  Question's answer.
- Partial output: package download must not return a ZIP when one PDF failed.

## Issue Map

- #87: populate bank-level `Question.answer`.
- #109: frontend paper-local answer document load/save flow.
- #110: per-Slot answer display from question tray.
- #111: reset Slot answer on selected Question swap.
- #112: schema-aware BlockNote question overlay.
- #113: shared BlockNote overlay for instructions and answers.
- #118: simplified command bar and package download.
- #119: unified draft save state and unsaved-change guard.
- #121: answer-key print surface from paper-local answers.
- #122: backend paper-local answer document and editor-draft API.
- #123: backend one-click PDF package endpoint.
- #124: lightweight final PDF preview route.
- #125: open decision on editor-draft validation.

## Verification

- Backend tests for assemble creating both documents.
- Backend tests that normal paper JSON does not expose answers.
- Backend tests for editor-draft load/save, lazy answer-document creation, and
  owner scoping.
- Backend tests that package download includes both PDFs and fails on partial
  render failure.
- Frontend tests for loading editor draft payload, revealing answers, saving
  drafts, previewing final outputs, and downloading the package.
- Browser checks for desktop/mobile editor layout, overlay behavior, preview
  route, and print routes.
