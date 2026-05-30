Title: V: Support in-section question reorder, derived numbering, and one-step undo
Labels: V

## What to build

Allow questions to be reordered within the same section while preventing cross-section moves, recomputing display numbers, and supporting one-step app-level undo for structured actions.

## Acceptance criteria

- [ ] Question containers can be reordered only within their current section.
- [ ] Cross-section moves are rejected and visually prevented where possible.
- [ ] Display numbers are derived from current paper order and recomputed after reorder.
- [ ] One-step undo supports swap, topic/easier/harder replacement, lock/unlock, restore original, and reorder.
- [ ] New structured actions replace the previous app-level undo entry.
- [ ] BlockNote typing undo still works for text editing.

## Blocked by

Blocked by #23.
