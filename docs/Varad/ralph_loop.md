# Varad Ralph Loop

Use this loop for each `V` issue. Keep this file project-specific; detailed
skill behavior lives in `.claude/skills`.

## Loop

1. Pick one GitHub issue, identify its committed base, and run
   `.claude/skills/issue-workflow/scripts/start_issue.sh <issue> [base-ref]`.
   Continue all issue work from the clean worktree printed by the script.
2. Read the issue, `contracts/v1_contract.md`, and relevant PRDs.
3. Inspect `.agents/skills` and `.claude/skills`, choose the smallest
   issue-relevant skill set, and read each chosen `SKILL.md` before relying on
   it. Use connected structured tools for issue metadata and code maps before
   loading broad file context.
4. Define the public interface and issue-level success criteria.
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

- `issue-workflow`: mandatory issue start and verification workflow. Use
  `start_issue.sh` before implementation and `verify_issue.sh` for focused and
  full changed-area gates.
- GitHub issue skill/tooling: prefer structured issue, PR, label, and comment
  reads over manually loading web pages.
- `gitnexus-exploring`: use a bounded query/context pass to find execution
  flows, callers, and ownership before direct source reads. If the index is
  stale or misses uncommitted code, say so and verify against the worktree
  instead of repeating broad searches.
- `tdd`: default implementation skill. Use for feature work, bug fixes,
  contract changes, and any issue with acceptance criteria.
- `code-review`: mandatory before commit. Use on the diff after implementation
  and verification; fix findings before final verification.
- `zoom-out`: use when the code area is unfamiliar and you need a fast map of
  modules, callers, and seams before editing.
- `diagnose`: use when a failure is confusing, flaky, or not reproducible from
  the obvious command. If deterministic automation is impossible and a human
  must perform the repro, copy and tailor
  `.claude/skills/diagnose/scripts/hitl-loop.template.sh` as the last-resort
  feedback loop.
- `prototype`: use only for unclear UI/state design where a small spike reduces
  risk before the TDD path.
- `grill-with-docs`: use when terminology, contract ownership, or domain docs
  are unclear and need a sharper decision.
- `to-issues`: use when the current issue is too large and should be split
  before implementation.
- `improve-codebase-architecture`: use when the solution starts spreading
  shallow logic across modules and needs a deeper interface.

Keep skill use token-bounded: choose only skills that change the next decision,
reuse their structured output, and do not duplicate exploration already owned
by GitNexus or the post-commit Antigravity review.


## TDD Gate

Name the public interface under test in the implementation plan, then follow
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
answer.

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

Invoke the skill through its packet-building script:

```bash
.claude/skills/agy-code-review/scripts/run_review.sh \
  <commit> <issue-number-or-url> [context-path ...]
```

The script bounds the initial review packet to the issue, patch, changed-file
contents, and explicitly highlighted context while still giving Antigravity a
clean full repository for evidence-driven follow-up.

The Antigravity review wrapper must use `Gemini 3.5 Flash (High)` exactly. It
prevalidates the label against `agy models` and verifies the selected model in
the CLI log because `agy --model` can silently fall back for an invalid label.

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
