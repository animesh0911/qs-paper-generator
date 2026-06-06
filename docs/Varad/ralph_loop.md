# Varad Ralph Loop

Use this loop for each `V` issue. Keep this file project-specific; detailed
skill behavior lives in `.claude/skills`.

## Loop

1. Pick one GitHub issue.
2. Read the issue, `contracts/v1_contract.md`, relevant PRDs, and any prior
   scratchboard for the issue.
3. Inspect `.claude/skills`, choose the issue-relevant skills, read each chosen
   `SKILL.md` before relying on it.
4. Define the public interface and issue-level success criteria. Create a
   scratchboard only when the issue needs durable decisions or multi-step notes.
5. Download or inspect any external artifacts needed for the work.
6. Implement with `tdd`: one RED/GREEN slice at a time.
7. Run focused verification after each slice; run the full changed-area
   verification gate when the issue implementation is complete.
8. Run the `code-review` skill on the uncommitted issue diff.
9. Fix accepted review findings and re-run the affected focused checks.
10. Re-read the GitHub issue for obvious scope misses.
11. Run the full changed-area verification gate.
12. In Main Flow, explain the data/control flow created or changed by the
    issue, with code-level references to the key interfaces, API calls, schemas,
    state shapes, persistence models, and tests.
13. Commit only that issue's files. When executing multiple issues, keep
    issue-scoped commits even when they share a branch.
14. Run the `agy-code-review` skill on the issue commit. Antigravity owns the
    deep second pass: full-repository tracing, issue-scope audit, cross-boundary
    contract checks, and missing intent-level test analysis.
15. Codex validates Antigravity findings against the real worktree, fixes
    accepted findings in a separate commit, and runs focused checks. Repeat the
    full verification gate only when the fix has meaningful blast radius.
16. Push the branch.
17. Close the GitHub issue only after the pushed branch contains the completed,
    verified work.
18. Give the user a brief summary of what changed, including the concrete code
    behavior affected.


## Skill Use

Use skills freely; they are part of the workflow, not optional decoration. Read
the relevant `SKILL.md` before using a skill. If you are not confident about the
skill's workflow, read it thoroughly before acting.

- `tdd`: default implementation skill. Use for feature work, bug fixes,
  contract changes, and any issue with acceptance criteria.
- `code-review`: mandatory before commit. Use on the diff after implementation
  and verification; fix findings before final verification.
- `zoom-out`: use when the code area is unfamiliar and you need a fast map of
  modules, callers, and seams before editing.
- `diagnose`: use when a failure is confusing, flaky, or not reproducible from
  the obvious command.
- `prototype`: use only for unclear UI/state design where a small spike reduces
  risk before the TDD path.
- `grill-with-docs`: use when terminology, contract ownership, or domain docs
  are unclear and need a sharper decision.
- `to-issues`: use when the current issue is too large and should be split
  before implementation.
- `improve-codebase-architecture`: use when the solution starts spreading
  shallow logic across modules and needs a deeper interface.


## TDD Gate

Name the public interface under test in the scratchboard, then follow
`.claude/skills/tdd/SKILL.md`.

## Verification Gate

Use two levels:

- **Focused checks:** the narrow tests/type checks covering the current
  RED/GREEN slice or review fix.
- **Full changed-area checks:** run once after implementation and again only
  when review fixes have meaningful blast radius.

Frontend:

```bash
cd frontend
npm test
npm run type-check
npm run build
npm run lint
```

Backend:

```bash
cd backend
pytest
python -m compileall .
```

If a command is unavailable or skipped, record that explicitly in the final
answer and scratchboard.

## Code-Review Gate

Run `.claude/skills/code-review/SKILL.md` on the diff. Fix findings, then
re-run affected focused checks. Cap review/fix at two rounds; document remaining
issues.

After the issue commit, run `.claude/skills/agy-code-review/SKILL.md`.
Antigravity receives a clean full-repository snapshot at the reviewed commit and
owns the expensive context gathering: trace callers, verify external interfaces,
re-read issue scope, and identify missing intent-level tests. Codex should not
duplicate that exploration by default; it validates concrete findings and fixes
accepted ones. Optional explicit context paths may still be passed as hints.

## Commit Gate

- Stage only files belonging to the current issue.
- Keep unrelated dirty-worktree changes untouched and unstaged.
- When one branch contains multiple issues, create one implementation commit per
  issue. Antigravity review fixes go in a separate commit rather than silently
  amending the reviewed commit.


## Close-Issue Gate

Closing an issue means shipping the change: commit the relevant files, push the
branch, then close the GitHub issue with a short completion comment that names
the delivered slice and any known verification caveats. Before closing, re-read
the issue for obvious scope misses; do not close if the verified implementation
clearly does not deliver the requested slice.
