---
name: agy-code-review
description: Review an already-committed change against its GitHub issue using a scoped packet plus a clean full-repository snapshot, then independently evaluate and fix justified findings. Use after Codex commits issue-driven implementation work or when the user asks for an Antigravity review of a commit.
---

# Antigravity Code Review

Review committed work through an issue/patch handoff plus a clean full-repository
snapshot at the reviewed commit. Antigravity owns the deep inspection pass;
Codex owns final judgment and fixes.

## Inputs

Identify:

- The commit to review. Default to `HEAD` only when it is the commit just created for the task.
- The GitHub issue number or URL the commit implements.
- Optional context paths worth highlighting to Antigravity. The full repository
  is already available, so these are hints rather than required evidence.

Do not guess the issue from unrelated open issues. If it is not explicit in the conversation,
commit message, or branch name, ask the user.

## Run The Review

Require a clean understanding of the committed scope before invoking Antigravity:

```bash
.claude/skills/agy-code-review/scripts/run_review.sh \
  <commit> <issue-number-or-url> [context-path ...]
```

The script creates a temporary review packet containing only:

- `issue.md` — issue title, body, labels, and comments
- `changed-files.txt` — paths changed by the commit
- `changes.patch` — the commit's changed-file patch
- `changed-files-context/` — full post-commit contents of changed text files
- `review-context/` — optional unchanged interface/contract files explicitly
  passed to the script
- `repository/` — a clean detached worktree at the reviewed commit, available
  for full caller/interface/contract tracing and non-destructive test commands
- `agy.stdout.log` / `agy.stderr.log` — captured CLI narration and diagnostics
- `review.md` — Antigravity's output

On success, stdout contains only the absolute path to `review.md`. Read that
file directly.

Antigravity should use the repository snapshot to do the expensive review work:

- trace changed interfaces through callers and adapters
- verify frontend/backend request and response contracts
- produce an acceptance-criteria coverage audit
- identify missing intent-level tests
- run focused, non-destructive checks when useful

Optional context paths should highlight likely seams, not limit exploration.

The review must remain baseline-aware. A repository gap is actionable against
the reviewed commit only when the commit introduced or worsened it, or when it
is an explicit unmet acceptance criterion of the reviewed issue. Pre-existing
adjacent backlog work must not be promoted into a blocking finding.

## Evaluate Findings

For every finding:

1. Check the cited repository evidence and reproduce only when the finding still
   needs confirmation.
2. Accept it only when it identifies a correctness bug, regression, security problem, missing
   intent-level test, or clear maintainability problem within the issue's scope.
3. Reject speculative features, out-of-scope refactors, style-only preferences, and claims not
   supported by the code.
4. Reject pre-existing adjacent gaps that the reviewed issue does not explicitly
   require.
5. Reject claims marked `needs-context` unless you verify them against the real
   worktree.
6. State briefly why each rejected finding is not being implemented.

Do not blindly apply Antigravity's suggestions.

## Fix And Verify

Apply accepted fixes surgically. Add or update tests when the finding changes behavior or exposes
missing intent coverage. Run the narrow relevant checks first, then the broader required project
checks when practical.

If fixes were made:

1. Summarize accepted and rejected findings.
2. Commit the verified review fixes separately unless the user asked to amend.
3. Report the fix commit and any checks that were not run.

If no findings are accepted, leave the committed change untouched and say so.

## Important CLI Behavior

- Invoke the installed binary as `agy`.
- Put every CLI flag before `--print`; later flags can become prompt text.
- Run Antigravity inside the clean detached repository snapshot. The issue and
  patch packet remain the review handoff and scope anchor.
- Treat `review.md` as the handoff contract, not Antigravity's stdout.
- Require every finding to state confidence: `verified` when supported by packet
  evidence, `inferred` when based only on the patch, or `needs-context` when the
  packet cannot prove the claim.
- Require integration claims to cite the repository file that proves the
  external interface. Missing evidence must be marked `needs-context`, never
  high severity.
- Antigravity may inspect any repository file and run non-destructive commands
  or focused tests. It must not edit files or create commits.
- Require a brief acceptance-criteria coverage section before findings.
- A finding is actionable only if it is caused/worsened by the reviewed commit
  or proves an explicit acceptance criterion remains unmet. Pre-existing
  adjacent work should be omitted or listed separately as non-blocking context.
- Never ask Antigravity to edit the repository during review.
