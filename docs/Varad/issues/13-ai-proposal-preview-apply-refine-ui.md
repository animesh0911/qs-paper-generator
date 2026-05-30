Title: V: Implement AI proposal preview, apply, dismiss, and refine UI
Labels: V
GitHub: #33

## What to build

Render live AI edit proposals in the editor using a BlockNote-AI-inspired preview flow without depending on BlockNote AI packages.

## Acceptance criteria

- [ ] Completed edit proposals auto-preview affected fields in the paper canvas.
- [ ] Bottom chat shows a max two-line summary, affected areas, and action buttons only after the response is ready.
- [ ] Right inspector shows detailed before/after diffs, validation errors, warnings, and affected patch paths.
- [ ] Apply is disabled for blocking validation errors and stale base revisions.
- [ ] Apply updates canonical paper state only through existing reducers, then BlockNote re-renders from canonical state.
- [ ] Dismiss clears the active proposal.
- [ ] Refine sends the full paper, base revision, original instruction, current proposal, refinement instruction, and guardrails; the refined result replaces the active proposal and auto-previews.
- [ ] Only one active job/proposal exists at a time.

## Blocked by

Blocked by #31, #32, #22, #28.
