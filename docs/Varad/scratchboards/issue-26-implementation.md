# Issue 26 Implementation Scratchboard

Issue: https://github.com/animesh0911/qs-paper-generator/issues/26

## Status

Implemented locally. Issue #23 is closed, so the stated blocker is cleared.
Existing unrelated uncommitted work remains in the worktree and must stay
separate from the issue #26 commit.

## Assumptions

- Reorder is a generic order-zone operation. For the current V1 document, each
  `DocSection` is adapted into an order zone, and each `DocSlot` is an order
  item. Future contracts may define zones differently without changing the
  editor's reorder seam.
- `slotId` remains stable after reorder. `displayNumber` is derived from the
  current ordered paper slots and should no longer be trusted as persisted
  source-of-truth state.
- The app-level undo stack is intentionally one entry deep and tracks only
  structured editor actions. BlockNote region typing keeps using BlockNote's
  own editor undo.
- A replacement action covers swap, same-topic, easier, and harder choices
  because those intents all call the same selected-question state transition.
- Cross-zone moves should be impossible from the UI affordance where practical,
  and rejected by the state helper even if called directly. For current V1,
  cross-zone means cross-section.
- Reorder permissions should not be modeled as section-level rules. The future
  backend contract should expose a general `capabilities.ordering.zones[]`
  shape; issue #26 should derive equivalent zones locally from V1 sections.

## Success Criteria

- A Slot can be reordered before or after another Slot in the same order zone.
- The BlockNote reorder research decision is recorded below: use app-level
  same-section move controls for issue #26, not BlockNote drag handles.
- Direct attempts to reorder a Slot into a different order zone return unchanged
  state with an explicit failure result.
- Visible display numbers are recomputed from current paper order after every
  reorder.
- One-step app-level undo restores the previous normalized paper state for:
  replacement, lock/unlock, restore original, and reorder.
- A newer structured action replaces the previous undo entry.
- Typing inside a `QuestionRegionEditor` does not write to the app-level undo
  entry, so BlockNote text undo remains isolated.

## Selected Skills

- `github:github`: inspect GitHub issue #26 and confirm issue #23 blocker
  status before execution.
- `impeccable`: shape reorder affordances so cross-section movement is visibly
  constrained without adding noisy UI.
- `browser:control-in-app-browser`: verify the `/editor` reorder and undo loop
  in the running app after implementation.

## BlockNote Reorder Research

Decision: implement reorder as app-level same-section Slot movement using
`dnd-kit` drag handles on React Slot rows. Do not use BlockNote's drag handle
for issue #26.

References checked:

- Official BlockNote docs, Block Side Menu:
  https://www.blocknotejs.org/docs/react/components/side-menu
- Official BlockNote docs, Manipulating Content:
  https://www.blocknotejs.org/docs/reference/editor/manipulating-content
- Official BlockNote docs, API Overview:
  https://www.blocknotejs.org/docs/reference/editor/overview
- Installed package source for `@blocknote/core`, `@blocknote/react`, and
  `@blocknote/mantine` at version `^0.51.3`.

Findings:

- BlockNote's standard UI reorder is the Block Side Menu drag handle. The docs
  describe it as a menu shown when hovering a BlockNote block; local source
  confirms `DragHandleButton` calls `sideMenu.blockDragStart(e, block)` for the
  hovered BlockNote block.
- BlockNote also exposes block-level `moveBlocksUp(blockIdentifier?)` and
  `moveBlocksDown(blockIdentifier?)`. The docs define these as moving selected
  or identified blocks inside the current BlockNote document.
- BlockNote undo/redo and transactions are editor-local. They are useful for
  text/block edits inside a single BlockNote editor, but they do not know about
  the app's `PaperDocumentV1` Slot order, lock state, selected question IDs, or
  slot overrides.
- The current paper editor renders each question region through an isolated
  `QuestionRegionEditor`, and `QuestionRegionEditor` disables BlockNote's side
  menu with `sideMenu={false}`. A whole question container is not currently one
  BlockNote block; it is a React Slot row containing multiple source-backed
  region editors.

Why not BlockNote drag handle here:

- Dragging a BlockNote block would move a paragraph/region inside one region
  editor, not reorder the whole question Slot in `document.paper.sections`.
- Modeling a whole Slot as one custom BlockNote block would be a larger
  architecture change: it would merge or wrap multiple region editors, change
  the source-override boundary, and likely affect BlockNote typing undo.
- Issue #26's contract-level requirements are about Slot order, section
  boundaries, derived display numbers, and app-level structured undo. Those are
  already owned by `frontend/src/lib/paper-document.ts` and
  `frontend/src/pages/editor.page.tsx`, not by BlockNote's internal document.

Implementation implication:

- Use `@dnd-kit/core`, `@dnd-kit/sortable`, and `@dnd-kit/utilities` at the
  React Slot layer. Each rendered Slot gets a small drag handle and each order
  zone gets its own `SortableContext`.
- Same-zone dragging commits through `reorderSlotWithinOrderZone`. Cross-zone
  dragging is rejected by the same helper, so the UI may let the pointer hover
  elsewhere but the canonical document order remains unchanged.
- Keep direct cross-zone rejection in the pure state helper so invalid calls
  fail loudly even if a future drag/drop UI is added.
- Leave BlockNote region typing undo untouched by not routing
  `QuestionRegionEditor` changes through the app-level structured undo entry.

## Ordering Contract Direction

Decision: do not add section-level reorder rules. Reorder is a general document
structure capability, and sections are only today's zone shape.

Future backend contract direction:

```json
{
  "capabilities": {
    "ordering": {
      "zones": [
        {
          "zoneId": "section:A",
          "label": "Section A",
          "itemKind": "slot",
          "orderedItemIds": ["slot_A_01", "slot_A_02"],
          "reorder": {
            "enabled": true,
            "allowedTargetZoneIds": ["section:A"]
          }
        }
      ],
      "numbering": {
        "scope": "paper",
        "style": "decimal",
        "deriveFromOrder": true
      }
    }
  }
}
```

Issue #26 implementation direction:

- Do not require a backend contract change before frontend work.
- Add a frontend order-zone adapter that derives zones from
  `document.paper.sections[]` when `capabilities.ordering` is absent.
- Name the local abstraction `OrderZone`, not `SectionReorderRule`, so the
  editor seam is ready for future backend-provided ordering zones.
- For current V1, each Section maps to one order zone:
  - `zoneId`: `section:${section.sectionId}`
  - `orderedItemIds`: `section.slots.map((slot) => slot.slotId)`
  - `allowedTargetZoneIds`: only the same zone
- Keep `paper.sections[].slots[]` as the render structure. Ordering zones
  describe allowed movement; they do not replace the rendered paper shape.

## Public Interfaces

- `buildOrderZones(stateOrDocument)` in
  `frontend/src/lib/paper-document.ts` derives current V1 zones from
  `document.paper.sections[]` and can later read
  backend-provided `capabilities.ordering.zones[]`.
- `reorderSlotWithinOrderZone(state, params)` accepts stable slot and order-zone
  IDs, rejects moves outside allowed target zones, updates canonical
  `document.paper.sections`, `slotsById`, and `slotOrderBySection`, then
  recomputes slot `displayNumber`.
- `renumberPaperSlots(document)` derives paper-scope decimal numbers from
  current section/slot order.
- `commitStructuredPaperAction(currentState, nextState)` and
  `undoStructuredPaperAction(currentState, undoEntry)` keep app-level undo one
  entry deep for structured actions.
- `EditorPage` owns one `StructuredPaperUndoEntry | null` and wraps
  `setSlotSelectedQuestion`, `setSlotLockState`, `restoreSlotSource`, and
  `reorderSlotWithinOrderZone`.
- `SortableQuestionSlot` exposes a drag handle for same-zone movement.
- `QuestionActionRail` remains focused on info, swap, lock/unlock, and ask.

## TDD Slices

1. Add `paper-document.test.ts` coverage for derived order zones:
   current Sections produce stable zones with same-zone-only targets.
2. Add `paper-document.test.ts` coverage for same-zone reorder:
   slot order changes, `slotId` stays stable, canonical section slots move,
   and display numbers recompute across the full paper.
3. Add `paper-document.test.ts` coverage for rejected cross-zone reorder:
   helper returns a failure result and preserves object-visible paper order.
4. Add `paper-document.test.ts` coverage for replacement/lock/restore/reorder
   undo state through a small pure reducer if extracted, otherwise cover via
   the page-level helper that records `previousState`.
5. Add or update `editor-paper.test.ts` to assert the view uses recomputed
   display numbers after reorder rather than stale source ordering.
6. Implement UI controls last, then verify manually in Browser that moving a
   question within Section A changes numbering and Undo restores the prior
   order.

## Main Flow

- `frontend/src/lib/paper-document.ts::normalizePaperDocument` already creates
  `sectionOrder`, `slotOrderBySection`, `slotsById`, and canonical
  `document.paper.sections`. Issue #26 should keep that module as the state
  transition seam instead of sorting in JSX.
- Reorder starts from a drag end event. `EditorPage` maps the active and over
  slot IDs into order zones from `buildOrderZones`, then calls
  `reorderSlotWithinOrderZone`. The helper validates allowed target zones,
  moves the slot ID inside that zone's ordered list, rebuilds the underlying
  section's `slots`, and recomputes display numbers for all sections in paper
  order.
- `frontend/src/lib/editor-paper.ts::buildEditorPaperView` should continue to
  consume the canonical `document`; once `document.paper.sections[].slots[]`
  is updated and renumbered, the existing mapper should render the current
  display order naturally.
- `frontend/src/pages/editor.page.tsx` wraps structured actions with
  `commitStructuredAction`, which stores the previous `paperState` as the
  single undo entry, then applies the next state. Region typing through
  `handleRegionChange` remains outside this helper.
- The top-bar Undo button applies the saved previous state and clears the undo
  entry. A subsequent structured action replaces the previous entry rather than
  appending history.

## Verification Plan

- Frontend unit tests for `paper-document` and `editor-paper`.
- `cd frontend && npm test`: passed, 32 tests.
- `cd frontend && npm run type-check`: passed.
- `cd frontend && npm run build`: passed with existing large editor chunk
  warning.
- `cd frontend && npm run lint`: passed.
- Browser verification on `/editor`: passed. Dragging Question 1 onto Question
  2 reorders within Section A and recomputes display numbers; Undo restores the
  previous order and disables afterward; dragging Question 1 onto Question 6 in
  Section B leaves the order unchanged.
