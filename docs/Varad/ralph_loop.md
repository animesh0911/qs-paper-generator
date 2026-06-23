# Varad Ralph Loop

Use this loop for each `V` issue.

## Loop

1. Pick one GitHub issue, identify its committed base, and run
   `.claude/skills/issue-workflow/scripts/start_issue.sh <issue> [base-ref]`.
   Continue all issue work from the clean worktree printed by the script.
1.1 You don't have to read all relevant skills. We are token budget mode.
2. Use /implement skill to implement the issue. This skill is there in pi.
3. Use the codex-agy-bridge MCP for code review.
4. Rectify the findings. You can also reject findings.
10. Re-read the GitHub issue for obvious scope misses.
16. Push the branch.

18. You are only allowed to close the issue after the changes are succesfully merged to main. Take pull from main , rebase the changes. push and merge to main.
19. Use building-mental-map skill to update the vault at
    `/Users/varad/Obsidian Vault/AI Research/`


#
