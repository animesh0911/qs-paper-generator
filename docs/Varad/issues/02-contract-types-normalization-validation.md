Title: V: Add frontend contract types, normalization, and runtime validation
Labels: V

## What to build

Add TypeScript types and runtime validation for `PaperDocumentV1`, then normalize it into editor-friendly canonical state maps.

## Acceptance criteria

- [ ] `assemblePaper` returns `PaperDocumentV1` instead of the legacy flat `Paper` shape for the editor flow.
- [ ] Frontend validates required top-level objects, format rules, sections, slots, selected questions, alternates, marks, type, and language.
- [ ] Validation fails loud in development and returns user-safe errors in UI.
- [ ] Normalized state includes `questionsById`, `slotsById`, section order, slot order by section, slot edits, lock state, and format rules.
- [ ] Unknown optional fields are ignored and preserved where practical.

## Blocked by

Blocked by #20.
