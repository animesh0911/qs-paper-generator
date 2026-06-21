# Issue 25 Implementation Scratchboard

Issue: https://github.com/animesh0911/qs-paper-generator/issues/25

## Selected Skills

- `tdd`: drive replacement and deterministic alternative filtering through
  public frontend seams before wiring the UI.
- `code-review`: review the final diff for correctness, complexity, and
  coverage before handoff.
- `browser:control-in-app-browser`: attempted for the `/editor` interaction
  check; the in-app browser blocked the local URL by policy.

## Public Interfaces

- `frontend/src/lib/paper-document.ts::setSlotSelectedQuestion`
- `frontend/src/lib/editor-paper.ts::buildEditorPaperView`
- `frontend/src/components/editor/editor-inspector.component.tsx::EditorInspector`

## Main Flow

- `setSlotSelectedQuestion(state, slotId, selectedQuestionId)` updates the
  normalized `slotsById` entry and the canonical
  `document.paper.sections[].slots[]` record for the target Slot. It preserves
  the Slot identity, section placement, marks, question type, display number,
  lock state, and `alternateQuestionIds`; it only changes
  `selectedQuestionId` and resets the Slot override to
  `{ modifiedFromSource: false, regions: {} }`. `questionsById` remains the
  same source-question map.
- `buildEditorPaperView(document, { slotEditsById, alternativesIntentBySlotId
  })` continues to resolve each Slot's `alternateQuestionIds`, then narrows the
  selected Slot's `alternateQuestions` for the active intent. `swap` returns all
  resolved slot-safe alternatives; `topic` returns topic-overlap matches first
  and falls back to chapter-overlap matches; `easier` and `harder` compare
  against the selected Question's difficulty rank.
- `EditorPage` feeds the active Slot/intent into `buildEditorPaperView`, so the
  right inspector receives already-filtered candidate data. Clicking
  QuestionActionRail actions sets the inspector mode and intent (`swap`,
  `topic`, `easier`, `harder`).
- `EditorInspector` renders candidate cards with question text, marks/type,
  chapter/topic chips, difficulty, CBSE relevance when present, source, and a
  `Use this question` action. Empty filtered results show `Show all
  alternatives` plus a disabled `Find more in question bank` placeholder.
- `EditorPage::handleUseAlternative` warns when the selected Slot has manual
  overrides, then applies `setSlotSelectedQuestion` and bumps that Slot's
  editor reset version so BlockNote-backed region editors remount with the new
  source Question content.
