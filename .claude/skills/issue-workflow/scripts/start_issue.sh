#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <issue-number> [base-ref]" >&2
  exit 2
}

issue_number="${1:-}"
base_ref="${2:-origin/main}"

[[ "$issue_number" =~ ^[0-9]+$ ]] || usage

repo_root="$(git rev-parse --show-toplevel)"
repo_name="$(basename "$repo_root")"
worktree_root="${ISSUE_WORKTREE_ROOT:-$(dirname "$repo_root")}"
worktree_path="${ISSUE_WORKTREE_PATH:-$worktree_root/$repo_name-issue-$issue_number}"
branch="${ISSUE_BRANCH:-codex/issue-$issue_number}"

git -C "$repo_root" fetch origin
git -C "$repo_root" rev-parse --verify --quiet "$base_ref^{commit}" >/dev/null || {
  echo "Base ref is not a committed revision: $base_ref" >&2
  exit 1
}

if git -C "$repo_root" show-ref --verify --quiet "refs/heads/$branch"; then
  echo "Local branch already exists: $branch" >&2
  exit 1
fi

if git -C "$repo_root" show-ref --verify --quiet "refs/remotes/origin/$branch"; then
  echo "Remote branch already exists: origin/$branch" >&2
  exit 1
fi

if [[ -e "$worktree_path" ]]; then
  echo "Worktree path already exists: $worktree_path" >&2
  exit 1
fi

git -C "$repo_root" worktree add -b "$branch" "$worktree_path" "$base_ref"

if [[ -n "$(git -C "$worktree_path" status --porcelain)" ]]; then
  echo "New worktree is unexpectedly dirty: $worktree_path" >&2
  exit 1
fi

printf 'Issue: %s\nBranch: %s\nBase: %s\nWorktree: %s\n' \
  "$issue_number" "$branch" "$base_ref" "$worktree_path"
