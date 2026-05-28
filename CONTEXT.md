# CONTEXT — domain glossary

Single source of truth for the vocabulary used in this codebase. Module names, class names, and documentation should use these terms exactly. New names must be added here before they are used in code.

This file is read by `/improve-codebase-architecture` and other architecture-aware agents.

## Domain terms

**Question**
A single bank item. Has section (A–E), question type (MCQ/VSA/SA/LA/CASE), marks, chapter, cognitive level, text, optional MCQ options, optional answer. Lives in `bank.models.Question`.

**Chapter**
A canonical CBSE Class 10 Science chapter, seeded from the NCERT taxonomy. Identified by slug. Lives in `bank.models.Chapter`.

**Ingestor**
Coordinator for the ingestion pipeline. Reads PDF bytes, parses them to text, strips Hindi, segments into raw questions, tags each with chapter + cognitive level, extracts diagrams, and persists `Question` rows as `verified=False`. Separately, `Ingestor.apply_answers(answer_pdf_bytes) → int` fills in `Question.answer` from a marking-scheme PDF. Adapters at four seams: **Parser** (default `PdfplumberParser`), **Tagger** (default `LLMTagger`), **DiagramExtractor** (default `PdfplumberDiagramExtractor`), **AnswerSource** (default `MarkingSchemeAnswerSource`). Lives in `bank.ingestor.Ingestor`. Symmetric to `PaperBuilder`.

**Parser / Tagger / DiagramExtractor / AnswerSource**
The four adapter seams of the Ingestor. `Parser.parse(pdf_bytes) → str`. `Tagger.tag(raw_questions, chapters) → list[dict]` with `chapter_slug` + `cognitive_level` added. `DiagramExtractor.extract(pdf_bytes, raw_questions) → list[bytes | None]` returning cropped image bytes or None per question. `AnswerSource.answers(pdf_bytes) → dict[int, str]` mapping question number to answer text — consumed by `Ingestor.apply_answers`, which assigns the n-th parsed answer to the n-th unverified Question ordered by id (CBSE marking schemes mirror the paper's numbering). Tests inject stub adapters.

**LLMClient**
Provider-agnostic LLM seam used by `LLMTagger` (and future ingestion features). `complete(prompt, max_tokens) → str`. Three adapters ship: `AnthropicClient`, `OpenAIClient`, `GeminiClient` — each imports its SDK lazily. Selected via `LLM_PROVIDER` env var (default `anthropic`). Lives in `bank.llm`.

**CognitiveLevel**
Bloom-style classification of a Question — Remember (R), Understand (U), Apply (Ap), Analyse (An). Drives the **DifficultyLevel** mix.

**DifficultyLevel**
Named distribution of cognitive levels: `easy`, `standard`, `hard`. Defined in `papers.picker.DIFFICULTY_LEVELS`.

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
Module that fills a PaperTemplate's Slots from the Question bank, honouring chapter weights and the DifficultyLevel's cognitive-level mix. Best-effort: unfillable slots are reported, not raised.

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
