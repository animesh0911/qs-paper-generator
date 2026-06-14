# Antigravity Code Review Report: Issue #172 (NCERT Textbook Corpus & Lexical Retrieval)

- **Review Target**: Current worktree (prerequisite issues #167/#168 are untracked; PR #178 is unmerged)
- **Scope**: NCERT textbook document ingestion, chapter mapping, retrieval chunking, and Postgres full-text lexical retrieval.
- **Reviewer**: Antigravity AI Code Reviewer
- **Date**: June 13, 2026

---

## Executive Verdict: CONDITIONAL ACCEPTANCE

The implementation of the NCERT textbook corpus storage, serialization, chapter mapping, and lexical retrieval is structurally clean, modular, and strictly adheres to the **no-LLM / no-embedding-provider** constraint. It provides a solid foundation for the RAG generation pipeline.

However, **three High-Severity correctness and structural bugs** (related to chemical symbol FTS filtering, landmark boundary truncation, and picture-caption separation) and several medium-severity issues must be addressed before this code can be safely integrated into production.

---

## Findings

### High Severity

#### 1. FTS Chemical Symbol Exclusion (Length < 3 Filter)
- **File & Lines**: [retrieval.py:95-100](file:///Users/varad/V/repo/qs-paper-generator/backend/corpus/retrieval.py#L95-L100)
- **Evidence**:
  ```python
  terms = list(
      dict.fromkeys(
          term.lower()
          for term in re.findall(r"[A-Za-z0-9]+", query_text)
          if len(term) >= 3
      )
  )
  ```
- **Impact**: All 1- or 2-character query terms are silently discarded. In a chemistry/science context, this excludes critical chemical symbols, formulas, and concepts (e.g., `pH`, `Fe`, `Cu`, `Zn`, `Na`, `Ca`, `Mg`, `Cl`, `O2`, `H2`, `CO`, `C`, `H`, `O`, `N`, `S`, `P`). Searching for "pH of ethanoic acid" strips `pH`, and searching for a single symbol like "Fe" raises a `ValueError` since no searchable terms remain.
- **Concrete Fix**: Replace the arbitrary length filter with a check against a standard English stopword list, while explicitly preserving alphanumeric chemical formula/symbol patterns (e.g., `^[A-Z][a-z]?\d*$` or `^pH$`).
  ```python
  # Proposed replacement
  CHEMICAL_PATTERN = re.compile(r"^(?:pH|[A-Z][a-z]?\d*)$", re.IGNORECASE)
  terms = []
  for term in re.findall(r"[A-Za-z0-9]+", query_text):
      term_lower = term.lower()
      if len(term) >= 3 or CHEMICAL_PATTERN.match(term):
          terms.append(term_lower)
  terms = list(dict.fromkeys(terms))
  ```

#### 2. Landmark Range Truncation at Picture/Table Elements
- **File & Lines**: [chapter_map.py:160-167](file:///Users/varad/V/repo/qs-paper-generator/backend/corpus/chapter_map.py#L160-L167)
- **Evidence**:
  ```python
  def _before_next_landmark(self, elements: list[TextbookElement], index: int) -> int:
      for candidate_index in range(index + 1, len(elements)):
          candidate = elements[candidate_index]
          if candidate.element_type in {"picture", "table"}:
              return candidate_index - 1
          if candidate.element_type == "section_header":
              return candidate_index - 1
      return len(elements) - 1
  ```
- **Impact**: Any `picture` or `table` element embedded within an Activity, Questions, or Exercises block prematurely terminates the landmark's range. The rest of the landmark's elements (continuing text) are orphaned and left without a landmark node association. Since NCERT activities frequently embed figures and tables, this breaks structural integrity.
- **Concrete Fix**: Do not treat `picture` and `table` elements as boundaries for parent landmarks. Remove them from the termination condition in `_before_next_landmark`.
  ```python
  def _before_next_landmark(self, elements: list[TextbookElement], index: int) -> int:
      for candidate_index in range(index + 1, len(elements)):
          candidate = elements[candidate_index]
          if candidate.element_type == "section_header":
              return candidate_index - 1
      return len(elements) - 1
  ```

#### 3. Picture-Caption Chunk Separation
- **File & Lines**: [retrieval.py:164-169](file:///Users/varad/V/repo/qs-paper-generator/backend/corpus/retrieval.py#L164-L169)
- **Evidence**:
  ```python
  atomic = element.element_type in _ATOMIC_CONTENT_TYPES
  boundary = current and (
      atomic
      or current_type != group_type
      or current_length + text_length > self.max_chars
  )
  ```
  where `_ATOMIC_CONTENT_TYPES = {"caption", "picture", "table"}`.
- **Impact**: Both `picture` and `caption` elements are marked atomic and chunked separately. This disconnects the image asset from its caption text. Lexical queries matching the caption will retrieve the caption chunk (which lacks the image ID), while the picture chunk (which has the image ID) gets no text and will never match search queries.
- **Concrete Fix**: Group adjacent `picture` or `table` elements with their adjacent `caption` elements into a single chunk.

---

## Medium Severity

#### 4. Ignored Picture Captions in Docling Nodes
- **File & Lines**: [retrieval.py:255-266](file:///Users/varad/V/repo/qs-paper-generator/backend/corpus/retrieval.py#L255-L266)
- **Evidence**:
  ```python
  def _element_text(element: TextbookElement) -> str:
      if element.text.strip():
          return element.text.strip()
      if element.element_type != "table":
          return ""
  ```
- **Impact**: For picture elements, the text is treated as empty, ignoring any captions embedded inside the picture node (`element.structured_data.get("captions")`). This prevents these captions from being indexed and queried unless extracted as separate nodes.
- **Concrete Fix**: Update `_element_text` to extract and concatenate caption strings from `structured_data.get("captions", [])` when the element is a picture.
  ```python
  if element.element_type == "picture":
      captions = element.structured_data.get("captions", [])
      return "\n".join(captions).strip()
  ```

#### 5. Missing Landmark Context in Chunk Heading Context
- **File & Lines**: [retrieval.py:206-207](file:///Users/varad/V/repo/qs-paper-generator/backend/corpus/retrieval.py#L206-L207) & [268-273](file:///Users/varad/V/repo/qs-paper-generator/backend/corpus/retrieval.py#L268-L273)
- **Evidence**:
  `_context_nodes` only traverses parent sections and does not include the landmark node (Activity/Exercise) that contains the chunk.
- **Impact**: Chunks inside Activities or Exercises only prepend section titles, lacking the landmark title (e.g., "Activity 4.1"). If the activity text is split, subsequent chunks cannot match queries for "Activity 4.1".
- **Concrete Fix**: Modify `_upsert` and `_context_nodes` to include the active landmark node in the hierarchy chain when building context.

#### 6. No Auto-Update for `search_vector` on Model Save
- **File & Lines**: [models.py:170-190](file:///Users/varad/V/repo/qs-paper-generator/backend/corpus/models.py#L170-L190)
- **Evidence**: No overridden `save()` method or pre-save signal handler updates `search_vector` on individual writes.
- **Impact**: Saving or updating a single `RetrievalChunk` (e.g., via the Django Admin interface) leaves its `search_vector` as NULL, excluding it from search until a full rebuild command is executed.
- **Concrete Fix**: Implement a custom `save` method on `RetrievalChunk` to update `search_vector` dynamically.
  ```python
  def save(self, *args, **kwargs):
      super().save(*args, **kwargs)
      # Trigger an update on search_vector using raw SQL/update expression
      RetrievalChunk.objects.filter(pk=self.pk).update(
          search_vector=SearchVector("text", config="english")
      )
  ```

---

### Low Severity

#### 7. Duplicate Cleaning String Punctuation Fragility
- **File & Lines**: [textbook.py:135-140](file:///Users/varad/V/repo/qs-paper-generator/backend/corpus/textbook.py#L135-L140)
- **Evidence**: Exact half-string split comparison:
  ```python
  if len(words) % 2 == 0 and words[: len(words) // 2] == words[len(words) // 2 :]:
  ```
- **Impact**: Duplicated texts with minor punctuation or capitalization differences (e.g., `"Activity 4.1 Activity 4.1."`) bypass cleaning and remain duplicated.
- **Concrete Fix**: Strip trailing punctuation and normalize whitespace/case before checking duplicate halves.

#### 8. Missing Document Metadata in Chunk Citations
- **File & Lines**: [retrieval.py:225-237](file:///Users/varad/V/repo/qs-paper-generator/backend/corpus/retrieval.py#L225-L237)
- **Evidence**: The citation JSON dictionary only stores `document_id` but not the source filename or hash.
- **Impact**: Citation rendering in the frontend requires database joins, which fail if the document is deleted or re-imported.
- **Concrete Fix**: Backfill `source_file_name` and `source_hash` directly into the chunk's `citation` JSON block.

---

## Accepted-Risk & Baseline Limitations (Not Bugs)

The following limitations are acceptable for the current walking skeleton RAG design:

1. **FTS Lexical OR-Search False Positives**: Because `PostgresTextbookRetriever._query` joins terms with `|` (OR), queries with common science words (e.g., "acid") match irrelevant chunks, producing false positives on unsupported queries (e.g., Nylon-6,6). This is a known baseline lexical search limitation; dense semantic search (Phase 4/5) is required to solve it.
2. **Missing Dense Vector Fields**: `RetrievalChunk` model does not implement `embedding`, `embedding_model`, or `embedding_version`. This is accepted since embedding selection and dense vector implementation are explicitly deferred to Phase 4.
3. **No Support for Unstructured Chapters**: Chapters without numbered headings matching `_NUMBERED_HEADING` will fail to create sections and generate zero retrieval chunks. This is an accepted limitation since NCERT Class 10 Science chapters follow a rigid numbered hierarchy.

---

## Issue Acceptance-Criteria Checklist

| Acceptance Criterion | Status | Notes |
|---|---|---|
| Deterministic Docling normalizer | **PASSED** | Normalizer tests verify stable element IDs, coordinate extraction, and asset mapping. |
| Chapter map Node/Edge derivation | **PASSED** | Deterministic hierarchy edges (`contains`, `next`, `references`) built successfully. |
| Zero-LLM dependency | **PASSED** | Normalization, mapping, chunking, and lexical retrieval use zero LLM APIs. |
| Citation/Provenance traceability | **PASSED** | Retrieval chunks carry exact page number ranges, source elements, and parent headings. |
| Idempotent imports | **PASSED** | Management command is fully idempotent; repeated runs preserve primary keys. |
| Postgres FTS Search index | **PASSED** | GIN index created via migration; GIN-backed query ranking implemented. |

---

## Verification Gaps

1. **Chemical Symbol Retrieval Verification**: The test suite lacks verification cases for 1-2 character queries. Adding test cases for `pH`, `O2`, and `Fe` would have caught the FTS symbol exclusion bug.
2. **Landmark Truncation Verification**: Tests use flat text mock elements and do not mock embedded figures/tables inside Activities, leaving the landmark truncation bug undetected.
3. **Punctuation Deduplication Verification**: No tests verify deduplication when trailing punctuation varies.

---

## Codex Finding Disposition

Validated against the real worktree after Antigravity review:

- **Accepted and fixed:** chemical/science terms shorter than three characters.
- **Accepted and fixed:** activity/question/exercise landmark truncation at embedded
  pictures and tables.
- **Accepted and fixed:** adjacent picture/table and caption chunk separation.
- **Accepted and fixed:** landmark titles missing from bounded chunk context.
- **Accepted and fixed:** source filename/hash missing from citation metadata.
- **Rejected:** extracting picture `structured_data.captions` as text. Those values
  are Docling references, not guaranteed caption strings; adjacent source caption
  elements are now grouped with the picture instead.
- **Rejected:** automatic `search_vector` updates on arbitrary model saves.
  RetrievalChunk is a rebuildable projection owned by RetrievalChunkBuilder, not an
  independently edited source record.
- **Rejected as out of scope:** punctuation-tolerant normalizer deduplication belongs
  to the prerequisite TextbookElement import slice.

Post-fix verification:

- Corpus tests: `18 passed`.
- Real jesc104 lexical baseline: unchanged at `13/22` passes, preserving known
  lexical-only misses and false positives rather than tuning around the evaluation.
