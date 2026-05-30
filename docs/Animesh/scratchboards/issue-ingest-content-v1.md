# Scratchboard: Ingest content/ PDFs into V1-contract-compliant question bank

## Goal

Walk every English-language CBSE Cl.10 Science PYQ PDF in `content/`, parse it,
classify each question's qtype from structure, build contract-shaped `content`,
tag chapter/cognitive/topic/primary-form via LLM, attach diagrams, record source
provenance, and persist rows the picker can immediately use to assemble V1
papers. End state: `POST /api/papers/assemble` produces papers backed by real
PYQ questions whose frontend rendering uses the structured contract paths, not
the `rawText` fallback.

## Success Criteria

- ~1500 `Question` rows ingested from `content/science_2024/`,
  `content/science_2025/`, `content/science_2026/` (excluding `(B)` VI files
  and the textbook).
- ≥80% of rows have `parse_quality='clean'`; <5% `broken`.
- Every row carries the contract source object: `source_type`, `source_name`,
  `source_file_name`, `source_page_number`, `source_original_qnum`.
- Section A's assertion-reason questions land with `qtype='assertion_reason'`
  and structured `content.assertion` + `content.reason` keys.
- Section E case-based questions land with `qtype='case_based'` and structured
  `content.passage` + `content.subparts`.
- Section D internal-OR questions land with `qtype='internal_choice'` and
  structured `content.choices`.
- Every row carries `topic_names: list[str]` (LLM-emitted, 1-3 strings).
- `Chapter.subject_area` populated for all 13 chapters.
- `POST /api/papers/assemble` succeeds against the ingested bank and the
  response satisfies the V1 contract (existing builder tests still pass,
  extended with content-shape assertions).

## Locked Decisions (post-grilling)

1. **Faithful contract quality bar** — no shortcuts to `rawText`-only for
   non-MCQ shapes. Structured `content` is the goal; `rawText` is fallback for
   parser failures only.
2. **Flat source-provenance fields** on `Question` (no `SourcePaper` model).
3. **`Chapter.subject_area`** (Bio/Chem/Phys) populated by data migration from
   the fixed 13-chapter mapping.
4. **Regex-first content parsing**, no LLM content restructuring. Parser
   failures fall through to `rawText`. ADR-0001 / contract §10: source
   `questions[]` content must not be LLM-rewritten.
5. **`Question.content = JSONField`** stores the full contract `content` shape
   per row.
6. **QuestionType enum = contract strings, no mapping** — see ADR-0001.
7. **qtype classified by structure**, not by section position. Section default
   only when structure is plain.
8. **`primary_form` LLM tag** distinguishes `diagram_based` / `table_based`
   from plain SA/LA where the diagram/table is the question's primary task.
9. **`parse_quality` is the picker gate; `verified` emerges from
   `Paper.approve`** — see ADR-0002.
10. **`topic_names = list[str]`** freeform LLM-emitted strings; no Topic model
    for V1.
11. **English-only file selection**: include all `31_*` / `31-*-*` / `1190-*` /
    `1191-*` files; **skip** `(B)` visually-impaired files and the textbook.
    Bilingual stripping already done by `strip_hindi`.
12. **Answers deferred** — set `answer=""` on ingest. Slice 9 handles via
    existing `Ingestor.apply_answers` when marking schemes land.
13. **Diagrams** — inline asset URL in `content` items via `Question.diagram`
    `FileField`; no separate asset registry. Use `image_placeholder` when
    `has_diagram=True` but extractor returned None.

## Phased Implementation

Sequenced so each phase is independently mergeable and the next can build on
it. Phases 1-3 are schema-only; ingestion runs in phase 6.

### Phase 1 — Schema additions (one migration)

- Add to `Question`: `content JSONField(default=dict)`, `parse_quality
  CharField` (clean/partial/broken, default `partial`), `topic_names
  JSONField(default=list)`, `source_type CharField`, `source_name CharField`,
  `source_file_name CharField`, `source_page_number PositiveSmallIntegerField
  null`, `source_original_qnum CharField`.
- Add to `Chapter`: `subject_area CharField` (BIO/CHEM/PHYS), data migration
  populates the 13-chapter mapping.
- No removal of existing fields (`verified`, `text`, `options` stay). `text`
  becomes the `rawText` fallback; `options` still used for MCQ until `content`
  is populated.

### Phase 2 — Enum alignment (one migration + cross-cutting renames)

- Rewrite `QuestionType` enum values to contract strings.
- Data migration: rewrite existing `qtype` column values.
- Update `seed_questions.py`, `papers.template.Slot.qtype`,
  `papers.picker.QuestionPool` keys, `bank.ingestor.SECTION_DEFAULT_QTYPE`.
- Delete `_QTYPE_CONTRACT` from `papers.document.PaperDocumentBuilder`; builder
  reads `q.qtype` / `slot.qtype` directly.
- Update all tests (`papers/tests/test_builder.py`,
  `papers/tests/test_picker.py`, `bank/tests/test_ingestor.py`).

### Phase 3 — Picker gate swap (ADR-0002)

- `QuestionPicker` pool query: `parse_quality__in=['clean','partial']` instead
  of `verified=True`.
- `Paper.approve` view: bulk-update referenced questions' `verified=True`.
- Update tests that set `verified=True` to make questions pickable → switch
  to `parse_quality='clean'`. Add new test: approving a paper flips
  `verified=True` on its questions.

### Phase 4 — Parser extensions (regex)

- `bank.ingestor`: new pure helpers for shape detection:
  - `_parse_assertion_reason(text) → dict | None`
  - `_parse_case_based(text) → dict | None` (passage + subparts)
  - `_parse_internal_choice(block_pair) → dict | None` (OR-split)
  - `_parse_long_answer_subparts(text) → list[dict] | None`
- `_classify_qtype(raw_question, section) → str` — returns the contract enum
  string based on detected structure or section default.
- `_compute_parse_quality(raw_question, classified_qtype) → str` — `clean` if
  structure matches qtype, `partial` if caveats, `broken` if confidence too
  low.
- `segment_questions` now emits `{section, qtype, marks, text, content,
  parse_quality}` instead of `{section, qtype, marks, text, options}`.
- `options` retained on output for backwards compatibility (MCQ).

### Phase 5 — LLM tagger output extension

- `LLMTagger.tag` prompt + parser now expects per-question:
  `{index, chapter_slug, cognitive_level, topic_names: list[str], primary_form:
  "none"|"diagram_based"|"table_based"}`.
- Ingestor sets `qtype = primary_form` when `primary_form != "none"` and
  current qtype is `short_answer`/`long_answer`.
- Ingestor populates `topic_names` from tagger output.

### Phase 6 — Source provenance + ingest mgmt command

- New pure helper `_parse_source_filename(path) → dict` returning
  `{source_type, source_name, source_file_name}`. CBSE filename grammar:
  `[<sample_code>_]<31>[-_]<set>[-_]<variant>[_Science].pdf`.
- `Ingestor.ingest(pdf_bytes, source_meta)` — accepts source metadata; populates
  the 5 source columns per row; also infers `source_page_number` from the
  page-tracking inside `PdfplumberParser.parse_pages`.
- New `python manage.py ingest_content [--dir content/] [--dry-run]`. Walks
  the tree, skips `(B)` files and `Class 10 Science Textbook PDF.pdf`, runs
  the Ingestor per file, prints per-file counts and a final summary.

### Phase 7 — PaperDocumentBuilder consumption

- `_build_question`: emit `rawText = q.text`; `content = q.content or
  {"stem": [{"type":"paragraph","text": q.text}]}` (fallback to current
  behavior when `content` is empty). Emit `metadata.subjectArea =
  q.chapter.subject_area`, `metadata.topicNames = q.topic_names`,
  `metadata.requiresDiagram = q.has_diagram`. Emit `source` from the 5 flat
  fields directly.
- Section subtitles: derive from majority subject_area of the section's
  questions, not hardcoded `"Class X"`.
- Diagram → `content` asset item: when `q.diagram` is set, append `{type:
  "image", url: q.diagram.url}` to `content.assets`; when `has_diagram=True`
  but no file, append `{type: "image_placeholder", text: "..."}`.

### Phase 8 — Run the ingestion, verify

- `docker compose run --rm web python manage.py ingest_content content/`
- Verify counts. Spot-check 10 random rows across qtypes for content shape
  fidelity. Hit `POST /api/papers/assemble` and inspect the returned
  document for contract compliance.

## Test Strategy

- Unit tests per pure helper (no LLM, no PDF, no DB) — Rule 9: tests encode
  *why* the shape matters, not just *what* the regex matches.
- Ingestor integration tests use stub adapters (existing pattern) with hand-
  crafted PDF bytes covering each shape.
- Builder tests extended to assert: contract qtype values present;
  `metadata.subjectArea` populated; `source.fileName` populated.
- One end-to-end smoke test that runs a real PDF from `content/` through the
  pipeline against stub LLM, asserts ≥1 row per qtype is produced.

## Out of Scope (V1)

- Marking-scheme ingestion (`apply_answers`) — Slice 9.
- Topic canonicalisation / `Topic` model — deferred.
- `(B)` visually-impaired file ingestion.
- Textbook parsing.
- Async ingest jobs (Celery) — runs synchronously in the mgmt command for V1.
- Per-question manual review UI in admin — superseded by editor "Fix in bank"
  flow (separate V issue).

## Open Risks

- **LLM cost**: ~1500 questions × tagger prompt ≈ $5-15 single run.
  Acceptable. Re-runs only happen on re-parse.
- **CBSE format drift across years**: 2024/2025/2026 mostly identical; if
  2026 has new shapes the parser fails on, those rows go `broken` — visible,
  not catastrophic.
- **Diagram extractor heuristic accuracy**: known imperfect; acceptable
  because `has_diagram` text flag is a secondary signal and contract permits
  `image_placeholder`.
- **`Section` enum stays `A`..`E`**: if CBSE introduces a Section F we'd
  need a migration. No signal that's imminent.
