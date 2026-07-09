# Extraction fidelity rubric (per page)

rubric_version: v1
status: draft — anchors to be tuned in the implementation issue.

You are grading the structured questions extracted from ONE page of a scanned
CBSE question paper. The reference context is the source page (OCR text or a
page rendering description). Deterministic recall/precision against the truth
manifest is computed elsewhere — you grade *faithfulness of what was
extracted*, i.e. "is the extraction the same as the PDF".

Score every dimension 0–5:

- **text_fidelity** — stems, options, and sub-parts reproduce the page text
  verbatim (allowing OCR-safe whitespace); no paraphrase, truncation, or
  translation drift. Bilingual pages must keep the English text exactly.
- **equation_fidelity** — numbers, units, chemical formulae/equations, and
  mathematical expressions are preserved exactly (subscripts, exponents,
  arrows, state symbols).
- **diagram_capture** — questions that depend on a figure are marked as
  diagram-based and carry figure references/boxes; no figure-dependent
  question is presented as pure text.
- **completeness_on_page** — every question (and internal-choice alternative)
  visible on the page appears exactly once; nothing invented, split, or
  merged.

Flags: `paraphrased_text`, `broken_equation`, `missed_diagram`,
`hallucinated_question`, `merged_or_split_question`, `language_mixup`.
