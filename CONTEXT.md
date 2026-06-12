# CONTEXT — domain glossary

Single source of truth for the vocabulary used in this codebase. Module names, class names, and documentation should use these terms exactly. New names must be added here before they are used in code.

This file is read by `/improve-codebase-architecture` and other architecture-aware agents.

## Domain terms

**Question**
A single bank item. Has section (A–E), **QuestionType** (contract-string enum), marks, chapter, cognitive level, **rawText**, structured **content** (contract-shape JSON), **topic_names** (freeform LLM-emitted strings), **source provenance** (`source_type`, `source_name`, `source_file_name`, `source_page_number`, `source_original_qnum`), **parse_quality**, **review_flags**, **verified**, optional answer, optional diagram. Lives in `bank.models.Question`.

**QuestionType**
Enum on `Question.qtype`. Values are **identical to PaperDocumentV1 `questionType` strings** — no mapping layer. Members: `mcq`, `assertion_reason`, `very_short_answer`, `short_answer`, `long_answer`, `case_based`, `internal_choice`, `diagram_based`, `table_based`, `custom`. Classified at ingest from the question's structure (e.g. `assertion`+`reason` keys → `assertion_reason`), with section default as fallback. See ADR-0001.

**SubjectArea**
The three CBSE Science streams: `Biology`, `Chemistry`, `Physics`. Lives on `Chapter.subject_area` (Bio = chapters 5, 6, 7, 8, 13; Chem = 1–4; Phys = 9–12). Derived onto questions via `Question.chapter.subject_area`; surfaces in `PaperDocumentV1` `metadata.subjectArea` and section subtitles.

**Chapter**
A canonical CBSE Class 10 Science chapter, seeded from the NCERT taxonomy. Identified by slug. Carries **subject_area**. Lives in `bank.models.Chapter`. Hardcoded taxonomy in `migrations/0003_seed_chapters.py` — LLM tagger picks from this closed list, never invents new chapters.

**Topic**
A subdivision *within* a chapter (e.g. "Monohybrid Cross" inside `heredity`). V1 stores topics as **freeform LLM-emitted strings** on `Question.topic_names = list[str]`. No `Topic` model. Canonicalisation deferred until V2 (cluster strings or seed from textbook TOC then). Emitted by the **Tagger**, persisted by the Ingestor, surfaced in `PaperDocumentV1` `metadata.topicNames`.

**primary_form**
Field on `Question` (`bank.models.PrimaryForm`): the dominant non-text form a question depends on — `none`, `diagram_based`, or `table_based`. Emitted by the **Extractor**, *orthogonal* to **QuestionType** (a `short_answer` can be `diagram_based`). `diagram_based` also reinforces `Question.has_diagram` at ingest. Stored for future form-aware picking/rendering; not yet a picker gate.

**parse_quality**
Field on `Question` — a plain structural self-assessment of completeness. Values: `clean` (structure matches the qtype exactly), `partial` (usable but with caveats, e.g. a case-based passage without enough subparts), `broken` (structure too poor to use, or teacher explicitly marked unsalvageable). Computed from how well the extracted structure matches the qtype by `question_shape.compute_parse_quality`, which the coordinator and `load_questions` both call; there is no verification pass against source text (ADR-0004). The per-qtype region rules it reads live in the **QuestionShape** spec. **The picker gate**: only `clean` + `partial` are eligible for picking. Replaces the previous `verified=True` gate. See ADR-0002. The **ingest guardrails** (`bank.guardrails`) downgrade it when they flag a structural defect.

**review_flags**
JSON list of reason-code strings on `Question` set by the **ingest guardrails** (`bank.guardrails.apply_guardrails`) — e.g. `chapter_unresolved`, `marks_section_mismatch`, `mcq_too_few_options`, `possible_split`, `empty_stem`, `blueprint_count_drift`. Empty = the deterministic checks found nothing; non-empty = the row is in the **review queue** (admin "needs review" filter) instead of being silently accepted. The complement to **parse_quality**: parse_quality stays the structural picker gate, `review_flags` is the queryable "why this needs a human" signal. A flag may also drag parse_quality down (a lost stem → `broken`; a tagging defect → `partial`). Introduced for the #126/#127 extraction-hardening (audit #108).

**verified**
Field on `Question`. Semantics: **"a human has seen this question in an approved paper and did not reject it."** Set to `True` automatically when `Paper.approve` runs — every referenced question is flipped. **Not** a picker gate. Used by analytics and future "show only battle-tested questions" filters. See ADR-0002.

**source provenance**
Five flat fields on `Question` recording where a row came from: `source_type` (one of **SourceType** — `previous_year_paper`, `sample_paper`, `question_bank`), `source_name` (e.g. `"31-2-1 Science 2026"`), `source_file_name` (e.g. `"31-2-1.pdf"`), `source_page_number`, `source_original_qnum`. The batch-wide three (`source_type`, `source_name`, `source_file_name`) are set at ingest by the `_Provenance.from_filename` helper — it takes the uploaded filename (deriving `source_name` from the filename stem) plus an optional `source_type` request field (default `previous_year_paper`). `source_page_number` and `source_original_qnum` are a **V2 deferral** — the Extractor does not yet track page offsets or per-question original numbering, so they stay blank. Mapped to the `PaperDocumentV1` `source` object by `PaperDocumentBuilder._build_source`, which emits the optional `fileName`/`pageNumber`/`originalQuestionNumber` only when set.

**Ingestor**
Coordinator for the ingestion pipeline. Sends the source PDF bytes straight to the **Extractor** (no text extraction), which returns structured, tagged question dicts (`section`, `qtype`, `marks`, `text`, `options`, `content` matching the contract shape per qtype, plus `chapter_slug`, `cognitive_level`, `topic_names`, `primary_form`, `figures`). The coordinator sets `parse_quality` from structure (`question_shape.compute_parse_quality`), de-duplicates by `source_hash` (within and across PDFs), hands the figure boxes to the **DiagramCropper**, **records source provenance** from the source filename, and persists `Question` rows with `verified=False` (scoped to an optional `school` for the live HTTP path). Two injectable seams: **Extractor** (default `GeminiExtractor`) and **DiagramCropper** (default `PyMuPdfCropper`). Lives in `bank.ingestor.Ingestor`. Symmetric to `PaperBuilder`.

**Two ingestion front doors** (both intentional — neither is redundant):
- **Committed-JSON path (CLI)** — `extract_paper` → reviewed `content/parsed/*.json` (git) → `load_questions`. For *developers* seeding the bank from a curated corpus and for the extraction benchmark; needs the durable, reproducible JSON artifact. `school` is `None` (shared corpus).
- **Live HTTP path** — `POST /api/bank/ingest/` → **IngestionJob** (Postgres) → `drain_ingestion_jobs` cron → Gemini → DB. For *teachers* uploading their own PDFs at runtime with no shell/repo/git; rows are scoped to the teacher's `school`.

**IngestionJob**
A queued teacher PDF upload, drained out-of-request — the seam that keeps the live HTTP ingest path off the request thread **without Celery / Redis / a worker daemon** (MVP infra constraint). `bank.views.ingest` (`IsTeacher`: authenticated + has a `school`) persists the uploaded PDF and creates a `pending` row, returning **202** + the job id; no Gemini call in the request. `drain_ingestion_jobs` (a management command run on the platform's **cron**) picks up `pending` *and* `running` rows and drives each through the extraction `StateGraph` (`workflows.extraction`) — one **checkpointer** step per PDF page, under the job's `thread_id` (ADR-0006). The graph's persist step is the same **Ingestor** tail the CLI path uses (`ingest_extracted`), scoping created `Question` rows to the job's `school`; the drain then records `done` (with `created_count`/`skipped_count`) or `failed` (with `error`). A `running` row whose process died is resumed from its last per-page checkpoint on the next pass — never re-billed from page 1; a `failed` row is terminal until manually flipped back to `pending`, which also resumes rather than restarts. `GET /api/bank/ingest/{id}/` lets the frontend poll status. `source_type` is caller-supplied (one of **SourceType**), not hardcoded. V1 has **no upfront review** — rows land `verified=False` and rely on the downstream `parse_quality`/`verified` gate (ADR-0002). Lives in `bank.models.IngestionJob`.

**Extractor**
The single adapter seam of the Ingestor. `Extractor.extract(pdf_bytes) → list[dict]` — one native-PDF call to a multimodal LLM does English-only filtering (discard the Hindi column, no translation), segmentation, qtype classification, `content` region structuring, and chapter/cognitive-level/`topic_names`/`primary_form` tagging in one pass. Default `GeminiExtractor` section-chunks the call (one request per Section A–E to keep attention dense) and merges the results in document order. Every taxonomy field is a **closed enum** in the response schema — including `chapter_slug`, which `build_question_schema` closes to the live `Chapter` slugs per call (Layer 1 of the #126/#127 hardening; previously the one free-form field and the #108 mis-tagging root cause). Diagrams are emitted as `image_placeholder` content items plus a `figures` box list the **DiagramCropper** turns into real crops. Tests inject a stub Extractor. See ADR-0004.

**DiagramCropper**
The Ingestor's second adapter seam, symmetric to the **Extractor**. `crop(pdf_bytes, rows, fingerprints) → list[str | None]` opens the source PDF once, crops each Extractor-localised figure box, saves PNGs to `default_storage`, and rewrites the question's `image_placeholder` into an `image` item referencing the asset by storage name (contract §9, no inline URL) via `content.place_item`. Returns each row's primary (first) cropped asset for the `Question.diagram` FileField. Default `PyMuPdfCropper` uses PyMuPDF (`fitz`); a bad box fails soft to the placeholder (ADR-0004). Tests inject a stub. Lives in `bank.diagram_cropper`. `load_questions` skips it — committed JSON already carries its image items.

**Content**
The structured, region-keyed question body (PaperDocumentV1 §9): **ITEM_REGIONS** (`stem`/`assertion`/`reason`/`passage`) hold `ContentItem[]` directly; **LABELLED_REGIONS** (`options`/`subparts`) hold `{label, content:[…]}` entries; `choices` holds choice-groups whose options carry their own `content[]`. A `ContentItem` is a dict with a `type` (`paragraph`/`equation`/`image`/`image_placeholder`/`table`). `bank.content` owns the region names and the **single tree-walk** over the shape — `walk`, `has_item`, `find_items`, `flatten_text`, `place_item` — so the Ingestor (`has_diagram`), DiagramCropper (figure placement), `PaperDocumentBuilder` (`requiresTable`), and the PDF renderer (text flatten) no longer each re-walk the tree by hand.

**QuestionShape**
The per-**QuestionType** structure spec in `bank.question_shape`: `QUESTION_SHAPES[qtype]` declares the `content_regions` a qtype populates and the `fallback_regions` `PaperDocumentBuilder` synthesises for an empty-`content` row. The single source the `compute_parse_quality` self-assessment and the document fallback both read, and which a test asserts the Gemini response schema covers — closing the per-qtype shape drift the way ADR-0001 closed the qtype-value drift.

**ingest guardrails**
The deterministic, general safety net (`bank.guardrails.apply_guardrails`) the **Ingestor** and `load_questions` both run over a freshly-parsed paper — after `parse_quality`, before de-dup — so no structural defect is silently persisted. It is **Layer 2** behind the Extractor's closed-enum schema (**Layer 1**): where Layer 1 stops a *live* extraction emitting a bad value, Layer 2 also catches *committed/legacy* JSON. Per question it resolves `chapter_slug` via the **ChapterResolver**, backfills the flat `options` from `content.options`, and flags marks↔section mismatch, bad enums, MCQ-with-<2-options, and lost/continued/split stems (an empty or bare-number stem, or one beginning at an orphaned `(b)`/`(c)` sub-part label — the OR-half the model split into its own entry, validated on 31-2-3); per paper (board-sized batches only, so a teacher worksheet from #104 isn't falsely flagged) it flags blueprint drift from the 20/6/7/3/3 = 39 shape. Findings land in `Question.review_flags` and downgrade **parse_quality**. Replaces the overfitted one-off `fix_parsed.py`/`validate_tags.py` scripts (audit #108).

**ChapterResolver**
`bank.guardrails.resolve_chapter_slug(emitted, canonical) → (slug | None, matched)` — snaps a model-emitted chapter slug *toward* the closed 13-slug taxonomy rather than blacklisting known-bad strings, so it generalises to unseen variants. Three escalating strategies: exact match on the filler-stripped token form (`_`↔`-`, dropped `and`/`the`/`of`), canonical-token-subset (`heredity-and-evolution` → `heredity`), then `difflib` fuzzy ratio (spelling, `colorful` → `colourful`). Below confidence → `(None, False)`, which flags `chapter_unresolved` rather than silently nulling the chapter.

**LLMClient**
Provider-agnostic LLM seam used by the **Extractor** (and future ingestion/editor features). `extract(pdf_bytes, prompt, response_schema) → dict` — sends the PDF + prompt and gets back JSON conforming to a provider-enforced response schema. One adapter ships: `GeminiClient`, a thin wrapper over `google-genai`'s native-PDF structured output that keeps the key server-side. Model from `GEMINI_MODEL` (default `gemini-3.5-flash`), key from `GEMINI_API_KEY`, timeout from `LLM_TIMEOUT_SECONDS`. `make_llm_client()` returns the default. Lives in `ai_services.llm`.

**CognitiveLevel**
Bloom-style classification of a Question — Remember (R), Understand (U), Apply (Ap), Analyse (An). Drives the **DifficultyLevel** mix.

**DifficultyLevel**
*Paper-level.* Named distribution of cognitive levels driving the **QuestionPicker**'s mix: `easy`, `standard`, `hard`. Defined in `papers.picker.DIFFICULTY_LEVELS`. Distinct from **QuestionDifficulty** below — same English word, different grain and value set; don't conflate them.

**QuestionDifficulty**
*Per-question.* The contract's `metadata.difficulty` label: `easy`, `medium`, `hard`, derived from a single Question's **CognitiveLevel** by `papers.document._QUESTION_DIFFICULTY_BY_COG` (R→easy, U/Ap→medium, An→hard). Not a stored field — computed at mapping time. Note `standard` (paper-level) ≠ `medium` (question-level): the two scales deliberately do not share value names beyond `easy`/`hard`.

**Section**
The five fixed sections of a CBSE Cl.10 Science paper: A (MCQ), B (VSA), C (SA), D (LA), E (Case-based).

**Slot**
One question position in a paper template. Carries section, question type, marks, and optional **OR-group**. Lives in `papers.template.Slot`.

**OR-group**
A pair of Slots presenting an "Answer A OR B" choice to the student. Both slots draw distinct Questions; only one contributes to total marks. Identified by an `or_group: int` shared by exactly two Slots.

**PaperTemplate**
A **Preset** plus its expanded list of Slots. Produced by the **TemplateBuilder**, consumed by the **QuestionPicker** and **PaperBuilder**. Lives in `papers.template.PaperTemplate`.

**Preset**
A named recipe for a kind of paper — currently `board`, `half_yearly`, `unit_test`. Bundles the slot-layout function with display metadata (`template_name`, `exam_type`, `duration_minutes`) used to populate **PaperDocumentV1**. Single source of truth for "what defines this kind of paper". Lives in `papers.template.Preset`; instances in `_PRESETS`.

**TemplateBuilder**
Module that turns a preset name into a validated PaperTemplate. The seam between "what kind of paper" (preset) and "what slots does that imply" (PaperTemplate).

**QuestionPicker**
Module that fills a PaperTemplate's Slots from the Question bank, honouring chapter weights and the DifficultyLevel's cognitive-level mix. Best-effort: unfillable slots are reported, not raised. **Pool gate:** `parse_quality__in=['clean','partial']` — see ADR-0002.

**QuestionPool**
In-memory map of `(section, qtype, marks) → list[(question_id, chapter_slug, cognitive_level)]`. Internal seam of QuestionPicker that lets the allocator be tested without the ORM.

**PaperOptions**
Teacher inputs to QuestionPicker: the PaperTemplate, chosen chapter slugs (empty = all), per-chapter weights (optional), difficulty name.

**FilledTemplate**
QuestionPicker output: parallel list of question ids (None where unfilled), parallel list of alternate question id lists (swap candidates, not persisted), + a **CoverageReport**.

**CoverageReport**
The persisted record of *what got covered and what couldn't be filled*: per-chapter counts, per-cognitive-level counts, list of unfilled slots with reasons. Lives on `Paper.report`.

**Paper**
A persisted question paper for a teacher. Owns title, total marks, the CoverageReport, and an ordered list of **PaperQuestions**.

**PaperQuestion**
Ordered placement of a Question within a Paper at assembly time. Carries paper, question, order, section, optional or_group. **Not** read at render time — the renderer consumes `Paper.document` (PaperDocumentV1). PaperQuestion rows are the assembly snapshot, kept for cross-paper analytics (e.g. UsageTracker in Slice 10).

**PaperBuilder**
The coordinator. `assemble(...) → AssemblyResult{paper, document}` — single entry point. Calls TemplateBuilder, runs QuestionPicker, persists the Paper + PaperQuestion rows, maps to PaperDocumentV1, and saves the document on the Paper. Used by the assemble view and tests.

**PaperDocumentBuilder**
Mapping layer that converts a `Paper`, `FilledTemplate`, and `PaperOptions` into a `PaperDocumentV1` dict. No DB writes. All IDs are derived (`paperId = "paper_{pk}"`, `questionId = "q_{pk}"`, `slotId = "slot_{section}_{index}"`). Lives in `papers.document`.

**PaperDocumentV1**
The JSON contract returned by `POST /api/papers/assemble`. Section-wise, slot-based paper document consumed by the frontend BlockNote editor AND the PDF renderer. Top-level shape: `{schemaVersion, request, template, paper, questions[]}`. Single source of truth at render time — `papers.pdf.render_paper_pdf(document)` reads it directly. Full specification in `contracts/v1_contract.md`.

**School**
A tenant. Optional FK on Question and Paper. Slice 1 keeps multi-tenancy passive; full enforcement comes later.

## Architecture terms

These mirror `.claude/skills/improve-codebase-architecture/LANGUAGE.md`. Reuse the vocabulary in PRs, ADRs, and docstrings.

- **Module** — anything with an interface and an implementation.
- **Interface** — everything a caller must know to use the module.
- **Seam** — where an interface lives; a place to alter behaviour without editing in place.
- **Adapter** — a concrete thing satisfying an interface at a seam.
- **Depth** — leverage at the interface (a lot of behaviour, small interface).
- **Locality** — change, bugs, knowledge concentrated in one place.

## LLM orchestration terms

Vocabulary for the LangGraph migration. Names the design in ADR-0005 (orchestration
layer) and ADR-0006 (durability). These are the agreed terms; implementation is
sequenced, not yet built — use them in code/PRs as the migration lands.

**LLM workflow**
A multi-step LLM-judgment orchestration — one that branches on model output, loops
with retries, or pauses for review. Expressed as **one compiled LangGraph
`StateGraph`** (the single workflow idiom), living in the `workflows/` package and
invoked uniformly. The "altitude 2" pattern; it composes **model seam** calls in
its nodes and persists via the **checkpointer**. The deterministic engine
(`QuestionPicker`, `PaperBuilder`, …) is *not* an LLM workflow — it is plain Python
the graphs call. See ADR-0005.
_Avoid_: agent, chain, pipeline (for this).

**model seam** (chat-model factory)
The "altitude 1" pattern — *call the model once*. `make_chat_model(purpose)` in
`ai_services.llm` is the one place that constructs a provider-agnostic LangChain
chat model and owns provider/model/key/tracing/retry. Successor to the `LLMClient`
adapter (ADR-0004). Tests inject a fake factory, not a patched module. See ADR-0005.
_Avoid_: LLM gateway, model wrapper.

**job ledger**
The queryable Postgres lifecycle record of an async workflow (`IngestionJob`;
planned `GenerationBatch`): `status`, `school`, owner, result counts, the poll
endpoint, and a `thread_id` pointer to the **checkpointer**. The business record the
API reads — distinct from execution state. See ADR-0006.
_Avoid_: job queue, task record.

**checkpointer**
LangGraph's `PostgresSaver`, persisting an **LLM workflow**'s in-flight execution
state keyed by `thread_id` — the engine-internal record that makes a workflow
resumable after a crash and lets it pause for human review and resume from a
separate process (the cron-drain). The complement to the **job ledger**: ledger =
"what/who/status", checkpointer = "where in the graph". See ADR-0006.
_Avoid_: cache, session store.
