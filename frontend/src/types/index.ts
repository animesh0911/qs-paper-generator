/**
 * TypeScript mirrors of the backend's response shapes.
 *
 * Source of truth lives in Python:
 * - `PaperDocument` mirrors `PaperDocumentV1` from `backend/papers/document.py`.
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
