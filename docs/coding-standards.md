# Coding Standards

Keep this stable and short. Put issue workflow, review gates, and one-off
commands in task docs, not here.

## Source Of Truth

- Use domain terms from `CONTEXT.md` exactly.
- Python formatting/linting lives in `backend/pyproject.toml` (`black`, `ruff`, 88 columns, py312).
- Frontend formatting/linting lives in `frontend/package.json`, `frontend/eslint.config.js`, and `frontend/.prettierrc`.

## Shape

- Backend follows Django app boundaries: `models.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`, plus focused modules for deep responsibilities.
- Keep ownership boundaries explicit: `bank` owns Questions and generation candidates; `corpus` owns textbook import, chapter maps, retrieval chunks, embeddings, and grounding seams; `ai_services` owns provider seams.
- Frontend filenames use the existing suffixes: `*.page.tsx`, `*.component.tsx`, `*.hook.ts`, `*.test.ts(x)`, and focused `src/lib/*.ts` helpers.

## Code Style

- Match nearby code before adding patterns.
- Prefer small, typed functions over broad utility bags.
- Do not add abstraction for one use.
- Comments and docstrings explain non-obvious why, invariants, or boundaries; do not narrate obvious code.
- Module docstrings are useful for deep modules and seams. Keep them concise: purpose, boundary, key invariants.

## Tests

- Tests should protect intent and invariants, not only line coverage.
- Use fakes for model, embedding, retrieval, and storage seams; never call live providers in tests.
- Put regression tests next to the module whose behavior they protect.

## Local Checks

- Backend: run the relevant `pytest`, `ruff check .`, `black --check .`, and migration check when models change.
- Frontend: run the relevant `npm run type-check`, `npm run lint`, `npm run test`, or `npm run build`.
- Report any skipped check explicitly.
