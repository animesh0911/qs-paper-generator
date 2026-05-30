Title: V: Add AI pending-state locks and document revision checks
Labels: V
GitHub: #35

## What to build

Protect the editor from stale AI proposals by tracking document revisions and blocking conflicting structured mutations while AI jobs are pending.

## Acceptance criteria

- [ ] Frontend maintains an in-memory monotonic `documentRevision`.
- [ ] AI job requests include `baseRevision`.
- [ ] AI job results can preview/apply only when `baseRevision` matches the current revision.
- [ ] While an AI edit or review job that can propose changes is pending, structured mutations such as swap, reorder, lock/unlock, and section edits are blocked.
- [ ] Reading, scrolling, selection, and inspector navigation remain available while jobs are pending.
- [ ] Stale proposal UI explains why Apply is disabled and offers Dismiss.

## Blocked by

Blocked by #33.
