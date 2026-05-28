// Fallback labels used until /api/bank/metadata/ responds.
// Canonical source is the backend Section.choices enum.
export const SECTION_TITLES: Record<string, string> = {
  A: 'Section A — Multiple Choice',
  B: 'Section B — Very Short Answer',
  C: 'Section C — Short Answer',
  D: 'Section D — Long Answer',
  E: 'Section E — Case-based',
};
