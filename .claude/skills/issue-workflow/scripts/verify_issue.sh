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
merge_base="$(git -C "$repo_root" merge-base HEAD "$base_ref")"
export DJANGO_DEBUG="${DJANGO_DEBUG:-1}"

changed_files=()
while IFS= read -r path; do
  changed_files+=("$path")
done < <(
  {
    git -C "$repo_root" diff --name-only "$merge_base" --
    git -C "$repo_root" ls-files --others --exclude-standard
  } | sort -u
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
backend_python_relative_files=()
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
    backend_python_relative_files+=("${path#backend/}")
  fi
done

backend_python="${BACKEND_PYTHON:-}"
if [[ -z "$backend_python" && -x "$repo_root/backend/.venv/bin/python" ]]; then
  backend_python="$repo_root/backend/.venv/bin/python"
elif [[ -z "$backend_python" ]]; then
  backend_python="$(command -v python3 || true)"
fi

backend_compose=()
if command -v docker-compose >/dev/null 2>&1; then
  backend_compose=(docker-compose)
elif docker compose version >/dev/null 2>&1; then
  backend_compose=(docker compose)
fi

backend_python_available() {
  [[ -n "$backend_python" ]] && "$backend_python" -m pytest --version >/dev/null 2>&1
}

run_backend_in_compose() {
  if ((${#backend_compose[@]} == 0)); then
    echo "Backend verification requires local Python with pytest or Docker Compose." >&2
    exit 1
  fi
  "${backend_compose[@]}" run --rm -e RUN_MIGRATIONS=0 web "$@"
}

require_frontend_dependencies() {
  if [[ ! -x "$repo_root/frontend/node_modules/.bin/vitest" ]]; then
    echo "Frontend verification requires frontend dependencies (run npm install)." >&2
    exit 1
  fi
}

if [[ "$backend_changed" == true ]]; then
  if backend_python_available && [[ "$mode" == "focused" ]]; then
    if ! "$backend_python" -c "import testmon" >/dev/null 2>&1; then
      echo "Focused backend verification requires pytest-testmon." >&2
      exit 1
    fi
    (cd "$repo_root/backend" && "$backend_python" -m pytest --testmon)
  elif backend_python_available; then
    (
      cd "$repo_root/backend"
      "$backend_python" -m pytest
    )
    while IFS= read -r path; do
      if [[ -f "$repo_root/$path" ]]; then
        "$backend_python" -m py_compile "$repo_root/$path"
      fi
    done < <(git -C "$repo_root" ls-files "backend/*.py")
    if ((${#backend_python_files[@]} > 0)); then
      "$backend_python" -m ruff check "${backend_python_files[@]}"
      "$backend_python" -m black --check "${backend_python_files[@]}"
    fi
  elif [[ "$mode" == "focused" ]]; then
    echo "Local pytest unavailable; running the full backend suite in Docker Compose."
    run_backend_in_compose pytest
  else
    run_backend_in_compose pytest
    run_backend_in_compose python -m compileall .
    if ((${#backend_python_relative_files[@]} > 0)); then
      run_backend_in_compose ruff check "${backend_python_relative_files[@]}"
      run_backend_in_compose black --check "${backend_python_relative_files[@]}"
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
