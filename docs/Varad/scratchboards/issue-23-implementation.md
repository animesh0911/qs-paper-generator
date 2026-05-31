# Issue 23 Implementation Scratchboard

Issue: https://github.com/animesh0911/qs-paper-generator/issues/23

## Selected Skills

- `github:github`: inspect GitHub issue #23 and confirm the stale #22 blocker.
- `impeccable`: shape restrained hover/selection/editing states for the paper
  editor.
- `browser:control-in-app-browser`: verify the `/editor` interaction loop in
  the running app.

## Public Interfaces

- `buildEditorPaperView(document, options)` maps a `PaperDocumentV1` plus
  optional `slotEditsById` into the editor canvas view.
- `setSlotRegionOverride(state, slotId, regionKey, content)` stores a manual
  edit at `slotId + regionKey`.
- `restoreSlotSource(state, slotId)` clears slot-level region overrides.
- `setPaperChromeText(state, regionKey, text)` updates editable paper chrome
  such as paper title, instruction blocks, section titles, section subtitles,
  and section instructions without changing source questions.

## Main Flow

- `frontend/src/lib/paper-document.ts` keeps canonical editor state normalized
  from `PaperDocumentV1`. `setSlotRegionOverride` writes teacher edits to
  `slotEditsById[slotId].regions[regionKey]`; `restoreSlotSource` clears those
  overrides. `setPaperChromeText` updates `document.paper` fields directly
  because paper chrome is authored by this paper, not by the source question
  bank. `questionsById` remains the original source question map.
- `frontend/src/lib/editor-paper.ts::buildEditorPaperView` maps the canonical
  document plus optional `slotEditsById` into the route view. Each selected
  question becomes a `questionContainerBlock` with fixed child order and stable
  region keys such as `stem`, `option:A`, `subquestion:a`, and
  `choice:0:A`. Paper chrome blocks use stable region keys such as
  `paper:title`, `instruction:<blockId>`, `section:A:title`,
  `section:A:subtitle`, and `section:A:instructions`.
- Question regions carry metadata distinguishing source question text from
  editable paper chrome: question regions use `sourceKind:
  source_question_text` and `editTarget: slot_override`; header/instruction
  chrome uses `sourceKind: paper_chrome` and `editTarget: paper_document`.
- `frontend/src/pages/editor.page.tsx` initializes normalized mock document
  state, passes `slotEditsById` into `buildEditorPaperView`, renders question
  regions and paper chrome blocks as BlockNote surfaces, and saves question
  edits as slot overrides while saving paper chrome edits back into
  `document.paper`.
- The inspector reads the selected slot/question from the view model and shows
  source metadata plus `Modified from source` / `Original source text`. Restore
  calls `restoreSlotSource` and remounts source-backed region editors.
- The mock `PaperDocumentV1` follows the common 2026 Science paper format seen
  in `31-2-1.pdf` and `31-2-2.pdf`: 80 marks, 3 hours, NOTE lines, General
  Instructions, and three subject sections: Section A Biology, Section B
  Chemistry, and Section C Physics.
