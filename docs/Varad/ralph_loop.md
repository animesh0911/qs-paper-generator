# Varad Ralph Loop

Use this loop for each `V` issue.

## Loop

1. Pick one GitHub issue, identify its committed base, and run
   `.claude/skills/issue-workflow/scripts/start_issue.sh <issue> [base-ref]`.
   Continue all issue work from the clean worktree printed by the script.
1.1 You dont have to read all relevant skills. We are token budget mode.
2. use /implement skill to implement the issue. This skill is there in codex
3. use the codex-agy-bridge for code review
4. Rectify the findings then fix the findings. You can also reject the findings.
10. Re-read the GitHub issue for obvious scope misses.
16. Push the branch.
17. Close the GitHub issue only after the pushed branch contains the completed,
    verified work.
18. Give me a brief of what changed. explain the flow. Explain relevant code. Make sure user understand the current state of things after issue is completed.


#