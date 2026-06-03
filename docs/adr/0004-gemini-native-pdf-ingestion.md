# Gemini native-PDF ingestion (supersedes ADR-0003)

Bank ingestion sends the **source PDF directly** to a multimodal LLM (Gemini,
default `gemini-3.5-flash`) which returns structured questions conforming to the
`paper_document.v1` question shape (contract §8–10) via a provider-enforced
response schema. There is no intermediate text-extraction step: `pdfplumber`,
the regex segmenter, the regex shape-detectors (assertion-reason / case-based /
internal-choice / options), and the marking-scheme regex parser are all removed.

The model does, in one pass per section: English-only filtering (discard the
Hindi column outright), question segmentation, type classification, `content`
region structuring (stem / options / assertion / reason / passage / subparts /
choices), `rawText` fallback (marks stripped), and figure localisation
(`{page, bbox}` per diagram). Diagrams are then cropped deterministically with
PyMuPDF from those boxes and stored as assets, referenced by the question's
content — the LLM never emits pixels.

## Why

CBSE PYQ layouts vary too much for regex, and the prior design (ADR-0003) still
depended on `pdfplumber` text extraction feeding an LLM segmenter plus a
deterministic fidelity guardrail. That guardrail compared LLM output against the
extracted text blob — but a native-PDF model has no such blob to grade against,
and the comparison was the main reason the text-extraction step survived.
Removing text extraction removes the guardrail's input, so the guardrail goes
too.

A native multimodal call is simpler (one model, one pass, no text-extraction
library, no regex), reads scanned and born-digital pages uniformly, handles the
bilingual two-column instruction tables that broke naive left-to-right OCR, and
keeps equations/tables intact. Ingestion is an **offline, one-time-per-year
batch over ~51 papers**, so latency and per-call cost are secondary to accuracy.
The default is `gemini-3.5-flash` — newest-generation and near-pro accuracy at
flash speed/cost, a strong fit for this batch. `GEMINI_MODEL` is a one-env switch
to a pro tier (`gemini-3.1-pro-preview` now, `gemini-3.5-pro` once GA) if review
shows the flash tier dropping or misreading too much.

## What replaces the deleted guardrail

The backstop is the existing **human verification gate** (ADR-0002): ingested
rows land `verified=False` and only reviewed rows reach the picker. The
verifier reviews questions *and* crops in Django Admin. We trade an automated
fidelity score for a human pass — acceptable because the batch is tiny and
one-time, and because the model is a far more faithful transcriber than the
regex path it replaces.

## Consequences

- `pdfplumber` dropped from `requirements.txt`; PyMuPDF (`pymupdf`) added for
  figure cropping. `litellm` is replaced by the Gemini SDK in `ai_services.llm`
  (the `LLMClient` seam stays; the adapter now speaks PDF + response schema).
- `parse_quality` reverts to a plain structural self-assessment (set by the
  model / coordinator), no longer touched by a verification pass. CONTEXT.md
  updated.
- ADR-0003's `LLMSegmenter`/`RegexSegmenter`/`_verify` and the two-pass
  (segment then tag) design are gone — one call now segments, classifies,
  structures, and tags.
- `load_questions` keeps working as a deterministic reload of committed,
  reviewed JSON (so the bank rebuilds without re-billing Gemini); its input is
  now the model's output shape, and it no longer runs `_verify`.
- Residual risk: the model can still drop or misread a question, and crops can
  clip. Both are caught at human review, not by code. If review shows crops are
  routinely bad, add a figure-detection model then — not speculatively now.
