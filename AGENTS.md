# AGENTS.md — 12-rule template

These rules apply to every task in this project unless explicitly overridden.
Bias: caution over speed on non-trivial work. Use judgment on trivial tasks.

## Coding standards

Mechanical conventions (formatters, linters, file naming, docstrings, import
order, pre-commit gates) live in [`docs/coding-standards.md`](docs/coding-standards.md).
Read it before writing or reviewing code; conformance is mandatory and Rule 11
takes precedence over personal taste.

Domain vocabulary lives in [`CONTEXT.md`](CONTEXT.md) — use those terms
exactly in module names, class names, and docstrings.

## Agent skills

### Issue tracker

Issues and PRDs live in GitHub Issues for `animesh0911/qs-paper-generator`;
Varad/editor work uses the `V` label. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default Matt Pocock triage role names when triaging; create labels only
when triage work starts needing them. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repo with root `CONTEXT.md` and optional ADRs under
`docs/adr/`. See `docs/agents/domain.md`.

## Rule 1 — Think Before Coding
State assumptions explicitly. If uncertain, ask rather than guess.
Present multiple interpretations when ambiguity exists.
Push back when a simpler approach exists.
Stop when confused. Name what's unclear.

## Rule 2 — Simplicity First
Minimum code that solves the problem. Nothing speculative.
No features beyond what was asked. No abstractions for single-use code.
Test: would a senior engineer say this is overcomplicated? If yes, simplify.

## Rule 3 — Surgical Changes
Touch only what you must. Clean up only your own mess.
Don't "improve" adjacent code, comments, or formatting.
Don't refactor what isn't broken. Match existing style.

## Rule 4 — Goal-Driven Execution
Define success criteria. Loop until verified.
Don't follow steps. Define success and iterate.
Strong success criteria let you loop independently.

## Rule 5 — Use the model only for judgment calls
Use me for: classification, drafting, summarization, extraction.
Do NOT use me for: routing, retries, deterministic transforms.
If code can answer, code answers.

## Rule 6 — Token budgets are not advisory
Per-task: 4,000 tokens. Per-session: 30,000 tokens.
If approaching budget, summarize and start fresh.
Surface the breach. Do not silently overrun.

## Rule 7 — Surface conflicts, don't average them
If two patterns contradict, pick one (more recent / more tested).
Explain why. Flag the other for cleanup.
Don't blend conflicting patterns.

## Rule 8 — Read before you write
Before adding code, read exports, immediate callers, shared utilities.
"Looks orthogonal" is dangerous. If unsure why code is structured a way, ask.

## Rule 9 — Tests verify intent, not just behavior
Tests must encode WHY behavior matters, not just WHAT it does.
A test that can't fail when business logic changes is wrong.

## Rule 10 — Checkpoint after every significant step
Summarize what was done, what's verified, what's left.
Don't continue from a state you can't describe back.
If you lose track, stop and restate.

## Rule 11 — Match the codebase's conventions, even if you disagree
Conformance > taste inside the codebase.
If you genuinely think a convention is harmful, surface it. Don't fork silently.

## Rule 12 — Fail loud
"Completed" is wrong if anything was skipped silently.
"Tests pass" is wrong if any were skipped.
Default to surfacing uncertainty, not hiding it.

## Rule 13 — Never invoke a paid LLM API without explicit consent
Any action that calls an LLM API costs real money. STOP and ask for explicit
consent before running ANYTHING that hits an LLM API — extraction, answer
generation, management commands, scripts, tests, or live endpoints that call
Gemini / OpenAI / Anthropic / any model provider.
This includes re-runs, retries, and "just to verify" calls. One run = one
charge; assume nothing is free.
Do NOT decide on your own that a run is worth it. Present what will run, how
many API calls it makes, and which model, then wait for a yes.
Also surface any config that changes model/cost (e.g. `GEMINI_MODEL` in `.env`)
the moment you notice it conflicts with stated intent — never silently proceed.

## Rule 14 — Sync before you branch
Before creating a branch or opening a PR, fetch and fast-forward the base
(`git fetch origin` then `git pull --ff-only`, or branch directly from
`origin/main`). Never branch off stale local state — the session's starting
commit may already be behind the remote.
After a merge, verify against the *integrated* result on the updated base, not
just your branch — your pre-merge test run proves nothing about what landed.

## Rule 15 — Antigravity-review every PR before merge
After opening a PR and before merging it, run the `agy-code-review` skill
against the PR's head commit (pass `-` as the issue when the PR has no linked
issue). This gate is mandatory on EVERY PR — feature, refactor, docs, or chore
— and applies to every agent (Codex and Claude alike).
Evaluate the findings, apply every accepted one as fixes (a separate commit),
push, and only THEN merge. Never merge a PR that still has unaddressed accepted
findings. If no findings are accepted, say so explicitly and merge.
If the `agy` CLI is missing, install it (`brew install --cask antigravity-cli`)
rather than skipping the gate.
