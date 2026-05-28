/**
 * TypeScript mirrors of the backend's response shapes.
 *
 * Source of truth lives in Python:
 * - `Chapter`, `Question`, `Paper`, `PaperItem` mirror DRF serializers in
 *   `backend/bank/serializers.py` and `backend/papers/serializers.py`.
 * - `SelectionReport`, `UnfilledSlot` mirror
 *   `backend/papers/selection.py::SelectionReport`.
 * - `AssembleRequest` mirrors `AssembleRequestSerializer` input.
 *
 * If you change any of those Python files, update this module in the same PR.
 *
 * @module types
 */
export interface Chapter {
  id: number;
  slug: string;
  name: string;
  order: number;
}

export interface Question {
  id: number;
  section: string;
  qtype: string;
  marks: number;
  chapter: Chapter | null;
  cognitive_level: string;
  text: string;
  options: { label: string; text: string }[];
  // Only present on dedicated answer-key endpoints; the default question
  // serializer omits it so paper-assemble responses do not leak the key.
  answer?: string;
}

export interface PaperItem {
  order: number;
  section: string;
  question: Question;
}

export interface UnfilledSlot {
  slot_index: number;
  section: string;
  qtype: string;
  marks: number;
  reason: string;
}

export interface SelectionReport {
  coverage: Record<string, number>;
  cog_coverage: Record<string, number>;
  unfilled: UnfilledSlot[];
}

export interface Paper {
  id: number;
  title: string;
  total_marks: number;
  report: SelectionReport;
  created_at: string;
  items: PaperItem[];
}

export interface AssembleRequest {
  title?: string;
  preset?: string;
  chapter_slugs?: string[];
  weights?: Record<string, number>;
  difficulty?: 'easy' | 'standard' | 'hard';
}
