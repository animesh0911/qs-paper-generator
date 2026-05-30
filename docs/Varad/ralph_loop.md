# Varad Ralph Loop

Use this loop for each `V` issue. Keep this file project-specific; detailed
skill behavior lives in `.claude/skills`.

## Loop

1. Pick one GitHub issue.
2. Read the issue, `docs/Varad/v1_contract.md`, relevant PRDs, and any prior
   scratchboard for the issue.
3. Inspect `.claude/skills`, choose the issue-relevant skills, read each chosen
   `SKILL.md` before relying on it, and record the selected skills plus why in
   the scratchboard.
4. Create a fresh scratchboard in the issue owner's docs directory:
   `docs/Varad/scratchboards/issue-XX-implementation.md` for `V` issues, or
   `docs/Animesh/scratchboards/issue-XX-implementation.md` for `A` issues.
5. Define the public interface under test.
6. Implement with `tdd`: one RED/GREEN slice at a time.
7. Run local verification.
8. Run the `code-review` skill on the diff.
9. Fix review findings.
10. Re-run verification.
11. Re-check every acceptance criterion from the GitHub issue against the
    verified implementation.
12. Update scratchboard.
13. Commit and push.
14. Close the GitHub issue after the pushed branch contains the completed,
    verified work.

## Agent Invocation

Use this prompt shape when assigning an issue to an agent:

```text
Execute the Varad Ralph Loop for GitHub issue #XX.
Read docs/Varad/ralph_loop.md first.
Use the issue, docs/Varad/v1_contract.md, relevant PRDs, and any existing
scratchboard as context.
If local work for this issue already exists, review and continue it instead of
restarting or reverting it.
Do not implement future issue scope.
Before final response, run the code-review gate and verification gate.
```

For in-progress issues, add:

```text
This issue already has local uncommitted work. Treat it as in-progress:
inspect the diff, check it against the scratchboard, complete missing parts,
run code-review, then commit only the relevant files.
```

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

## Scratchboard

Every implementation issue gets a scratchboard with:

- issue link
- selected skills
- assumptions
- public interfaces
- RED/GREEN slices
- verification commands/results
- review findings and fixes
- decisions worth carrying forward
- final code-level change summary

Scratchboards are working notes. Keep them useful, not polished. At the end of
the issue, add a concise code-level summary so a human can see what changed
without reconstructing the diff. Name the touched modules/files and the concrete
interfaces, schemas, state shapes, tests, or behavior changed.

Keep owner scratchboards separated by directory. Varad/frontend issue notes
belong under `docs/Varad/scratchboards/`; Animesh/backend issue notes belong
under `docs/Animesh/scratchboards/`. Do not create backend handoff notes in the
Varad scratchboard directory, or frontend implementation notes in the Animesh
scratchboard directory.

## TDD Gate

Name the public interface under test in the scratchboard, then follow
`.claude/skills/tdd/SKILL.md`.

## Verification Gate

Run the commands relevant to the changed area.

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

## Acceptance-Criteria Gate

After TDD, code review, and verification, re-read the GitHub issue and check
each acceptance criterion against the verified implementation.

- If every acceptance criterion passes, record that in the scratchboard and
  proceed to commit, push, and the close-issue gate.
- If any acceptance criterion does not pass, do not close the issue. Add the
  GitHub label `needs more work`, leave a short issue comment naming the failed
  criteria and the blocker or follow-up, record the result in the scratchboard,
  and move on to the next issue.
- If scope has intentionally moved to another issue, link the follow-up issue
  when explaining why the current issue is or is not complete.

## Code-Review Gate

Run `.claude/skills/code-review/SKILL.md` on the diff. Fix findings, then
re-run verification. Cap review/fix at two rounds; document remaining issues.

## Commit Gate

Before commit:

- scratchboard is updated
- verification results are known
- code-review findings are fixed or documented
- unrelated local changes remain unstaged
- commit message names the issue or concrete slice

Do not close the GitHub issue until the pushed branch contains the completed
work and verification has passed.

## Close-Issue Gate

Closing an issue means shipping the change: commit the relevant files, push the
branch, then close the GitHub issue with a short completion comment that names
the delivered slice and any known verification caveats. Once verification has
passed and every acceptance criterion passes, do not wait for extra user
confirmation before committing, pushing, and closing the issue.
