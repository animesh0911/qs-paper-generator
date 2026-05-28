# Frontend modules

Per-module overview. Source is authoritative; this is a map. Open the file and read its module header for the full story.

## `src/pages/`

Page-level routes. Each file ends in `.page.tsx`.

| File | Purpose |
|---|---|
| `login.page.tsx` | Auth form. Sets the token via `lib/api`. |
| `dashboard.page.tsx` | Coverage form + paper preview. Orchestrates `useCoverageForm`, `CoverageFormView`, `PaperPreview`, `lib/api.assemblePaper`. |
| `index.ts` | Barrel. |

## `src/hooks/`

| File | Purpose |
|---|---|
| `useAuth.hook.ts` | Token + logout + auth status. |
| `useCoverageForm.hook.ts` | Owns chapter selection, weights, difficulty. Exposes `toAssemblePayload()`. |

## `src/components/`

| Path | Purpose |
|---|---|
| `ui/button/` | shadcn-style button primitive. |
| `ui/card/` | shadcn-style card primitive. |
| `ui/input/` | shadcn-style input primitive. |
| `coverage/coverage-form/` | Renders the Slice 3 form (difficulty, chapter checklist, weight inputs, generate button). |
| `coverage/paper-preview/` | Renders the generated paper card: report panel + sections + questions. |

## `src/lib/`

| File | Purpose |
|---|---|
| `api.ts` | `request()` HTTP helper, `assemblePaper`, `fetchChapters`, `fetchMetadata`, `downloadPaperPdf`, token helpers. |
| `utils.ts` | `cn()` Tailwind class merger. |

## `src/types/`

| File | Purpose |
|---|---|
| `index.ts` | `Chapter`, `Question`, `PaperItem`, `Paper`, `CoverageReport`, `UnfilledSlot`, `AssembleRequest`. Mirrors `papers.picker.CoverageReport` and the assemble API. |

## `src/constants/`

| File | Purpose |
|---|---|
| `index.ts` | Static fallback labels used until `/api/bank/metadata/` resolves. |

## Reading order for a new dev

1. `types/index.ts` (the contracts coming over the wire).
2. `lib/api.ts` (the HTTP adapter).
3. `hooks/useCoverageForm.hook.ts` (the form state owner).
4. `components/coverage/coverage-form/` (the form view).
5. `components/coverage/paper-preview/` (the result view).
6. `pages/dashboard.page.tsx` (orchestration).
