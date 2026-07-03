# Production PDF Extraction: OCR + LLM vs. Native Multimodal Pipeline

## Executive Summary
This document outlines production-grade research on extracting structured questions and data from PDF exam papers. It evaluates the common practice of layout-aware OCR conversion to Markdown followed by schema-constrained LLM structuring against native Multimodal (Vision) LLM extraction. Finally, it recommends actionable architecture patterns and implications for the Mistral OCR experiment planned in this repository.

---

## 1. Flow Comparison: OCR-First vs. Native Multimodal (VLM)

Modern production document extraction pipelines rely on one of two paradigms:
1. **OCR-First Flow (OCR -> Markdown -> LLM)**: A dedicated document parsing engine converts visual files (images or PDFs) into layout-preserving text format (Markdown/JSON) as an intermediate step. A text-based LLM (e.g., Mistral Large) then ingests this text and transforms it into the final structured schema under strict programmatic constraints.
2. **Native Multimodal Flow (VLM Direct)**: The system passes page images directly to a Vision-Language Model (VLM, e.g., Gemini 2.5 Pro or GPT-4o). The VLM performs visual analysis and structured JSON synthesis in a single, unified inference step.

### Trade-off Matrix

| Metric | OCR-First Flow (e.g., Mistral OCR + Structuring LLM) | Native Multimodal Flow (VLM-only) |
| :--- | :--- | :--- |
| **Text & Symbol Accuracy** | **Superior.** Deterministic optical character recognition ensures that alphanumeric characters, mathematical formulas, subscripts, and small digits are extracted verbatim without hallucination. | **Moderate to Low.** VLMs are prone to visual token hallucinations, occasionally misreading small digits (e.g., mistaking a "3" for an "8" in marks or equation subscripts). |
| **Layout & Column Awareness** | **High.** Advanced OCR engines (Mistral OCR, Docling, Marker) reconstruct two-column exam sheets, headers/footers, and lists into structured Markdown in reading order. | **Excellent (Conceptual).** VLMs natively grasp visual hierarchy and spatial grouping, but translating this to exact JSON structure can drift without heavy prompting. |
| **Inference Cost** | **Low.** Downstream text models are significantly cheaper per token. OCR processing costs are minimal (e.g., Mistral OCR is ~$1 per 1,000 pages). | **Very High.** Visual inputs consume substantial token counts (e.g., 1k-3k tokens per high-res page image), which scales poorly for large datasets. |
| **Latency** | **Low to Moderate.** OCR adds 1-2 seconds of pre-processing, but subsequent text LLM generation is fast and has lower output token footprints. | **High.** Processing high-resolution images incurs high initial time-to-first-token (TTFT) and slower overall generation speeds. |
| **Handling Diagrams & Visuals** | **Weak.** Images must be cropped or represented by coordinate boxes. The text LLM cannot answer questions that depend entirely on the visual content of a drawing. | **Excellent.** Natively reasons about charts, geometric diagrams, physics apparatus drawings, and flowcharts directly. |
| **Scanned / Low-Res PDFs** | **Strong.** Robust preprocessing algorithms correct skew, contrast, and noise. | **Poor.** High susceptibility to accuracy drop-offs on scans below 150 DPI or noisy/smudged papers (the visual "cliff effect"). |

---

## 2. Core Pipeline Production Topics

### A. Page Chunking & Slicing
*   **The Page-by-Page Ingestion Pattern**: Production systems typically slice PDFs into single-page documents and process them in parallel. This offers three critical benefits:
    1.  **Parallelization**: Scales throughput by distributing pages across worker nodes.
    2.  **Failure Isolation**: If a single page fails due to parsing or structuring errors, it doesn't crash the entire ingestion job.
    3.  **State Checkpointing**: Saves progress incrementally, allowing resilient resumes from failures.
*   **Stitching Across Boundaries**: Exam questions or reading passages may start at the bottom of page $N$ and end on page $N+1$. Best-practice architectures handle this via:
    *   *Sliding Windows*: Appending a small tail of the previous page's Markdown as read-only context to the prompt of the subsequent page.
    *   *Post-Processing Assemblers*: A lightweight heuristic stage that identifies orphan question items (e.g., missing options or stem sentences) and merges them with preceding items.

### B. Layout & Markdown Preservation
*   **Why Markdown is Standard**: Plain text strips away tables, headings, bold emphasis, and bullet hierarchies. Markdown acts as a structured intermediate language. Since LLMs are pre-trained extensively on Markdown text, they extract data from Markdown tables and list items with much higher fidelity than raw text streams.
*   **Reading Order Reconstruction**: Standard PDF parsers read text using raw drawing coordinates, which breaks double-column exam layouts (merging columns horizontally). Layout-aware engines (such as Mistral OCR or Docling) reconstruct the vertical reading flow, keeping paragraphs and adjacent questions separated.
*   **LaTeX Math and Science Formula Support**: Science and math papers contain formulas, equations, and chemical symbols (e.g., $\text{NaHCO}_3$). Standard OCR engines distort these into garbage text. Modern document OCR engines natively recognize mathematical elements and compile them into inline LaTeX equations (e.g., `$\text{NaHCO}_3$`), preserving their exact syntax for downstream LLM evaluation.

### C. Schema JSON & Structured Output
*   **Enforcing Output Schemas**: Raw LLM outputs are prone to syntax mistakes or schema drift. Production systems enforce structure using:
    *   **Instructor**: A library that maps LLM completions to Pydantic objects using tool-calling under the hood. It performs automatic validation and JSON coercion.
    *   **Structured Outputs (JSON Schema)**: API-level constraints (like Mistral's native json_mode or OpenAI/Gemini structured outputs) that restrict decoding search space to valid JSON matching the schema.
*   **Type Coercion**: A downstream schema normalization layer maps fuzzy LLM strings (e.g., "Multiple-Choice Question", "MCQ", "Visual Option") to canonical, clean enum choices (e.g., `mcq`, `assertion_reason`).

### D. Validation & Human-in-the-Loop (HITL)
*   **Automated Validation Gates**: Structured payloads must pass a series of heuristic checks:
    1.  *Schema Compliance*: Validating required fields and type types.
    2.  *MCQ Consistency*: Confirming that `mcq` types contain exactly four options, each with a unique label (A, B, C, D).
    3.  *Mark Integrity*: Ensuring marks are positive integers within standard bounds.
    4.  *Chapter Mapping*: Resolving freeform LLM topic names to canonical curriculum slugs.
*   **Human-in-the-Loop Routing**: If a page fails validation, or the model indicates low confidence, the question is flagged (e.g., `parse_quality = PARTIAL` or `BROKEN` with specific `review_flags`). The system routes it to a teacher-facing correction queue where they can view the original PDF page alongside the extracted fields to correct the error manually.

### E. Retry & Checkpointing
*   **Decoupling OCR and Structuring**: Running OCR and LLM structuring as separate, independent nodes is a vital production pattern. Because OCR is slow and expensive, caching or checkpointing its output is necessary. If the downstream LLM rate-limits or fails schema validation, the system retries only the structuring step using the cached Markdown, eliminating duplicate OCR API costs.
*   **Exponential Backoff and Jitter**: Transient network failures and rate limits are managed using exponential backoff with random jitter to prevent API thundering herds.
*   **Dead Letter Queues (DLQ)**: Documents that fail repeatedly are pushed to a quarantine queue for manual inspection.

---

## 3. Actionable Implications for this Repository's Ingestion Plan

### Codebase Context
This codebase implements a resumable LangGraph extraction workflow in `backend/workflows/extraction.py`. The current flow operates as:
`PDF page -> Gemini native-PDF structured extraction -> Question persistence`.

The experimental Mistral OCR plan is documented in [mistral_ocr_langgraph_experiment.md](file:///Users/varad/V/repo/qs-paper-generator/docs/Varad/mistral_ocr_langgraph_experiment.md) and backed by [ocr_extractor.py](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/ocr_extractor.py) and [mistral_ocr_poc.py](file:///Users/varad/V/repo/qs-paper-generator/backend/scripts/mistral_ocr_poc.py).

### Actionable Architecture Recommendations

#### 1. Adopt Option B (Decoupled OCR and Structuring Nodes)
We recommend bypassing Option A (minimal extractor swap) and moving directly to **Option B** (explicit OCR and structure nodes as separate check-pointed stages) in the production LangGraph state machine.
*   **Why**: Mistral OCR takes 2-4 seconds per page. The structuring LLM is fast but prone to rate limits (HTTP 429) or JSON formatting issues under strict Pydantic schemas.
*   **Implication**: By separating these steps into distinct LangGraph nodes (`ocr_page` and `structure_page`), the system checkpoints the raw Markdown text in the graph state. If structuring fails, the graph resumes from the cached Markdown rather than re-triggering the slow and costly Mistral OCR API call.

#### 2. Handle Base64 URL Scaling Constraints
*   The current proof-of-concept in [MistralOcrClient](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/ocr_extractor.py#L55) sends PDF slices as inline base64 data URLs.
*   **Implication**: This method is prone to failure on large, high-resolution pages due to payload limits.
*   **Production Fix**: Modify the pipeline to upload the PDF slices to a temporary Cloud Storage bucket (S3/GCS) and pass a short-lived signed URL to Mistral OCR. Alternatively, upload the entire multi-page PDF once using Mistral's File API, obtain a File ID, and process pages using the `file_id` referencing specific indexes.

#### 3. Leverage Mistral OCR 4 Bounding Boxes for Diagram Cropping
*   The system has a [DiagramCropper](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/diagram_cropper.py) helper to isolate figures on PDF pages.
*   **Implication**: Instead of a separate VLM call to identify coordinate ranges for diagram extraction, the system can leverage Mistral OCR 4's native `include_blocks` coordinate response.
*   **Actionable Flow**:
    1.  Call `ocr_client.process_pdf` with `"include_blocks": True`.
    2.  Filter the returned blocks list for items labeled `"image"` or `"figure"`.
    3.  Extract their bounding box coordinates and pass them directly to the `DiagramCropper` system to slice, save, and attach the image assets to the ingested questions.

#### 4. LaTeX and Subscript Conservation
*   Exam papers for CBSE Class 10 Science are heavy on chemical reactions and formulas.
*   **Implication**: Incorporate explicit guidelines in the structuring prompt (`_markdown_extraction_prompt` in [ocr_extractor.py](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/ocr_extractor.py#L142)) to instruct the LLM:
    > "Preserve all math equations and chemical formulas in standard LaTeX markdown (e.g., `$\text{CO}_2$`, `$\text{Fe}_2\text{O}_3$`, or `$v = u + at$`) exactly as formatted by the OCR model. Do not strip LaTeX delimiters or convert equations to plain text."

#### 5. Verification, Schema Coercion, and Human-in-the-Loop (HITL)
*   Integrate structured JSON question payloads returned by [MistralOcrMarkdownExtractor](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/ocr_extractor.py#L107) directly with [Ingestor.ingest_extracted](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/ingestor.py#L920).
*   **Actionable Pipeline Rules**:
    *   If the structuring LLM assigns a chapter slug that is not present in the database enum [Chapter](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/models.py#L111), default it to `None`.
    *   Run checks on the payload: if an MCQ question does not parse into exactly four distinct options, or if question marks are missing, mark the question candidate with `parse_quality = ParseQuality.PARTIAL` or `BROKEN` and raise specific `review_flags`.
    *   Ensure that such flagged items route directly to the teacher review dashboard to block raw, faulty data from entering the canonical [Question](file:///Users/varad/V/repo/qs-paper-generator/backend/bank/models.py#L133) bank.

---

## 4. References & Source Citations
1. [Mistral AI Document AI API Capability Guide](https://docs.mistral.ai/capabilities/document/) - Core specifications on PDF/Image OCR and document structuring.
2. [Mistral OCR Announcement & Feature Set](https://mistral.ai/news/mistral-ocr) - Specifications for block coordinates, LaTeX parsing, and tables.
3. [Instructor Python Client Documentation](https://github.com/jxnl/instructor) - Implementing Pydantic validation on top of LLM structured tool outputs.
4. [Vellum AI Comparison: OCR vs. Multimodal LLMs](https://www.vellum.ai/blog/ocr-vs-multimodal-llms-for-document-extraction) - Comprehensive benchmarking on cost, accuracy, and operational tradeoffs.
5. [Docling Document Parser Repository](https://github.com/DS4SD/docling) - In-depth concepts on structural chunking, table extraction, and reading order preservation.
6. [Unstructured.io - Production RAG and Document Extraction Pipelines](https://unstructured.io/) - Architectural concepts for page chunking, routing, and schema validation.
