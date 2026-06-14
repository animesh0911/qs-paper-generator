#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <focused|full>" >&2
  exit 2
}

mode="${1:-}"
[[ "$mode" == "focused" || "$mode" == "full" ]] || usage

repo_root="$(git rev-parse --show-toplevel)"
base_ref="${BASE_REF:-origin/main}"
merge_base="$(git -C "$repo_root" merge-base HEAD "$base_ref" 2>/dev/null || true)"
if [[ -z "$merge_base" ]]; then
  echo "Could not find a merge base between HEAD and $base_ref." >&2
  echo "Ensure the base ref exists locally and has been fetched." >&2
  exit 1
fi
export DJANGO_DEBUG="${DJANGO_DEBUG:-1}"

changed_files=()
while IFS= read -r -d '' path; do
  changed_files+=("$path")
done < <(
  git -C "$repo_root" diff --name-only -z "$merge_base" --
  git -C "$repo_root" ls-files --others --exclude-standard -z
)

if ((${#changed_files[@]} == 0)); then
  echo "No changes relative to $base_ref."
  exit 0
fi

printf 'Changed files relative to %s:\n' "$base_ref"
printf '  %s\n' "${changed_files[@]}"

backend_changed=false
frontend_changed=false
backend_python_files=()
for path in "${changed_files[@]}"; do
  case "$path" in
    backend/* | contracts/* | docker-compose.yml)
      backend_changed=true
      ;;
    frontend/* | package.json | package-lock.json)
      frontend_changed=true
      ;;
  esac
  if [[ "$path" == backend/*.py && -f "$repo_root/$path" ]]; then
    backend_python_files+=("$repo_root/$path")
  fi
done

backend_python="${BACKEND_PYTHON:-}"
if [[ -z "$backend_python" ]]; then
  if [[ -x "$repo_root/backend/.venv/bin/python" ]]; then
    backend_python="$repo_root/backend/.venv/bin/python"
  elif [[ -x "$repo_root/backend/.venv/Scripts/python.exe" ]]; then
    backend_python="$repo_root/backend/.venv/Scripts/python.exe"
  elif [[ -x "$repo_root/backend/.venv/Scripts/python" ]]; then
    backend_python="$repo_root/backend/.venv/Scripts/python"
  else
    backend_python="$(command -v python3 || command -v python || true)"
  fi
fi

require_backend_python() {
  if [[ -z "$backend_python" ]] || ! "$backend_python" -m pytest --version >/dev/null 2>&1; then
    echo "Backend verification requires Python with pytest installed." >&2
    exit 1
  fi
}

require_frontend_dependencies() {
  if [[ ! -d "$repo_root/frontend/node_modules/vitest" ]]; then
    echo "Frontend verification requires frontend dependencies (run npm install)." >&2
    exit 1
  fi
}

if [[ "$backend_changed" == true ]]; then
  require_backend_python
  if [[ "$mode" == "focused" ]]; then
    if ! "$backend_python" -c "import testmon" >/dev/null 2>&1; then
      echo "Focused backend verification requires pytest-testmon." >&2
      exit 1
    fi
    (cd "$repo_root/backend" && "$backend_python" -m pytest --testmon)
  else
    (
      cd "$repo_root/backend"
      "$backend_python" -m pytest
    )
    while IFS= read -r -d '' path; do
      if [[ -f "$repo_root/$path" ]]; then
        "$backend_python" -m py_compile "$repo_root/$path"
      fi
    done < <(git -C "$repo_root" ls-files -z "backend/*.py")
    if ((${#backend_python_files[@]} > 0)); then
      "$backend_python" -m ruff check "${backend_python_files[@]}"
      "$backend_python" -m black --check "${backend_python_files[@]}"
    fi
  fi
fi

if [[ "$frontend_changed" == true ]]; then
  require_frontend_dependencies
  if [[ "$mode" == "focused" ]]; then
    (cd "$repo_root/frontend" && npm test -- --changed "$merge_base")
  else
    (
      cd "$repo_root/frontend"
      npm test
      npm run type-check
      npm run build
      npm run lint
    )
  fi
fi

if [[ "$backend_changed" == false && "$frontend_changed" == false ]]; then
  echo "No backend or frontend checks selected for these changes."
fi
