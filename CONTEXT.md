# CONTEXT — domain glossary

Single source of truth for the vocabulary used in this codebase. Module names, class names, and documentation should use these terms exactly. New names must be added here before they are used in code.

This file is read by `/improve-codebase-architecture` and other architecture-aware agents.

## Domain terms

**Question**
A single bank item. Has section (A–E), **QuestionType** (contract-string enum), marks, chapter, cognitive level, **rawText**, structured **content** (contract-shape JSON), **topic_names** (freeform LLM-emitted strings), **source provenance** (`source_type`, `source_name`, `source_file_name`, `source_page_number`, `source_original_qnum`), **parse_quality**, **verified**, optional answer, optional diagram. Lives in `bank.models.Question`.

**QuestionType**
Enum on `Question.qtype`. Values are **identical to PaperDocumentV1 `questionType` strings** — no mapping layer. Members: `mcq`, `assertion_reason`, `very_short_answer`, `short_answer`, `long_answer`, `case_based`, `internal_choice`, `diagram_based`, `table_based`, `custom`. Classified at ingest from the question's structure (e.g. `assertion`+`reason` keys → `assertion_reason`), with section default as fallback. See ADR-0001.

**SubjectArea**
The three CBSE Science streams: `Biology`, `Chemistry`, `Physics`. Lives on `Chapter.subject_area` (Bio = chapters 5, 6, 7, 8, 13; Chem = 1–4; Phys = 9–12). Derived onto questions via `Question.chapter.subject_area`; surfaces in `PaperDocumentV1` `metadata.subjectArea` and section subtitles.

**Chapter**
A canonical CBSE Class 10 Science chapter, seeded from the NCERT taxonomy. Identified by slug. Carries **subject_area**. Lives in `bank.models.Chapter`. Hardcoded taxonomy in `migrations/0003_seed_chapters.py` — LLM tagger picks from this closed list, never invents new chapters.

**Topic**
A subdivision *within* a chapter (e.g. "Monohybrid Cross" inside `heredity`). V1 stores topics as **freeform LLM-emitted strings** on `Question.topic_names = list[str]`. No `Topic` model. Canonicalisation deferred until V2 (cluster strings or seed from textbook TOC then). Emitted by the **Tagger**, persisted by the Ingestor, surfaced in `PaperDocumentV1` `metadata.topicNames`.

**primary_form**
Field on `Question` (`bank.models.PrimaryForm`): the dominant non-text form a question depends on — `none`, `diagram_based`, or `table_based`. Emitted by the **Tagger**, *orthogonal* to **QuestionType** (a `short_answer` can be `diagram_based`). `diagram_based` also reinforces `Question.has_diagram` at ingest. Stored for future form-aware picking/rendering; not yet a picker gate.

**parse_quality**
Field on `Question` — the parser's self-assessment of structural completeness. Values: `clean` (parsed structure matches detected qtype exactly), `partial` (parsed but with caveats, e.g. options truncated), `broken` (parser confidence too low, or teacher explicitly marked unsalvageable). **The picker gate**: only `clean` + `partial` are eligible for picking. Replaces the previous `verified=True` gate. See ADR-0002.

**verified**
Field on `Question`. Semantics: **"a human has seen this question in an approved paper and did not reject it."** Set to `True` automatically when `Paper.approve` runs — every referenced question is flipped. **Not** a picker gate. Used by analytics and future "show only battle-tested questions" filters. See ADR-0002.

**source provenance**
Five flat fields on `Question` recording where a row came from: `source_type` (e.g. `previous_year_paper`, `sample_paper`, `question_bank`), `source_name` (e.g. `"31-2-1 Science 2026"`), `source_file_name` (e.g. `"31-2-1.pdf"`), `source_page_number`, `source_original_qnum`. The batch-wide three (`source_type`, `source_name`, `source_file_name`) are set at ingest by the `_Provenance.from_filename` helper — it takes the uploaded filename (deriving `source_name` from the filename stem) plus an optional `source_type` request field (default `previous_year_paper`). `source_page_number` and `source_original_qnum` are a **V2 deferral** — the Segmenter does not yet track page offsets or per-question original numbering, so they stay blank. Mapped to the `PaperDocumentV1` `source` object by `PaperDocumentBuilder._build_source`, which emits the optional `fileName`/`pageNumber`/`originalQuestionNumber` only when set.

**Ingestor**
Coordinator for the ingestion pipeline. Reads PDF bytes, parses to text per page, strips Hindi, segments into raw questions, **classifies qtype from structure** (assertion-reason / case-based / internal-choice / section-default), **builds structured `content`** matching the contract shape per qtype, tags each with chapter + cognitive level + **topic_names** + **primary_form** via LLM, extracts diagrams, **records source provenance** from the source filename, **computes `parse_quality`** per row, and persists `Question` rows with `verified=False`. Separately, `Ingestor.apply_answers(answer_pdf_bytes) → int` fills in `Question.answer` from a marking-scheme PDF. Adapters at four seams: **Parser** (default `PdfplumberParser`), **Tagger** (default `LLMTagger`), **DiagramExtractor** (default `PdfplumberDiagramExtractor`), **AnswerSource** (default `MarkingSchemeAnswerSource`). Lives in `bank.ingestor.Ingestor`. Symmetric to `PaperBuilder`.

**Parser / Tagger / DiagramExtractor / AnswerSource**
The four adapter seams of the Ingestor. `Parser.parse(pdf_bytes) → str`. `Tagger.tag(raw_questions, chapters) → list[dict]` — adds `chapter_slug`, `cognitive_level`, `topic_names: list[str]`, and `primary_form ∈ {none, diagram_based, table_based}` per question. `DiagramExtractor.extract(pdf_bytes, raw_questions) → list[bytes | None]` returning cropped image bytes or None per question. `AnswerSource.answers(pdf_bytes) → dict[int, str]` mapping question number to answer text — consumed by `Ingestor.apply_answers`, which assigns the n-th parsed answer to the n-th unverified Question ordered by id (CBSE marking schemes mirror the paper's numbering). Tests inject stub adapters.

**LLMClient**
Provider-agnostic LLM seam used by `LLMSegmenter`, `LLMTagger` (and future ingestion/editor features). `complete(prompt, max_tokens) → str`. One adapter ships: `LiteLLMClient`, a thin wrapper over `litellm.completion` that gives a single call shape across OpenAI, Anthropic, Gemini, and future providers with keys kept server-side. Model selected via `LLM_MODEL` (provider-prefixed, e.g. `anthropic/claude-...`), falling back to `LLM_PROVIDER` + per-provider model env vars (default provider `anthropic`). `make_llm_client()` returns the default. Lives in `ai_services.llm` (shared by bank ingestion and editor AI).

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
