# Verification emerges from paper approval; picker gates on parse quality

`Question.verified` no longer gates the `QuestionPicker`. The picker now gates on `Question.parse_quality IN ('clean', 'partial')`. `verified=True` is set automatically when `Paper.approve` runs, for every question referenced by the approved paper. There is no manual pre-ingestion verification step.

## Why

The previous design — every ingested row starts `verified=False`, picker excludes them, a human flips them — required an admin review UI that doesn't exist and would have blocked the V1 ingestion goal under a ~12-hour manual-review backlog (1500+ rows × 30 sec each). Splitting the gate into two orthogonal concerns matches the actual workflow:

- **`parse_quality`** answers "is this row structurally usable?" — a deterministic parser self-assessment, set at ingest, requires no human. Three states: `clean` (parsed structure matches detected qtype exactly), `partial` (usable but with caveats, e.g. options truncated), `broken` (excluded from picker). Teachers can also flip a row to `broken` via the editor's "mark unsalvageable" action.
- **`verified`** answers "has a human seen this row in a real paper context and not rejected it?" — emerges naturally from `Paper.approve` flipping the flag for every referenced question. Useful for analytics and future "show only battle-tested questions" filters, but not a hard gate.

Teachers can also *correct* a question in-bank via a new `PATCH /api/bank/questions/{id}` endpoint (separate V/A issues). Correction promotes `parse_quality` to `clean` and `verified` to `True`. This makes rejection rare — most bad rows are fixable, not unsalvageable. The contract's existing slot-override mechanism (§10) covers paper-specific edits that should *not* propagate to the bank.

## Consequences

- Picker pool grows from "verified only" (~0 rows post-ingest) to "parse_quality in (clean, partial), not broken" (~95% of ingested rows). First generated paper draws from a real corpus on day one.
- `verified` field semantics change. Existing tests that flip `verified=True` to make questions pickable must move to using `parse_quality='clean'`.
- `Paper.approve` view gains a side-effect: bulk update of referenced questions' `verified` flag. Idempotent.
- Day-1 paper quality depends entirely on `parse_quality` accuracy — the parser's self-assessment must be honest. Conservative defaults (downgrade to `partial` on any caveat) accepted to keep the bar high.
