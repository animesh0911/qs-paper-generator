Title: V: Build print-faithful BlockNote editor shell
Labels: V

## What to build

Create the React editor surface that renders a print-faithful paper canvas using BlockNote, with top bar, left rail, right inspector area, and bottom floating chat shell.

## Acceptance criteria

- [ ] Editor route can load the mocked `PaperDocumentV1`.
- [ ] Center canvas resembles an A4/CBSE exam paper, including header, instructions, section boundaries, marks, numbering, and question spacing.
- [ ] Top bar includes paper title, one-step undo, save draft, approve, download PDF, and review paper actions.
- [ ] Left rail includes section outline and validation summary.
- [ ] Right inspector exists but can be empty until selection is implemented.
- [ ] Bottom floating chat shell is always available but does not cover core paper content.
- [ ] Bottom chat is visually locked to the bottom of the viewport and remains accessible while the paper scrolls.
- [ ] Editor controls are hidden from print/export styling.

## Blocked by

Blocked by #21.
