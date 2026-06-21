# Scratchboard: Issue #22 Implementation

GitHub: https://github.com/animesh0911/qs-paper-generator/issues/22

## Selected Skills

- `impeccable`: required by the issue for minimal, product-register editor UI decisions.
- `tdd`: Ralph loop implementation skill; use one public-interface slice at a time.
- `code-review`: required Ralph loop review gate before final verification.

## Assumptions

- Issue #21 frontend work is available locally: `mockPaperDocumentV1`,
  `parsePaperDocument`, and `normalizePaperDocument` exist and pass their tests.
- The issue asks for a shell, not full selection/editing/swap behavior. The
  right inspector can remain a quiet placeholder until selection is implemented.
- BlockNote should be present in the route, but business tests should target our
  paper canvas view model rather than BlockNote internals.
- Backend live assemble alignment remains tracked separately in issue #38, so
  this route loads the mocked `PaperDocumentV1`.

## Public Interfaces Under Test

```ts
buildEditorPaperView(document)
```

React route:

```tsx
<EditorPage />
```

## RED/GREEN Slices

### Slice 1: editor paper view model

RED: `buildEditorPaperView(document)` did not exist. Added tests requiring the
mocked `PaperDocumentV1` to become:

- title, subtitle, marks, and duration metadata
- general instructions
- section outline rows
- slot rows with display number, marks label, lock state, and BlockNote starter
  blocks
- validation counts for total, filled, locked, and warning slots

GREEN: added `frontend/src/lib/editor-paper.ts`. It maps the contract into a
React-friendly view model and converts each supported question content shape
into basic BlockNote paragraph blocks.

### Slice 2: React editor shell

GREEN: added `/editor`, backed by `mockPaperDocumentV1`, with:

- top bar actions: undo, save draft, review paper, download PDF, approve
- left section outline and validation summary
- centered paper canvas with header, instructions, sections, numbering, marks,
  and BlockNote-rendered question regions
- right inspector placeholder
- fixed bottom chat shell
- print media rules hiding editor chrome

### Slice 3: bundle containment

GREEN: lazy-loaded the editor route in `App.tsx` so BlockNote is not part of the
initial dashboard/login route bundle.

## Verification

- `cd frontend && npm test`: pass, 12 tests.
- `cd frontend && npm run type-check`: pass.
- `cd frontend && npm run build`: pass. Vite still warns that the lazy editor
  chunk is larger than 500 kB because BlockNote is large; the main route bundle
  is split from the editor.
- `cd frontend && npm run lint`: pass with 1 pre-existing warning in
  `frontend/src/components/ui/button/button.component.tsx`.
- Browser visual check at `http://127.0.0.1:5173/editor`: pass for desktop and
  mobile responsive layout after revisions.
- Print CSS check: pass. In Playwright print media,
  `[data-editor-chrome]` computes to `display: none`.

## Review Findings and Fixes

- Code-review pass found one standards issue in the new test file: missing
  module-level header. Fixed in `frontend/src/lib/editor-paper.test.ts`.

## Acceptance-Criteria Check

- Editor route can load the mocked `PaperDocumentV1`: PASS. `/editor` parses
  `mockPaperDocumentV1` through `assertPaperDocument`.
- Use impeccable skill for minimal design decisions: PASS. Product-register
  guidance used: paper centered, restrained chrome, no decorative cards or
  gradients, controls secondary to paper.
- Center canvas resembles A4/CBSE paper: PASS. Includes document header,
  instructions, section boxes, numbering, marks, and question spacing.
- Top bar includes required actions: PASS.
- Left rail includes section outline and validation summary: PASS.
- Right inspector exists but empty until selection: PASS.
- Bottom floating chat shell is always available and does not cover final paper
  content while scrolling: PASS. The route reserves bottom padding and locks
  the chat to the viewport bottom.
- Bottom chat remains accessible while paper scrolls: PASS.
- Editor controls are hidden from print/export styling: PASS.

## React Learning Notes

- `EditorPage` is a route component. It uses `useMemo` to parse the mock once
  and build the paper view model from it. This avoids recomputing all section
  and slot display rows on every render.
- `QuestionRegionEditor` is a small child component because React hooks must be
  called at the top level of a component. Each question region calls
  `useCreateBlockNote({ initialContent })`, then renders a `BlockNoteView`.
- `editable={false}` keeps this issue to shell/rendering scope. Later region
  editing can turn editing on and persist changes as slot-level overrides.
- `data-editor-chrome` marks UI that belongs to the editor, not the paper.
  Print CSS hides those elements so export/print keeps only paper content.
- `React.lazy` plus `Suspense` loads `EditorPage` only when `/editor` is opened,
  which keeps BlockNote out of the initial dashboard bundle.

## Decisions Worth Carrying Forward

- Keep `PaperDocumentV1` canonical. BlockNote blocks are render/edit surfaces,
  not the business source of truth.
- Use `buildEditorPaperView` as the public mapper seam for future shell work so
  React stays mostly presentational.
- BlockNote package size is expected; keep the route lazy-loaded and consider
  deeper manual chunking only if production bundle budgets require it.

## Final Code-Level Change Summary

- Added BlockNote, Mantine BlockNote UI dependencies, Mantine peer packages, and
  lucide icons.
- Added `frontend/src/lib/editor-paper.ts` and tests for mapping
  `PaperDocumentV1` into editor shell display state and BlockNote starter
  blocks.
- Added `frontend/src/pages/editor.page.tsx` as the mock-backed editor route.
- Updated `frontend/src/App.tsx` to lazy-load `/editor` behind auth.
- Updated `frontend/src/index.css` with paper canvas, BlockNote reset, and print
  hiding rules for editor chrome.
