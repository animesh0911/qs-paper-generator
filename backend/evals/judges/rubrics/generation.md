# Generated-question quality rubric

rubric_version: v1
status: draft — dimension weights/anchors to be tuned in the implementation issue.

You are grading ONE generated CBSE Class 10 Science question candidate. The
reference context contains the NCERT textbook excerpts the generator was
grounded on. Treat those excerpts as the only source of truth for factual
claims.

Score every dimension 0–5 (0 = unusable, 3 = usable with edits, 5 = a teacher
would ship it unchanged):

- **ncert_fidelity** — the question and its answer are factually correct and
  consistent with the reference excerpts; terminology matches NCERT usage.
- **self_containedness** — a student who cannot see the excerpts can answer;
  no "according to the excerpt/section/table above" phrasing, no dependence on
  data that is not reproduced in the stem.
- **qtype_conformity** — the payload matches its declared qtype and marks:
  MCQ has exactly four options A–D with exactly one clearly correct answer;
  very_short_answer=2, short_answer=3, long_answer=5 marks with appropriate
  scope.
- **answer_correctness** — the bundled answer is right, unambiguous, and for
  MCQ is just the correct option label.
- **difficulty_plausibility** — plausible as a board-exam item for the claimed
  cognitive level; not trivially copyable from the excerpt verbatim.

Flags (emit any that apply): `ungrounded_claim`, `leaked_citation_or_section`,
`wrong_language`, `ambiguous_mcq`, `duplicate_of_excerpt_sentence`.
