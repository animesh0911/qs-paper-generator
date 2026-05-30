# Scratchboard: Issue #21 Implementation

GitHub: https://github.com/animesh0911/qs-paper-generator/issues/21

## Selected Skills

- `tdd`: primary implementation loop.
- `code-review`: required diff review gate before final verification.

## Assumptions

- Issue #20 is complete and closed, so `mockPaperDocumentV1` and the structural
  `paperDocumentSchema` are available as the baseline contract fixture.
- Issue #21 should not add BlockNote rendering or editor actions. It should only
  add validation, API-boundary behavior, normalization state, and the minimal
  backend alignment needed for `POST /api/papers/assemble` to return the V1
  document shape the frontend now requires.

## Public Interfaces Under Test

```ts
parsePaperDocument(payload)
normalizePaperDocument(document)
getPaperDocumentErrorMessage(error)
assemblePaper(payload)
```

Backend alignment public interface:

```python
POST /api/papers/assemble -> PaperDocumentV1
```

## RED/GREEN Slices

### Slice 1: semantic contract validation

RED: `parsePaperDocument(invalidDocument)` should reject:

- missing `selectedQuestionId` references
- referenced questions whose marks, question type, or language do not match the
  containing slot

GREEN: `paperDocumentSchema.superRefine` now validates selected and alternate
question references against `questions[]` and checks slot compatibility.

### Slice 2: canonical editor normalization

RED: `normalizePaperDocument(parsedDocument)` should derive:

- `questionsById`
- `slotsById`
- `sectionOrder`
- `slotOrderBySection`
- `slotEditsById`
- `lockStateBySlotId`
- `formatRules`

GREEN: added `frontend/src/lib/paper-document.ts` with the normalization seam.
Question source content remains in `questionsById`; paper-specific edits are
held separately in `slotEditsById`.

### Slice 3: user-safe contract errors

RED: contract failures should keep developer details but expose a safe UI
message.

GREEN: added `PaperDocumentContractError`, `assertPaperDocument`, and
`getPaperDocumentErrorMessage`. `assemblePaper` validates through this seam and
the dashboard logs the detailed error in development while rendering the safe
message.

### Slice 4: unknown optional fields

RED: parsed documents should preserve additive optional fields.

GREEN: schema objects now use `passthrough()` where practical, including the
top-level document and nested slot objects.

### Backend handoff: live assemble response alignment

Issue #21 frontend validation now expects the V1 contract, but backend
`PaperDocumentBuilder` still needs a backend-owned follow-up before live
`/api/papers/assemble` responses satisfy it:

- emit top-level `format`
- include `alternateQuestionIds` on every slot, using `[]` when no alternates
  exist

Per owner decision, backend code changes were removed from this frontend issue
and handed to the backend team in `A` issue #38:
https://github.com/animesh0911/qs-paper-generator/issues/38

## Verification

- `cd frontend && npm test`: pass, 10 tests.
- `cd frontend && npm run type-check`: pass.
- `cd frontend && npm run build`: pass.
- `cd frontend && npm run lint`: pass with 1 pre-existing warning in
  `frontend/src/components/ui/button/button.component.tsx`.
- Backend tests: not applicable after backend code changes were removed from
  this frontend issue.

## Review Findings and Fixes

- Code-review gate found no acceptance-scope issues.
- Formatting issue in the chained Zod schema definitions was fixed with
  Prettier before final verification.

## Acceptance-Criteria Check

- `assemblePaper` returns `PaperDocumentV1` instead of the legacy flat `Paper`
  shape for the editor flow: PASS. `assemblePaper` returns `Promise<PaperDocument>`
  and validates the raw response through `assertPaperDocument`.
- Frontend validates required top-level objects, format rules, sections, slots,
  selected questions, alternates, marks, type, and language: PASS. Structural
  validation lives in `paperDocumentSchema`; reference and compatibility checks
  live in `superRefine`.
- Validation fails loud in development and returns user-safe errors in UI:
  PASS. `PaperDocumentContractError` keeps detailed developer text, and the
  dashboard logs details in dev while rendering a safe user message.
- Normalized state includes `questionsById`, `slotsById`, section order, slot
  order by section, slot edits, lock state, and format rules: PASS.
  `normalizePaperDocument` returns those fields.
- Unknown optional fields are ignored and preserved where practical: PASS.
  Schema objects use `passthrough()` and tests cover top-level and slot-level
  additive fields.

Close decision: acceptance criteria pass for the frontend `V` scope. Do not
close until the branch is committed and pushed per the Ralph close-issue gate.
Backend live response alignment is tracked separately in #38.

## Decisions Worth Carrying Forward

- `DocSection.instructions` is optional in TypeScript because the V1 contract
  marks section instructions optional.
- Backend V1 `format` emission and required empty slot alternates are now a
  backend-team handoff in #38, not part of this frontend issue.
- Issue #21 is implemented locally but should not be closed until the relevant
  branch is committed, pushed, and the frontend verification lane is green.
