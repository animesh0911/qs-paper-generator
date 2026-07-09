# Generated-answer rubric (textbook-grounded)

rubric_version: v1
status: draft — anchors to be tuned in the implementation issue.

You are grading ONE model-generated answer to a question extracted from a
CBSE paper. The reference context contains NCERT textbook excerpts retrieved
for this question's chapter/topic. The textbook is the ground truth: an answer
is correct only insofar as the excerpts (or unambiguous curriculum facts the
excerpts directly imply) support it.

Score every dimension 0–5:

- **correctness** — the answer is scientifically correct for this question per
  the reference excerpts; for MCQ the chosen option is the right one.
- **groundedness** — every substantive claim is supported by the excerpts;
  claims the excerpts cannot support are flagged, not rewarded, even if they
  happen to be true.
- **marks_depth** — depth matches the marks: roughly one distinct scoring
  point per mark, in CBSE marking-scheme style; numericals show formula,
  substitution, and final value with SI unit.
- **scheme_style** — persistable answer text only: no preamble, no
  restatement of the question, notes a diagram/data dependency briefly instead
  of inventing labels or values.

If the reference context is empty (chapter not yet in the corpus), score only
`correctness` and `marks_depth`, set `groundedness` to -1, and emit the flag
`no_textbook_context` — those verdicts are reported separately, never averaged
with grounded ones.

Flags: `unsupported_claim`, `contradicts_textbook`, `invented_labels_or_values`,
`wrong_option`, `no_textbook_context`.
