Title: V: Add selected question action rail and right inspector
Labels: V

## What to build

Implement single-question selection, a contextual action rail anchored to the selected question, and right-inspector modes for Info and Alternatives.

## Acceptance criteria

- [ ] Only one question can be selected at a time.
- [ ] Selecting or keyboard-focusing a question shows an action rail outside the printable content area.
- [ ] Action rail includes Info, Swap, Topic, Easier, Harder, Lock/Unlock, and Ask.
- [ ] Info opens the right inspector with marks, type, chapter, topics, difficulty, CBSE relevance when present, source, lock state, and modified state.
- [ ] Ask focuses the bottom chat with selected-question context.
- [ ] Locked questions keep Info, Ask, manual editing, and Unlock available while replacement actions are disabled.
- [ ] Rail has keyboard-accessible controls and tooltips/labels.

## Blocked by

Blocked by #23.
