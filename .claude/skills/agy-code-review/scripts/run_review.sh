#!/bin/sh
set -eu

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <commit> <issue-number-or-url> [context-path ...]" >&2
  exit 2
fi

commit=$1
issue=$2
shift 2

command -v git >/dev/null 2>&1 || {
  echo "git is not installed or not on PATH" >&2
  exit 127
}
command -v gh >/dev/null 2>&1 || {
  echo "gh is not installed or not on PATH" >&2
  exit 127
}
command -v agy >/dev/null 2>&1 || {
  echo "agy is not installed or not on PATH" >&2
  exit 127
}

repo_root=$(git rev-parse --show-toplevel)
commit_sha=$(git rev-parse --verify "${commit}^{commit}")
packet_dir=$(mktemp -d "${TMPDIR:-/tmp}/agy-code-review.XXXXXX")
review_file="$packet_dir/review.md"
changed_context_dir="$packet_dir/changed-files-context"
review_context_dir="$packet_dir/review-context"
repo_context_dir="$packet_dir/repository"
mkdir -p "$changed_context_dir" "$review_context_dir"

cleanup() {
  git -C "$repo_root" worktree remove --force "$repo_context_dir" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

git -C "$repo_root" diff-tree --root --no-commit-id --name-only -r "$commit_sha" \
  > "$packet_dir/changed-files.txt"
git -C "$repo_root" show --format=fuller --find-renames --find-copies "$commit_sha" \
  > "$packet_dir/changes.patch"
gh issue view "$issue" --json number,title,state,labels,body,comments \
  --template '# Issue #{{.number}}: {{.title}}

State: {{.state}}
Labels: {{range .labels}}{{.name}} {{end}}

## Body

{{.body}}

## Comments
{{range .comments}}
### {{.author.login}}

{{.body}}
{{end}}
' > "$packet_dir/issue.md"

if [ ! -s "$packet_dir/changed-files.txt" ]; then
  echo "commit has no changed files: $commit_sha" >&2
  exit 1
fi

while IFS= read -r path; do
  [ -n "$path" ] || continue
  if git -C "$repo_root" cat-file -e "$commit_sha:$path" 2>/dev/null; then
    mkdir -p "$changed_context_dir/$(dirname "$path")"
    if ! git -C "$repo_root" show "$commit_sha:$path" \
      > "$changed_context_dir/$path" 2>/dev/null; then
      rm -f "$changed_context_dir/$path"
    fi
  fi
done < "$packet_dir/changed-files.txt"

for path in "$@"; do
  case "$path" in
    /*)
      echo "context path must be repository-relative: $path" >&2
      exit 2
      ;;
  esac
  if [ ! -f "$repo_root/$path" ]; then
    echo "context path is not a file: $path" >&2
    exit 2
  fi
  mkdir -p "$review_context_dir/$(dirname "$path")"
  cp "$repo_root/$path" "$review_context_dir/$path"
done

git -C "$repo_root" worktree add --detach --quiet "$repo_context_dir" "$commit_sha"

(
  cd "$repo_context_dir"
  agy --dangerously-skip-permissions --print-timeout 10m --print \
    "Act as a senior code reviewer. The clean repository at the current working directory is the reviewed commit. Review $packet_dir/changes.patch against $packet_dir/issue.md; $packet_dir/changed-files.txt defines the changed-file scope and $packet_dir/review-context/ contains optional highlighted evidence. Own the deep review pass: inspect any repository file needed to trace callers, adapters, schemas, backend/frontend contracts, and acceptance-criteria coverage. You may run non-destructive commands or focused tests when useful. Do not edit files or create commits. Be baseline-aware: a repository gap is actionable only when this commit introduced or worsened it, or when it proves an explicit acceptance criterion in issue.md remains unmet. Do not turn pre-existing adjacent backlog work into blocking findings. Write the review to $review_file. Start with a concise acceptance-criteria coverage audit, then rank actionable findings by severity. For each finding include: confidence (verified, inferred, or needs-context), changed file path, relevant line or hunk, concrete failure mode, cited repository evidence, whether the commit caused/worsened it or which explicit acceptance criterion it misses, and why it conflicts with issue intent or engineering correctness. Any cross-boundary or integration claim must cite the repository file that proves the external interface; if evidence is unavailable, mark it needs-context and do not rank it high severity. Include missing tests only when they protect issue intent. Omit pre-existing adjacent gaps or list them separately as non-blocking context. Do not request speculative features, out-of-scope refactors, or style-only changes. If all acceptance criteria are covered and there are no actionable findings, write exactly: No actionable findings. Verify that $review_file exists and is non-empty, then reply with exactly DONE." \
    > "$packet_dir/agy.stdout.log" 2> "$packet_dir/agy.stderr.log"
) || {
  echo "Antigravity review failed; logs: $packet_dir/agy.stdout.log $packet_dir/agy.stderr.log" >&2
  exit 1
}

if [ ! -s "$review_file" ]; then
  echo "Antigravity did not create a non-empty review: $review_file" >&2
  exit 1
fi

printf '%s\n' "$review_file"
