Title: V: Implement question block tree and slot-level manual edits
Labels: V

## What to build

Map each selected question into an extensible BlockNote block tree with stable editable regions, and store manual edits as paper-slot overrides without mutating the original question-bank question.

## Acceptance criteria

- [ ] Block tree supports `questionContainerBlock`, `questionStemBlock`, `mcqOptionBlock`, `passageBlock`, `subQuestionBlock`, and `internalChoiceBlock`.
- [ ] Region order inside a question is fixed; region reorder/delete is disabled.
- [ ] Each editable region has a stable `regionKey`.
- [ ] Manual edits are stored as `slotId + regionKey` overrides.
- [ ] Original `questionsById[questionId]` content remains immutable in frontend state.
- [ ] Region metadata distinguishes source-locked question text from editable paper chrome such as title, section headings, instructions, marks, and formatting fields.
- [ ] Edited questions show a “Modified from source” indicator in the editor and inspector.
- [ ] Restore original clears slot-level overrides for the selected question.

## Blocked by

Blocked by #22.
