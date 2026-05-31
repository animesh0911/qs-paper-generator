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
6.5 Download anything and everything you need for the dev work.
7. Run local verification.
8. Run the `code-review` skill on the diff.
9. Fix review findings.
10. Re-run verification.
11. Prune the scratchboard to the final handoff shape: Selected Skills, Public
    Interfaces, and Main Flow only.
12. In Main Flow, explain the data/control flow created or changed by the
    issue, with code-level references to the key interfaces, API calls, schemas,
    state shapes, persistence models, and tests.
13. Re-read the GitHub issue for obvious scope misses before commit.
14. Commit and push.
15. Close the GitHub issue after the pushed branch contains the completed,
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

Every implementation issue gets a scratchboard. During implementation, it may
temporarily hold assumptions, RED/GREEN notes, verification notes, or review
findings. Before handoff, prune it back to exactly these sections:

- Selected Skills
- Public Interfaces
- Main Flow

Scratchboards are working notes, not a permanent log. Keep them lean. Do not
duplicate acceptance criteria, paste issue checklists, or retain verification
transcripts unless a specific result changes the public interface or main flow.
The final scratchboard should read like a compact handoff from the implementer
to a human maintainer: identify the main flow created by the work and annotate
it with code references. Depending on the issue, this may be a data flow, API
request flow, UI state flow, persistence flow, or validation flow.

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
the delivered slice and any known verification caveats. Before closing, re-read
the issue for obvious scope misses; do not close if the verified implementation
clearly does not deliver the requested slice.
