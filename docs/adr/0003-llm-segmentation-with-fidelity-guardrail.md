# LLM segmentation with a fidelity guardrail

> **Superseded by [ADR-0004](0004-gemini-native-pdf-ingestion.md) (2026-06-03).**
> Ingestion now sends the PDF directly to a multimodal model; the text
> extraction this ADR's guardrail graded against no longer exists, so the
> `Segmenter`/`RegexSegmenter`/`_verify` design described below is removed.
> Retained for history.

The Ingestor's `Segmenter` seam splits cleaned PDF text into structured questions using an LLM (`LLMSegmenter`) instead of the regex rules of `segment_questions` (kept as `RegexSegmenter`, a deterministic fallback). CBSE PYQ layouts vary too much for regex to classify qtype and build contract-shape `content` reliably; an LLM handles the variety. To contain LLM hallucination, emitted output must pass deterministic **verification checks** against the source text before it is trusted; failures are forced to `parse_quality='broken'` (or the batch degraded to `partial`). The checks: (1) **fidelity** — each question's `text` is a whitespace-normalised substring of the source or `difflib` ratio ≥ threshold (catches invented words); (2) **coverage** — emitted question count matches the source's question-number anchors (catches dropped/merged questions); (3) **order** — emitted questions appear in source reading order, and within MCQ/assertion-reason questions the options appear in source order too (catches reordering and swapped option labels).

## Why

Regex segmentation was brittle: each new paper format leaked malformed rows into the bank. An LLM is robust to format variety but can fabricate, drop, or misattribute text. The design keeps the LLM as a *proposer* and code as the *grader*: the source text (from the deterministic `PdfplumberParser`) is ground truth, so "did the model invent words?" is a code check, not a matter of trust. Because `broken` rows are already excluded from the picker pool (ADR-0002), a bad LLM output caps yield instead of corrupting the bank — the failure mode we can tolerate.

## Consequences

- `parse_quality` is no longer purely a structural self-assessment; `broken` is also set by the verification checks. CONTEXT.md updated accordingly.
- Residual risk the checks do *not* catch: a swap between two items that occupy the *same* source position run (e.g. reordered subparts whose source offsets tie), or text the LLM lightly paraphrases that still clears the fuzzy threshold. Far narrower than before; bounded by the human `Paper.approve` backstop. The common merge/drop/reorder/option-swap cases are now caught deterministically.
- Ingestion now makes two LLM passes (segment, then tag). Acceptable on an offline batch job where latency is irrelevant; kept as separate seams for testability rather than merged to save a round-trip.
