# Ubiquitous Language

Authoritative glossary of every domain term used in code, docs, and conversation. If you find yourself reaching for a synonym, stop and use the term here.

The machine-readable copy lives in [`CONTEXT.md`](../CONTEXT.md) at the repo root and is preferred by architecture-aware agents.

## Bank

**Question** — single bank item. Section, qtype, marks, chapter, cognitive level, text, options, answer, `verified` flag.

**Chapter** — NCERT Cl.10 Science chapter. Identified by slug (e.g. `electricity`, `life-processes`). Order matches the textbook.

**Section** — one of A (MCQ), B (VSA), C (SA), D (LA), E (Case-based). Fixed by CBSE board layout.

**QuestionType** — MCQ / VSA / SA / LA / CASE. Tied to section by board convention but stored separately so future presets can mix.

**CognitiveLevel** — R (Remember), U (Understand), Ap (Apply), An (Analyse). Bloom-style classification.

**Ingestor** — coordinator for the ingestion pipeline. Parses a PDF, segments into raw questions, tags them, persists `Question` rows as `verified=False`.

**Parser / Tagger** — the two adapter seams of the Ingestor. Default `PdfplumberParser` and `LLMTagger`. Tests inject stubs.

**LLMClient** — provider-agnostic LLM seam in `ai_services.llm`. `complete(prompt, max_tokens) → str`. One adapter: `LiteLLMClient` over `litellm.completion`, spanning OpenAI / Anthropic / Gemini. Model chosen via `LLM_MODEL` (provider-prefixed), falling back to `LLM_PROVIDER`.

## Paper template

**Slot** — one question position in a paper template. (section, qtype, marks, or_group?).

**OR-group** — pair of Slots representing "Answer A OR B". Both filled with distinct Questions; only one contributes to total marks.

**PaperTemplate** — a `Preset` plus its expanded list of Slots. Output of TemplateBuilder, input to QuestionPicker.

**Preset** — bundled recipe for a kind of paper: name, template_name, exam_type, duration_minutes, build_slots. Currently `board`, `half_yearly`, `unit_test`. Single source of truth — used by both TemplateBuilder and PaperDocumentBuilder.

**TemplateBuilder** — turns a preset name into a validated PaperTemplate.

## Question picking

**DifficultyLevel** — named cognitive-level distribution. `easy` / `standard` / `hard`.

**PaperOptions** — teacher's inputs to QuestionPicker: the PaperTemplate, chapter slugs, per-chapter weights, difficulty.

**QuestionPool** — in-memory `{bucket → [(qid, chapter_slug, level)]}`. Internal seam in QuestionPicker that lets the allocator be tested without the ORM.

**FilledTemplate** — QuestionPicker output: parallel `question_ids` (None where unfilled) + a CoverageReport.

**CoverageReport** — `{coverage, cog_coverage, unfilled}`. Persisted on `Paper.report` and returned in API.

**QuestionPicker** — fills a PaperTemplate's Slots best-effort, honouring chapter weights and the DifficultyLevel.

## Paper

**Paper** — persisted paper. Title, total marks, CoverageReport, ordered PaperQuestions, `document` (PaperDocumentV1), `status` (draft/approved).

**PaperQuestion** — placement of a Question in a Paper at assembly time. Order, section, or_group. **Not** read at render time — the document is the render-time source of truth. Kept for cross-paper analytics (UsageTracker, Slice 10).

**PaperBuilder** — single `assemble(...)` coordinator. Builds template → picks questions → persists Paper + PaperQuestions → maps to PaperDocumentV1 → returns `AssemblyResult{paper, document}`.

**PaperDocumentBuilder** — mapping layer that converts a `Paper` + `FilledTemplate` + `PaperOptions` into a `PaperDocumentV1` dict. No DB writes.

**PaperDocumentV1** — single render-time contract returned by `POST /papers/assemble`. Consumed by both the frontend BlockNote editor and the PDF renderer.

## Identity

**School** — tenant. Optional FK on Question and Paper.

**User** — Django user with a school FK; staff users see answer keys.

## What we avoid

- "service" — say the specific module (`QuestionPicker`, `TemplateBuilder`).
- "component" inside backend prose — Django doesn't use that term. Say "module" or "view" or "model".
- "boundary" — say **seam** (overloaded with DDD's "bounded context").
- "handler" — say "view" (Django) or the module name.
