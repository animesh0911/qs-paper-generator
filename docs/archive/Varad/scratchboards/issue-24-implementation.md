# Issue 24 Implementation Scratchboard

Issue: https://github.com/animesh0911/qs-paper-generator/issues/24

## Selected Skills

- `impeccable`: shape a restrained product UI for the selected-question action
  rail and inspector modes without letting editor chrome invade the printable
  paper.
- `browser:control-in-app-browser`: verify the `/editor` selection, rail,
  inspector, locked-action, and chat-focus interactions in the running app.

## Public Interfaces

- `buildEditorPaperView(document, options)` exposes selected-slot data used by
  the editor page: one slot per `slotId`, source metadata, lock/modified state,
  and resolved alternatives.
- `EditorPage` owns the single selected question, inspector mode, active
  alternatives intent, and chat focus/context.

## Main Flow

- `frontend/src/lib/editor-paper.ts::buildEditorPaperView` resolves each
  slot's `alternateQuestionIds` into `alternateQuestions` with question text,
  marks, type, chapter, topics, difficulty, CBSE relevance, and source. The
  right inspector consumes this view data instead of looking up alternatives in
  React render code.
- `frontend/src/lib/paper-document.ts::setSlotLockState` updates the normalized
  `lockStateBySlotId`, `slotsById`, and canonical `document.paper.sections[]`
  slot record together. The editor view is rebuilt from `paperState.document`,
  so rail disabled states, inspector lock state, and validation locked counts
  stay aligned.
- `frontend/src/pages/editor.page.tsx` keeps a single `selectedSlotId`, plus
  `inspectorMode` (`info` or `alternatives`) and an alternatives intent
  (`swap`, `topic`, `easier`, or `harder`). Clicking or focusing a question
  selects that one slot and clears paper-chrome selection.
- The selected question renders `QuestionActionRail` as `data-editor-chrome`
  outside the desktop paper content area. The rail exposes keyboard-accessible
  buttons with labels/tooltips for Info, Swap, Topic, Easier, Harder,
  Lock/Unlock, and Ask. Locked slots disable replacement actions while leaving
  Info, Ask, manual editing, and Unlock available.
- The Info inspector mode shows marks, type, chapter, topics, difficulty, CBSE
  relevance when present, source details, lock state, and modified state. The
  Alternatives mode lists resolved slot-safe alternatives and disables
  replacement buttons while the selected slot is locked.
- Ask sets bottom chat text to `Question <displayNumber>:` and focuses the chat
  input, preserving selected-question context for the next chat workflow.
