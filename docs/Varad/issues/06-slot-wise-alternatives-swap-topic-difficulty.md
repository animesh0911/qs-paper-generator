Title: V: Implement slot-wise alternatives, swap, topic, easier, and harder flows
Labels: V

## What to build

Use each slot’s `alternateQuestionIds` to show safe replacement candidates and apply deterministic filters for normal swap, topic change, easier, and harder actions.

## Acceptance criteria

- [ ] Swap shows all valid slot-wise alternatives in the right inspector.
- [ ] Topic filters alternatives by selected topic/chapter metadata.
- [ ] Easier and Harder filter alternatives by difficulty relative to the current question.
- [ ] Candidate snippets show question text, marks/type, chapter/topic chips, difficulty, relevance when present, and source.
- [ ] Applying a replacement preserves `slotId`, section, marks, type, and display numbering.
- [ ] Applying a replacement updates selected question ID and clears old slot edits after warning.
- [ ] Empty state includes “Show all alternatives” and disabled “Find more in question bank” placeholder.

## Blocked by

Blocked by #24.
