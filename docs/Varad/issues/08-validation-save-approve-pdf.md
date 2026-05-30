Title: V: Save drafts, approve final paper, and render exam-ready PDF from canonical document
Labels: V

## What to build

Wire the editor to save canonical `PaperDocumentV1` drafts, approve final papers, and ensure the backend PDF renderer uses the final canonical document including slot-level edits and selected replacements.

## Acceptance criteria

- [ ] Save draft sends canonical paper state only, not BlockNote document JSON.
- [ ] Approval freezes the final canonical document.
- [ ] Structural errors block approval; warnings can be approved intentionally.
- [ ] PDF output includes final selected questions, teacher text edits, headers, instructions, sections, marks, numbering, and internal choices.
- [ ] PDF output excludes editor-only UI: action rails, metadata chips, source panels, modified badges, validation UI, and chat.
- [ ] Backend tests prove PDF reflects edited slot content instead of stale bank question text.

## Blocked by

Blocked by #21, #23, #25.
