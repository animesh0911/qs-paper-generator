# Issue 27 Implementation

## Selected Skills

- `tdd`: issue changes public save/approve/PDF behaviour; implement one public-interface slice at a time.
- `code-review`: required Ralph loop gate before final verification.

## Public Interfaces

- Frontend API adapter: `savePaperDraft(document)` PATCHes `PaperDocumentV1` canonical state; `approvePaper(document)` POSTs the final canonical state for approval.
- Backend paper API: `PATCH /api/papers/{id}/` saves draft canonical `PaperDocumentV1`; `POST /api/papers/{id}/approve/` validates and freezes final canonical `PaperDocumentV1`.
- Backend PDF seam: `render_paper_pdf(document)` renders from final `PaperDocumentV1`, including slot-level overrides.

## Main Flow

- The editor keeps `PaperDocumentV1` as the canonical save/export state in
  `frontend/src/lib/paper-document.ts`. Slot region edits now update both
  `slotEditsById` and the matching Slot `overrides` inside
  `paperState.document`, so the persisted document contains teacher text edits
  without mutating `questions[]`.
- `frontend/src/lib/api.ts` exposes `savePaperDraft(document)` and
  `approvePaper(document)`. Both derive the backend paper id from
  `document.paper.paperId` and send `{ document }`; no BlockNote JSON or
  editor-only UI state is included.
- `frontend/src/pages/editor.page.tsx` wires toolbar actions to the API seam:
  save sends the current canonical draft, approve sends the current canonical
  final document and asks for confirmation when editor warnings exist, and PDF
  download saves the current draft before calling the PDF endpoint.
- `backend/papers/views.py` validates canonical documents on draft save and
  approval. Structural errors are missing question references or selected /
  alternate questions whose marks, question type, or language do not match the
  Slot. Approval saves the submitted document before setting status to approved,
  which freezes the final canonical document.
- `backend/papers/pdf.py` renders directly from `PaperDocumentV1`: title,
  subtitle, header blocks, instruction blocks, sections, section instructions,
  numbering, marks, selected questions, structured content, internal choices,
  and Slot overrides. Because it consumes only the backend document contract, it
  has no path to render editor-only UI such as action rails, metadata chips,
  validation UI, or chat.
