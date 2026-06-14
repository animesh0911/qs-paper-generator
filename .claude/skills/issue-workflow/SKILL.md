---
name: issue-workflow
description: Start isolated issue branches/worktrees and run token-efficient changed-area verification. Use when beginning a GitHub issue, preparing a clean issue commit, running focused RED/GREEN checks, or running the full pre-commit verification gate.
---

# Issue Workflow

Keep issue work isolated and let deterministic tools select context and checks.

## Start An Issue

1. Identify the issue number and committed base. Use `origin/main` unless the
   issue explicitly depends on an unmerged committed branch.
2. Run:

   ```bash
   .claude/skills/issue-workflow/scripts/start_issue.sh <issue> [base-ref]
   ```

3. Continue all issue work from the path printed by the script.
4. Check GitNexus freshness, refresh a stale index, then use GitNexus query,
   context, and impact tools before broad file reads.

The script fetches `origin` and creates a new branch in a separate clean
worktree. Never implement an issue in a checkout that already has unrelated
changes.

## Verify An Issue

During each RED/GREEN slice, run affected checks:

```bash
.claude/skills/issue-workflow/scripts/verify_issue.sh focused
```

Before review and commit, run the full checks for every changed area:

```bash
.claude/skills/issue-workflow/scripts/verify_issue.sh full
```

Set `BASE_REF` when the issue branch is not based on `origin/main`. Focused
backend verification requires `pytest-testmon`; focused frontend verification
uses Vitest's changed-file selection. Full verification deliberately runs the
complete changed-area suites.

The script fails when required tooling is unavailable. Report skipped commands
instead of describing the verification gate as passed.
