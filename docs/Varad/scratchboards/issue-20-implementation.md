# Scratchboard: Issue #20 Implementation

GitHub: https://github.com/animesh0911/qs-paper-generator/issues/20

## Skill Use

Primary skill: `tdd`.

Relevant rules from the skill:

- Test through public interfaces, not implementation details.
- Use vertical slices, not a horizontal test dump.
- Keep the public interface small.
- Avoid mocks for our own modules.

## Public Interface Under Test

```ts
paperDocumentSchema.parse(mockPaperDocumentV1);
```

This is the frontend API-boundary contract. If the mock does not parse here,
the editor should not trust it.

Secondary public fixture:

```ts
mockPaperDocumentV1;
```

The fixture is a development stand-in for backend `PaperDocumentV1`.

## Why This Issue Is More Than "Just Mock Data"

The issue is primarily about creating the mocked backend contract, but the mock
is only useful if the frontend can prove it matches the runtime schema. So the
slice includes:

- Vitest runner
- contract tests
- TypeScript contract types
- Zod runtime schema
- mocked `PaperDocumentV1`

It does **not** include:

- normalization
- BlockNote mapping
- editor UI
- backend generation changes

## Completed TDD Slices

### Slice 1: API boundary accepts the mock

RED: test imported `mockPaperDocumentV1` and parsed it with
`paperDocumentSchema`; failed because the mock did not exist.

GREEN: added Vitest, schema updates, TypeScript types, and the mock fixture.

### Slice 2: slot question references are closed over `questions[]`

Behavior: every selected/alternate question id referenced by slots exists in
the document's `questions[]`.

### Slice 3: selected and alternate questions are slot-compatible

Behavior: referenced questions match slot marks, question type, and paper
language.

### Slice 4: format rules are contract data

Behavior: mock carries page, paper chrome, numbering, section movement,
question-region, and MCQ layout rules so the editor does not need to hardcode
CBSE structure.

### Slice 5: representative content shapes exist

Behavior: mock contains real content shapes for MCQ, assertion-reason, short
answer, long answer with subparts, case-based passage/subparts, internal choice,
diagram placeholder, and table content.

### Slice 6: action tray metadata exists

Behavior: every slot has stable action fields and every alternate carries
chapter/topic/difficulty/source/language/marks/type metadata needed by Info,
Swap, Topic, Easier, and Harder flows.

## Acceptance Criteria Coverage

- Top-level `schemaVersion`, `request`, `template`, `format`, `paper`,
  `questions`: covered by schema parse test.
- `format` page/chrome/numbering/section/question-region rules: covered.
- Representative question shapes: covered.
- Slot stable fields: covered by schema parse and action-tray metadata test.
- Alternates metadata: covered by action-tray metadata test.
- Closed question references: covered.
- Slot compatibility: covered.

## Interface Explanation For Final Answer

- `mockPaperDocumentV1`: realistic fixture shaped like backend output.
- `paperDocumentSchema`: runtime API-boundary validator.
- `PaperDocument` types: compile-time mirror of the contract.

## Verification

- `npm test`: pass, 6 tests.
- `npm run type-check`: pass.
- `npm run build`: pass.
- `npm run lint`: 0 errors, 1 existing warning in
  `frontend/src/components/ui/button/button.component.tsx`.

## Notes

- Do not make a normalization helper in this issue. That belongs to #21.
- Do not add React/BlockNote behavior here.
- Keep tests behavioral: "mock parses", "references resolve",
  "slot-compatible", "representative shapes exist".
- Review note: the stricter frontend schema now reflects the finalized Varad
  contract, while current backend `PaperDocumentBuilder` still needs to emit
  top-level `format` and always-present slot fields. Backend alignment should be
  handled before relying on live `/papers/assemble` for the editor flow.
