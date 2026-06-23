# CONTEXT — Canonical Domain Terms

Use these names exactly in code, docs, tests, and issue language. Keep this file
lean; put explanations, workflows, and history in ADRs or issue docs.

## Bank

- **Question**: One canonical bank item with Chapter, QuestionType, marks,
  content, provenance, parse quality, review flags, and optional answer/diagram.
  Owner: `bank.models.Question`.
- **QuestionType**: Contract-string enum shared with `PaperDocumentV1`; do not
  add a mapping layer. Owner: `bank.models.QuestionType`.
- **Chapter**: Closed CBSE Class 10 Science taxonomy, identified by slug and
  subject area. Owner: `bank.models.Chapter`.
- **SubjectArea**: Biology, Chemistry, or Physics; derived from Chapter.
- **Topic**: Freeform LLM-emitted question topic strings in `Question.topic_names`;
  distinct from corpus **ChapterMapNode**. No Topic model yet.
- **Content**: Structured question body using contract regions and content items.
  Owner: `bank.content`.
- **primary_form**: Dominant non-text form a Question depends on: none, diagram,
  or table. Orthogonal to QuestionType.
- **parse_quality**: Structural picker gate: clean, partial, or broken.
- **review_flags**: Deterministic reason codes explaining why a Question needs
  human review.
- **verified**: Human has approved a paper containing the Question; not a picker
  gate.
- **source provenance**: Flat source fields on Question: type, name, file, page,
  and original question number.

## Ingestion

- **Ingestor**: Coordinator that persists parsed Questions and applies structure,
  provenance, dedupe, guardrails, and diagram cropping. Owner: `bank.ingestor`.
- **Extractor**: Adapter seam that turns source PDFs into structured Question
  payloads. Default implementation is model-backed.
- **DiagramCropper**: Adapter seam that turns localized figure boxes into stored
  diagram assets.
- **IngestionJob**: Teacher PDF upload drained out-of-request and resumable via
  the extraction workflow. Owner: `bank.models.IngestionJob`.

## Paper Assembly

- **Preset**: Named paper recipe.
- **PaperTemplate**: Expanded Slots for one Preset.
- **Slot**: One required paper position.
- **OR-group**: Two alternative Slots where only one contributes marks.
- **QuestionPicker**: Fills a PaperTemplate with eligible Questions.
- **CoverageReport**: Coverage and unfilled-slot diagnostics for a picked paper.
- **Paper**: Persisted assembled paper.
- **PaperDocumentV1**: Render-time paper contract consumed by editor and PDF.

## AI Question Generation

- **QuestionGenerator**: Provider-neutral seam for bulk generated Questions.
  Owner: `bank.generation`.
- **GenerationBatch**: Durable teacher-owned generation job with selected
  Chapters, optional canonical ChapterMapNode IDs, optional topic hints,
  difficulty, status, timestamps, and failure text. Owner:
  `bank.models.GenerationBatch`.
- **GeneratedQuestionCandidate**: Valid generated Question payload linked to a
  GenerationBatch with optional grounding manifest; review-only until accepted
  into Question bank.
- **Generated Question Gate**: Deterministic validation before generated payloads
  become candidates. Owner: `bank.generated_question_gate`.
- **AI-generated provenance**: Source/answer provenance applied to accepted
  generated Questions.

## Corpus And Grounding

- **TextbookDocument**: One canonical extracted NCERT chapter with immutable
  extraction provenance. Owner: `corpus.models.TextbookDocument`.
- **TextbookElement**: One source-addressable extracted element with source
  order, page, text/structure, and optional asset. Owner: `corpus.models`.
- **ChapterMapNode**: Corpus-owned section/topic/landmark node with source-order
  ownership range; distinct from bank Topic.
- **ChapterMapEdge**: Evidence-backed relationship between ChapterMapNodes:
  contains, next, or references.
- **RetrievalChunk**: Stable citation-bearing group of TextbookElements owned by
  one ChapterMapNode; runtime NCERT context for generation.
- **GroundingContext**: Ordered retrieved RetrievalChunks plus exact citations;
  not persisted independently.
- **TextbookRetriever**: Corpus retrieval seam returning GroundingContext.
  Lexical and dense adapters live in `corpus.retrieval`.
- **EmbeddingClient**: Provider-neutral vector seam with explicit model, version,
  and dimensions. Owner: `corpus.embeddings`.
- **Selected Topic Grounding Context**: Query-free assembly of one selected
  ChapterMapNode subtree for question-and-answer generation.

## People And Tenancy

- **Teacher**: Authenticated user who creates papers, uploads PDFs, or starts
  generation for their school.
- **School**: Tenant boundary for teacher-owned runtime data.

## Avoid

- Do not use **Topic** for corpus map nodes; say **ChapterMapNode**.
- Do not call generated payloads **Questions** until accepted into the bank.
- Do not call RetrievalChunks **Questions** or **Topics**.
- Prefer concrete domain names over vague service/handler/component language.
