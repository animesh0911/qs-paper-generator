# Ubiquitous Language

Authoritative glossary of every domain term used in code, docs, and conversation. If you find yourself reaching for a synonym, stop and use the term here.

The machine-readable copy lives in [`CONTEXT.md`](../CONTEXT.md) at the repo root and is preferred by architecture-aware agents.

## Bank

**Question** — single bank item. Section, qtype, marks, chapter, cognitive level, text, options, answer.

**Chapter** — NCERT Cl.10 Science chapter. Identified by slug (e.g. `electricity`, `life-processes`). Order matches the textbook.

**Section** — one of A (MCQ), B (VSA), C (SA), D (LA), E (Case-based). Fixed by CBSE board layout.

**QuestionType** — MCQ / VSA / SA / LA / CASE. Tied to section by board convention but stored separately so future presets can mix.

**CognitiveLevel** — R (Remember), U (Understand), Ap (Apply), An (Analyse). Bloom-style classification.

## Paper plan

**Slot** — one position in a paper plan. (section, qtype, marks, or_group?).

**OR-group** — pair of Slots representing "Answer A OR B". Both filled with distinct Questions; only one contributes to total marks.

**PaperSpec** — ordered list of Slots for one paper. Output of BlueprintEngine, input to SelectionEngine.

**Preset** — named PaperSpec factory: `board`, `half_yearly`, `unit_test`.

**BlueprintEngine** — preset name → validated PaperSpec.

## Selection

**DifficultyProfile** — named cognitive-level distribution. `easy` / `standard` / `hard`.

**SelectionInput** — teacher's selection: chapter slugs, weights, difficulty, the PaperSpec.

**CandidatePool** — in-memory `{bucket → [(qid, chapter_slug, level)]}`. Internal seam in SelectionEngine.

**SelectionResult** — engine output: parallel `question_ids` (None where unfilled) + a SelectionReport.

**SelectionReport** — `{coverage, cog_coverage, unfilled}`. Persisted on `Paper.report` and returned in API.

**SelectionEngine** — fills a PaperSpec's Slots best-effort, honouring chapter weights and the DifficultyProfile.

## Paper

**Paper** — persisted paper. Title, total marks, SelectionReport, ordered PaperQuestions.

**PaperQuestion** — placement of a Question in a Paper. Order, section, or_group. Future teacher edits land here.

**PaperAssembler** — coordinator that runs BlueprintEngine → SelectionEngine → persist.

**PaperLayout** — ORM-free flat structure consumed by the PDF renderer.

## Identity

**School** — tenant. Optional FK on Question and Paper.

**User** — Django user with a school FK; staff users see answer keys.

## What we avoid

- "service" — say the specific module (`SelectionEngine`, `BlueprintEngine`).
- "component" inside backend prose — Django doesn't use that term. Say "module" or "view" or "model".
- "boundary" — say **seam** (overloaded with DDD's "bounded context").
- "handler" — say "view" (Django) or the module name.
