Title: V: Add mocked PaperDocumentV1 with CBSE format rules and rich alternates
Labels: V

## What to build

Create the frontend development fixture for the BlockNote paper editor: a mocked `PaperDocumentV1` that includes the required top-level `format` object, ordered sections/slots, stable IDs, broad slot-wise alternatives, and representative CBSE Class 10 Science question types.

## Acceptance criteria

- [ ] Mock payload includes `schemaVersion`, `request`, `template`, `format`, `paper`, and `questions`.
- [ ] `format` includes V1 CBSE page/chrome/numbering/section/question-region rules.
- [ ] Mock includes MCQ, assertion-reason, short answer, long answer with subparts, case-based, and internal choice examples.
- [ ] Every slot has stable `slotId`, `displayNumber`, `marks`, `questionType`, `selectedQuestionId`, `locked`, and `alternateQuestionIds`.
- [ ] Alternates include topic/chapter tags, difficulty, optional CBSE relevance, source, language, marks, and question type.
- [ ] No frontend code has to infer CBSE section/order rules that should be contract data.

## Blocked by

None - can start immediately.
