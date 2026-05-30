# Contract values used directly as DB enum values

`bank.models.QuestionType` enum values are **identical to the `questionType` strings in `contracts/v1_contract.md`** (`"mcq"`, `"assertion_reason"`, `"very_short_answer"`, ...). The previous `_QTYPE_CONTRACT` mapping dict in `PaperDocumentBuilder` is deleted. `Section` already followed this pattern (`"A"`..`"E"` match `sectionId`); `QuestionType` is brought in line.

## Why

The mapping layer was a constant source of drift: enum names like `MCQ`/`VSA`/`SA`/`LA`/`CASE` carried a hidden contract obligation that wasn't visible at the model definition. Adding `assertion_reason` and `internal_choice` (needed for V1 ingestion of CBSE PYQs) forced a choice between (a) extending the enum *and* the mapping dict, or (b) collapsing them. We picked (b) to make the contract the single source of truth — when the contract gains a new `questionType`, exactly one enum value is added, and every layer (parser, picker, template, builder, frontend) sees the same string.

## Consequences

- Migration `0004` rewrites existing rows' qtype values (`MCQ` → `mcq`, etc.) and updates 11 seeded questions in `seed_questions.py`.
- `papers.template.Slot.qtype`, `papers.picker.QuestionPool` keys, `bank.ingestor.SECTION_DEFAULT_QTYPE`, and all tests using the old strings move to the new values.
- DB enum is publicly visible in API responses. If we ever want to rename a contract value, it becomes a coordinated frontend + backend + DB migration. Accepted because the contract is supposed to be stable across V1.
