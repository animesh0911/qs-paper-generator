# Coding Standards

Conventions enforced across this codebase. Lint+format tools catch the mechanical pieces; the docstring conventions below are reviewed in PRs.

## Tools

| Tool | Purpose | Applies to |
|---|---|---|
| Black | Code formatting | Python |
| Ruff | Linting + import order | Python |
| Prettier | Code formatting | TypeScript, JSX, JSON, CSS |
| ESLint | Linting + React rules | TypeScript, JSX |
| Husky + lint-staged | Pre-commit gate | Staged files |

Configuration lives in `backend/pyproject.toml` (Black, Ruff) and `frontend/package.json` + `eslint.config.js`.

## Running locally

```bash
# Backend (inside the web container)
docker exec qs_paper_generator-web-1 ruff check .
docker exec qs_paper_generator-web-1 black --check .

# Frontend
docker exec qs_paper_generator-frontend-1 npx tsc --noEmit
docker exec qs_paper_generator-frontend-1 npx eslint src
```

Pre-commit runs Prettier + ESLint over staged `src/**/*.{ts,tsx}` automatically.

## File naming

Frontend follows saas-labs conventions ported in commit `64551f5`:

- Pages: `<name>.page.tsx` under `src/pages/`
- Components: `<name>.component.tsx` under `src/components/<name>/`, with `index.ts` barrel
- Hooks: `use<Name>.hook.ts` under `src/hooks/`
- Libraries: `api.ts`, `utils.ts` under `src/lib/`

Backend follows standard Django layout: `models.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py` per app.

## Docstring convention

Every source file gets a **module-level docstring** explaining:

1. **What the module is** — one sentence.
2. **Where it sits** — which seam, what it depends on, who calls it.
3. **Notable patterns** — invariants, ordering constraints, error policy.

Methods get docstrings only when behaviour is **not** obvious from the signature + name. A `def total_marks(self) -> int` needs none. A `def _allocate(n, ratios) -> dict[str, int]` does, because the largest-remainder math is the whole point.

This matches `CLAUDE.md` Rule "default to no comments unless WHY is non-obvious."

### Python module docstring shape

```python
"""One-sentence module purpose.

Longer prose: what problem this module solves, what seam it occupies,
where the implementation contract lives.

Patterns / invariants:
- Bullet of any non-obvious rule a caller must respect.
- Another bullet.

Where it fits:
- Called by: <module>
- Calls into: <module>
- Persisted via: <model>
"""
```

### TS/TSX module header shape

```ts
/**
 * One-sentence module purpose.
 *
 * Longer prose: what this module renders / owns / coordinates.
 *
 * Patterns:
 * - Bullet of any non-obvious rule.
 *
 * Where it fits:
 * - Used by: <module>
 * - Uses: <module>
 *
 * @module <ModuleName>
 */
```

## Vocabulary

Use the terms from [`CONTEXT.md`](../CONTEXT.md) exactly — `Question`, `Chapter`, `Preset`, `PaperTemplate`, `Slot`, `OR-group`, `QuestionPicker`, `CoverageReport`, `PaperDocumentV1`, `Ingestor`, `Parser`, `Tagger`, `LLMClient`, etc. Don't drift into `service`, `handler`, `component` when a domain term fits.

For architecture talk, use the vocabulary in `.claude/skills/improve-codebase-architecture/LANGUAGE.md`: **module**, **interface**, **seam**, **adapter**, **depth**, **locality**.

## Comments inside functions

Default to none. Write one only when the **why** is non-obvious — a hidden constraint, a workaround for a specific bug, behaviour that would surprise a reader. Never narrate the **what**; identifiers do that.

## Tests

Tests must encode **why** the behaviour matters, not just **what** it does. A test that can't fail when business logic changes is wrong. See `papers/tests/test_selection.py` for examples.
