# Deep Review Synthesis — reviewed by Pi

Date: 2026-07-04

## Review runs produced

- `docs/reviews/agy-backend-paper-generation-review.md`
- `docs/reviews/agy-backend-api-auth-review.md`
- `docs/reviews/agy-backend-bank-ai-review.md`
- `docs/reviews/agy-frontend-generate-editor-review.md`

I reviewed the generated reports, spot-checked the most severe claims against source files, and grouped the findings below by priority. Several reports independently found the same classes of issues; duplicates are consolidated here.

## Highest-priority issues to fix first

### P0/P1 — Cross-tenant question leakage in paper picking

- Source report: `agy-backend-api-auth-review.md`
- Evidence spot-check: `backend/papers/picker.py` `_fetch_candidates` filters by section/qtype/marks/quality/chapter, but not by `school`.
- Risk: a generated paper for one school can include private uploaded/generated questions from another school.
- Fix direction: pass user/school context into candidate fetching and filter with public-or-owned scope, e.g. `Q(school__isnull=True) | Q(school=user.school)`.

### P1 — Paper assembly transaction boundary is too narrow

- Source reports: `agy-backend-paper-generation-review.md`, `agy-backend-api-auth-review.md`
- Evidence spot-check: `backend/papers/builder.py` persists `Paper`/`PaperQuestion` inside `_persist()` transaction, then performs document build/contract guard/answer build afterward.
- Risk: contract/answer failures leave orphan draft `Paper` rows with missing documents.
- Fix direction: wrap the whole `PaperBuilder.assemble()` orchestration in one `transaction.atomic()`.

### P1 — AI-generated MCQ option conversion can crash on `content: null`

- Source report: `agy-backend-bank-ai-review.md`
- Evidence spot-check: `backend/bank/generation_batches.py` `options_from_generated_content` iterates `option.get("content", [])`; if the key exists with `None`, it iterates `None`.
- Risk: accepting a batch can fail and roll back because one MCQ option payload is slightly malformed.
- Fix direction: validate option content as a list in `generated_question_gate.py` and use `option.get("content") or []` defensively.

### P1 — Auth/session hardening gaps

- Source report: `agy-backend-api-auth-review.md`
- Evidence spot-check: `backend/accounts/serializers.py` enforces `min_length=6` but does not call Django `validate_password`.
- Risk: weak passwords accepted; non-expiring DRF tokens have no server-side logout/revocation path.
- Fix direction: call `validate_password`; add logout/token deletion; consider token expiry or short-lived auth.

## High-value P2 fixes

### Backend/API

- Reconcile `PaperQuestion` rows on approval after edits/swaps (`Paper.approve()` docstring says this should happen, report says it currently does not).
- Avoid persistent auth tokens in print/PDF query params; replace with short-lived one-time print tokens.
- Make `PaperEditorDraftView.patch` answer-document reconciliation tolerant of swapped-question mismatch errors, not only missing-answer errors.
- Add per-email/account login throttling or lockout; IP-only throttling is weak against distributed attempts.

### Bank / AI generation

- Add a persistent worker lock/heartbeat for generation batches so a long-running worker is not reclaimed and run concurrently on the same LangGraph thread.
- Catch parser/provider errors in `backend/ai_editor/assistant.py` and return safe fallbacks instead of 500s.
- Wrap multi-query generation-batch expiry in `transaction.atomic()`.
- Preserve source hash / provenance when accepting generated questions into the bank.
- Log/persist validation reason-code summaries when generated candidates are rejected.

### Frontend generate/editor flow

- Validate stale saved `selectedFormatId` against fetched formats in `useCoverageForm`; reset to first active format if missing.
- Wrap `sessionStorage.setItem` in `try/catch` to avoid private-mode/quota crashes.
- Add scroll lock/focus handling/Escape close for the new chapter/source selection overlays.
- Replace dialog approval reconciliation loops with bulk setters on the hook when practical.
- Consider warning before silently dropping selected sources after chapter changes.

## Test gaps to prioritize

1. Cross-tenant picker isolation: school A paper must not include school B private questions.
2. Assembly rollback: mocked contract failure should leave no `Paper` row.
3. Generated MCQ null option content: validation rejects it or accept conversion does not crash.
4. Intent parser failure: malformed model output returns safe fallback, not HTTP 500.
5. Stale paper format in session storage: invalid saved format is reset after formats load.
6. Selection overlay a11y: Escape closes; background scroll is locked; focus stays in dialog.

## Notes on review execution

- Four review files are present and non-empty.
- `agy-backend-bank-ai-review.md` also captured a backend test run with existing failures unrelated to this review request (`backend/bank/tests/test_ingestion_job.py` dry-run/fixture failures under that agent environment). I did not change source code as part of this review pass.
