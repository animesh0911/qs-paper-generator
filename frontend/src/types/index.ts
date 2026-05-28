/**
 * TypeScript mirrors of the backend's response shapes.
 *
 * Source of truth lives in Python:
 * - `PaperDocument` mirrors `PaperDocumentV1` from `backend/papers/document.py`.
 * - `CoverageReport` mirrors `CoverageReport` from `backend/papers/selection.py`.
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

export interface CoverageReport {
  coverage: Record<string, number>;
  cog_coverage: Record<string, number>;
  unfilled: UnfilledSlot[];
}

// Legacy Paper type — kept for PDF download helper
export interface Paper {
  id: number;
  title: string;
  total_marks: number;
  report: CoverageReport;
  created_at: string;
  items: PaperItem[];
}

// PaperDocumentV1 — returned by POST /api/papers/assemble
export interface DocQuestionContent {
  stem: { type: string; text: string }[];
  options?: { label: string; content: { type: string; text: string }[] }[];
}

export interface DocQuestion {
  questionId: string;
  marks: number;
  questionType: string;
  rawText: string;
  content: DocQuestionContent;
  metadata: { chapterNames: string[]; difficulty: string };
}

export interface DocSlot {
  slotId: string;
  displayNumber: string;
  marks: number;
  questionType: string;
  selectedQuestionId: string | null;
  orGroup?: number;
  alternateQuestionIds?: string[];
}

export interface DocSection {
  sectionId: string;
  title: string;
  marks: number;
  instructions: string;
  slots: DocSlot[];
}

export interface DocPaper {
  paperId: string;
  title: string;
  totalMarks: number;
  durationMinutes: number;
  sections: DocSection[];
}

export interface PaperDocument {
  schemaVersion: string;
  paper: DocPaper;
  questions: DocQuestion[];
}

export interface AssembleRequest {
  title?: string;
  preset?: string;
  chapter_slugs?: string[];
  weights?: Record<string, number>;
  difficulty?: 'easy' | 'standard' | 'hard';
}
