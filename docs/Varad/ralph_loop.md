# Varad Ralph Loop

Use this loop for each `V` issue. Keep this file project-specific; detailed
skill behavior lives in `.claude/skills`.

## Loop

1. Pick one GitHub issue and identify its committed base. Use `origin/main`
   unless the issue explicitly depends on an unmerged committed branch.
2. Run the `issue-workflow` start script and continue from its clean issue
   worktree.
3. Read the issue, `contracts/v1_contract.md`, relevant PRDs, and any prior
   scratchboard for the issue.
4. Inspect `.claude/skills`, choose the issue-relevant skills, read each chosen
   `SKILL.md` before relying on it.
5. Check GitNexus freshness. Refresh a stale index, then use query, context,
   and impact results to identify the smallest relevant code surface before
   broad file reads.
6. Define the public interface and issue-level success criteria. Create a
   scratchboard only when the issue needs durable decisions or multi-step notes.
7. Download or inspect any external artifacts needed for the work.
8. Implement with `tdd`: one RED/GREEN slice at a time.
9. Run `issue-workflow` focused verification after each slice; run its full
   changed-area verification when the issue implementation is complete.
10. Run the `code-review` skill on the uncommitted issue diff.
11. Fix accepted review findings and re-run affected focused checks.
12. Re-read the GitHub issue for obvious scope misses.
13. Run the `issue-workflow` full changed-area verification gate.
14. In Main Flow, explain the data/control flow created or changed by the
    issue, with code-level references to the key interfaces, API calls, schemas,
    state shapes, persistence models, and tests.
15. Commit only that issue's files. When executing multiple issues, keep
    issue-scoped commits even when they share a branch.
16. Run the `agy-code-review` skill on the issue commit. Antigravity owns the
    deep second pass: full-repository tracing, issue-scope audit, cross-boundary
    contract checks, and missing intent-level test analysis.
17. Codex validates Antigravity findings against the real worktree, fixes
    accepted findings in a separate commit, and runs focused checks. Repeat the
    full verification gate only when the fix has meaningful blast radius.
18. Push the branch.
19. Close the GitHub issue only after the pushed branch contains the completed,
    verified work.
20. Give the user a brief summary of what changed, including the concrete code
    behavior affected.


## Skill Use

Use skills freely; they are part of the workflow, not optional decoration. Read
the relevant `SKILL.md` before using a skill. If you are not confident about the
skill's workflow, read it thoroughly before acting.

- `tdd`: default implementation skill. Use for feature work, bug fixes,
  contract changes, and any issue with acceptance criteria.
- `issue-workflow`: mandatory at issue start and verification gates. Use it to
  isolate work from unrelated changes and select deterministic changed-area
  checks.
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
  RED/GREEN slice or review fix. Run `issue-workflow` focused verification;
  backend selection uses `pytest-testmon`.
- **Full changed-area checks:** run once after implementation and again only
  when review fixes have meaningful blast radius. Run `issue-workflow` full
  verification.

Run from the issue worktree root:

```bash
.claude/skills/issue-workflow/scripts/verify_issue.sh full
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
