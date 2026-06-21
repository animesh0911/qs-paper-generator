# Ubiquitous Language

This is the human-readable glossary. `CONTEXT.md` is the lean machine-facing
copy agents should load first.

## Bank

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Question** | One canonical bank item that can be picked into papers. | Item, row, generated output |
| **QuestionType** | Contract-string type of a Question, shared with `PaperDocumentV1`. | Q type, section type |
| **Chapter** | Closed CBSE Class 10 Science chapter taxonomy entry. | Unit, lesson |
| **Topic** | Freeform question topic string emitted during bank ingestion or generation. | ChapterMapNode, canonical topic |
| **Content** | Structured region-based body of a Question. | Text blob, markdown |
| **parse_quality** | Structural eligibility signal: clean, partial, or broken. | Validity, verification |
| **review_flags** | Reason codes explaining why a Question needs human review. | Errors, warnings |
| **verified** | Signal that a human approved a paper containing the Question. | Picker-ready, reviewed |

## Paper Assembly

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Preset** | Named recipe for a paper shape. | Template |
| **PaperTemplate** | Expanded Slots for one Preset. | Blueprint |
| **Slot** | One required position in a paper. | Question placeholder |
| **OR-group** | Pair of alternative Slots where only one contributes marks. | Choice group |
| **QuestionPicker** | Domain component that fills Slots with eligible Questions. | Selector service |
| **CoverageReport** | Diagnostics for chapter/cognitive coverage and unfilled Slots. | Stats, result |
| **PaperDocumentV1** | Render-time paper contract consumed by editor and PDF. | Paper JSON |

## Generation

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **QuestionGenerator** | Seam that asks a model for generated Question payloads. | Generator service |
| **GenerationBatch** | Durable teacher-owned bulk generation job. | Job, batch job |
| **GeneratedQuestionCandidate** | Valid generated payload awaiting teacher review. | Question, draft question |
| **Generated Question Gate** | Deterministic validator for generated payloads. | Model validation |
| **AI-generated provenance** | Source and answer provenance stamped onto accepted generated Questions. | AI flag |

## Corpus And Grounding

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **TextbookDocument** | One canonical extracted NCERT chapter artifact. | Corpus file |
| **TextbookElement** | One source-addressable extracted textbook element. | Chunk, paragraph |
| **ChapterMapNode** | Corpus-owned section/topic/landmark node with source ownership. | Topic |
| **ChapterMapEdge** | Evidence-backed relationship between ChapterMapNodes. | Graph link |
| **RetrievalChunk** | Citation-bearing group of TextbookElements used as runtime context. | Passage, topic chunk |
| **GroundingContext** | Ordered retrieved chunks and citations supplied to generation. | RAG result |
| **TextbookRetriever** | Seam that returns GroundingContext. | Search service |
| **EmbeddingClient** | Provider-neutral seam for vectorizing text batches. | Embedding provider |
| **Selected Topic Grounding Context** | Query-free context assembled from one selected ChapterMapNode subtree. | Semantic search result |

## Relationships

- A **Question** belongs to one **Chapter** and may carry many freeform **Topics**.
- A **PaperTemplate** contains many **Slots**; a **QuestionPicker** fills them with **Questions**.
- A **GenerationBatch** produces many **GeneratedQuestionCandidates**.
- A **GeneratedQuestionCandidate** becomes a **Question** only after teacher acceptance.
- A **TextbookDocument** contains many **TextbookElements** and **ChapterMapNodes**.
- A **RetrievalChunk** belongs to exactly one **ChapterMapNode**.
- A **GroundingContext** contains **RetrievalChunks**, not **Questions**.

## Example Dialogue

> **Dev:** "Can I use **Topic** to fetch NCERT context?"
> **Domain expert:** "No. **Topic** is a freeform bank string. Use a **ChapterMapNode** when selecting textbook context."
> **Dev:** "So generated output from a **GenerationBatch** is a **Question**?"
> **Domain expert:** "Not yet. It is a **GeneratedQuestionCandidate** until the teacher accepts it into the bank."
> **Dev:** "And the model receives **RetrievalChunks** through a **GroundingContext**?"
> **Domain expert:** "Exactly. The chunks cite the textbook; the candidate still has to pass the **Generated Question Gate**."

## Flagged Ambiguities

- **Topic** must not mean **ChapterMapNode**. Bank Topics are freeform strings; corpus nodes are canonical source ranges.
- **Question** must not mean generated payload. Use **GeneratedQuestionCandidate** before acceptance.
- **verified** must not mean picker eligibility. Use **parse_quality** for structural eligibility.
