# Issue 173: pgvector and EmbeddingClient Plan

## Goal

Prepare the corpus-owned retrieval path for dense search without selecting or
calling a live embedding provider.

The issue is complete when Postgres 16 runs with pgvector, RetrievalChunks can
store profile-versioned vectors, fixed vectors can drive filtered nearest-
neighbor queries through an HNSW index, and embedding population is resumable
and idempotent. Existing lexical retrieval must continue to work when no
embedding exists.

## Baseline and Scope

- Implement from the completed issue-172 head, commit `6bd502b`, or its
  integrated equivalent after PR #180 lands.
- Keep all embedding persistence, population, querying, seams, and test
  adapters inside `backend/corpus/`.
- Do not select a production embedding model, populate the real `jesc104`
  corpus, evaluate retrieval quality, or call a provider. Those belong to
  issue #174.
- Do not combine lexical and dense rankings. Hybrid retrieval belongs to issue
  #175.
- Do not add a teacher-facing API or frontend.

## Public Interfaces

Add `EmbeddingClient` to `CONTEXT.md` before using it in code.

```python
@dataclass(frozen=True)
class EmbeddingProfile:
    model: str
    version: str
    dimensions: int


class EmbeddingClient(Protocol):
    profile: EmbeddingProfile

    def embed(
        self, texts: tuple[str, ...]
    ) -> tuple[tuple[float, ...], ...]: ...
```

The profile is part of the seam because vector dimensions and stored
model/version metadata must describe the same output. Corpus feature code
depends only on this protocol; provider SDK imports remain outside `corpus`.

```python
@dataclass(frozen=True)
class EmbeddingPopulationRequest:
    document: TextbookDocument
    client: EmbeddingClient
    batch_size: int = 32


@dataclass(frozen=True)
class EmbeddingPopulationResult:
    document: TextbookDocument
    populated_count: int
    skipped_count: int


class RetrievalChunkEmbeddingPopulator:
    def populate(
        self, request: EmbeddingPopulationRequest
    ) -> EmbeddingPopulationResult: ...
```

`populate` processes stable chunk order in independently committed batches.
It skips a chunk only when the embedding is present and both stored profile
fields match the requested client profile. It validates result count,
dimensions, and finite numeric values before writing a batch. A failed batch
leaves earlier batches committed so a retry skips completed work.

```python
class PostgresVectorTextbookRetriever:
    def __init__(self, client: EmbeddingClient): ...

    def retrieve(
        self, request: TextbookRetrievalRequest
    ) -> GroundingContext: ...
```

The dense adapter embeds the query through `EmbeddingClient`, applies the
existing Chapter, optional ChapterMapNode, content-type, and limit filters,
restricts rows to the client's model/version, orders by cosine distance, and
uses `stable_chunk_id` as the deterministic tie-breaker. It does not silently
mix in lexical results. The existing `PostgresTextbookRetriever` remains the
lexical-only path and must work with every embedding field null.

## Persistence and Dimension Decision

Extend `RetrievalChunk` with:

```text
embedding          nullable unbounded pgvector vector
embedding_model    blank string when embedding is null
embedding_version  blank string when embedding is null
```

Add a check constraint requiring all three fields to be populated together or
all three to be absent.

Do not use `vector(n)` for the column in this issue. Production dimensions are
selected in issue #174. pgvector permits an unbounded `vector` column, but an
approximate index must target rows of one known dimension.

To prove indexed integration without locking production dimensions, migration
`0004` should:

1. enable the `vector` extension with `VectorExtension`;
2. add the three RetrievalChunk fields and consistency constraint; and
3. create one partial expression HNSW cosine index for the fixed test profile,
   casting `embedding` to `vector(3)` only where model/version identify that
   profile.

The index name and fixed profile constants must be explicit, for example:

```text
model: fixed-vector-test
version: v1
dimensions: 3
index: retrieval_chunk_fixed_test_v1_hnsw
```

Issue #174 must add the selected production profile's dimension-specific
index. The unbounded column can store the selected profile without a column
rewrite, and the test index does not claim to be the production index.

When `RetrievalChunkBuilder` rebuilds an existing stable chunk:

- preserve its embedding when the persisted chunk text is unchanged;
- clear embedding, model, and version when the chunk text changes; and
- leave new chunks unembedded.

This prevents stale vectors from surviving a chunk-text change.

## Infrastructure Changes

- Change the Compose database image from `postgres:16` to the documented,
  version-pinned `pgvector/pgvector:0.8.2-pg16-bookworm` image.
- Keep the current environment, healthcheck, named `pgdata` volume, service
  name, and dependent-service workflow unchanged.
- Add `pgvector>=0.4.2,<0.5` to `backend/requirements.txt`.
- Update the database image references in `docs/Animesh/commands.md` and
  `docs/architecture-diagrams.md`.
- Document that moving between Postgres 16 images reuses the existing volume,
  while normal backup practice still applies before infrastructure changes.

## Fixed Test Adapter

Add a deterministic adapter under `backend/corpus/tests/` that:

- exposes the fixed three-dimensional profile;
- maps exact input strings to fixed vectors;
- records requested batches so skip/resume behavior is observable;
- can fail on a configured call for resumability tests; and
- raises on unknown text instead of inventing a vector.

The adapter performs no network or model call.

## TDD Tracer Slices

### Slice 1: pgvector is migration-owned

RED: an integration test asserts the `vector` extension exists after
migrations and a RetrievalChunk round-trips a fixed vector.

GREEN: switch the Compose image, add the Python dependency, enable the
extension, and add nullable vector/profile fields plus the consistency
constraint.

Focused check:

```bash
cd backend
pytest corpus/tests/test_embeddings.py -k "extension or persistence"
python manage.py makemigrations --check
```

### Slice 2: population is profile-aware and idempotent

RED: populate two chunks through the fixed adapter, rerun, and assert the
second run makes no adapter call and reports both chunks skipped.

GREEN: add `EmbeddingProfile`, `EmbeddingClient`,
`EmbeddingPopulationRequest`, `EmbeddingPopulationResult`, and
`RetrievalChunkEmbeddingPopulator`.

Focused check:

```bash
cd backend
pytest corpus/tests/test_embeddings.py -k "populate or idempotent"
```

### Slice 3: population resumes after failure

RED: fail the adapter on the second batch, assert the first batch remains
stored, retry, and assert only unfinished chunks are requested.

GREEN: validate complete adapter output before each batch write and commit each
successful batch independently.

Also cover re-embedding when model/version changes and rejection of wrong
vector counts, wrong dimensions, non-finite values, and invalid batch sizes.

### Slice 4: rebuilds cannot retain stale embeddings

RED: embed a chunk, rebuild unchanged and preserve it; then change its built
text, rebuild, and assert all embedding fields are cleared.

GREEN: make `RetrievalChunkBuilder` compare old and new text before preserving
embedding metadata.

Focused check:

```bash
cd backend
pytest corpus/tests/test_retrieval.py corpus/tests/test_embeddings.py
```

### Slice 5: dense retrieval filters and orders fixed vectors

RED: fixed vectors prove cosine nearest-neighbor ordering, stable tie-breaking,
Chapter filtering, ChapterMapNode filtering, content-type filtering, and
model/version isolation.

GREEN: add `PostgresVectorTextbookRetriever` using a cast whose dimensions come
from the injected profile. Keep the existing request and GroundingContext
interfaces.

Dense retrieval with no matching embeddings returns an empty context. The same
fixture queried through `PostgresTextbookRetriever` must still return lexical
results, proving the lexical-only fallback remains operational.

### Slice 6: the fixed-profile query uses HNSW

RED: obtain the dense queryset plan with sequential scans disabled inside the
test transaction and assert it names
`retrieval_chunk_fixed_test_v1_hnsw`.

GREEN: add the partial expression HNSW cosine index in the migration and make
the query expression and profile predicate match it exactly.

This test must use `ORDER BY` cosine distance plus `LIMIT`; pgvector cannot use
the approximate index for a differently shaped order expression.

## Verification Gate

Focused:

```bash
cd backend
pytest corpus/tests/test_embeddings.py corpus/tests/test_retrieval.py
python manage.py makemigrations --check
```

Changed-area:

```bash
cd backend
pytest
ruff check .
black --check .
python -m compileall .
python manage.py makemigrations --check
```

Infrastructure:

```bash
docker compose up -d --build db web
docker compose exec web python manage.py migrate --noinput
docker compose exec db psql -U qpg -d qpg -c \
  "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
docker compose exec db psql -U qpg -d qpg -c \
  "\d+ corpus_retrievalchunk"
```

No command in this issue may instantiate a live provider adapter or call a
paid embedding API.

## Planned Files

- `CONTEXT.md`
- `docker-compose.yml`
- `backend/requirements.txt`
- `backend/corpus/models.py`
- `backend/corpus/embeddings.py`
- `backend/corpus/retrieval.py`
- `backend/corpus/migrations/0004_*.py`
- `backend/corpus/tests/fakes.py`
- `backend/corpus/tests/test_embeddings.py`
- `backend/corpus/tests/test_retrieval.py`
- `docs/Animesh/commands.md`
- `docs/architecture-diagrams.md`

## Success Criteria

- The extension, fields, constraint, and fixed-profile HNSW index are created
  only by committed Django migrations.
- Fixed vectors persist and produce deterministic filtered nearest-neighbor
  ordering through the HNSW index.
- Population skips completed model/version matches and resumes without
  re-embedding successful batches.
- Rebuilds preserve valid embeddings and clear stale ones.
- Lexical retrieval still works with no embeddings.
- `corpus` imports no provider SDK and verification makes zero live or paid
  model calls.
- Production dimensions remain explicitly deferred to issue #174.

## Ralph Checkpoints After Implementation

1. Run focused checks after each RED/GREEN slice.
2. Run the full changed-area gate.
3. Run the `code-review` skill on the uncommitted issue diff and fix accepted
   findings.
4. Re-read issue #173 for scope misses and rerun the required checks.
5. Commit only issue-173 files.
6. After explicit Rule 13 consent, run the mandatory review packet:

   ```bash
   .claude/skills/agy-code-review/scripts/run_review.sh \
     <issue-173-commit> 173 \
     CONTEXT.md backend/corpus/retrieval.py
   ```

   The wrapper must confirm `Gemini 3.5 Flash (High)` before the paid review
   runs.
7. Fix accepted Antigravity findings in a separate commit, verify, push, and
   only then close the issue.

## References

- pgvector installation and Docker tags:
  <https://github.com/pgvector/pgvector>
- pgvector variable-dimension columns and partial expression indexes:
  <https://github.com/pgvector/pgvector#frequently-asked-questions>
- pgvector-python Django fields, migrations, distance expressions, and HNSW:
  <https://github.com/pgvector/pgvector-python#django>
