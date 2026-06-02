/**
 * Builds the slot-to-question view model for PaperDocumentV1 renderers.
 *
 * This pure mapping is shared by preview and print rendering so browser PDF
 * output follows the same selected question text as the editor surface.
 *
 * @module buildSimplePaperView
 */
import type { DocQuestion, DocSection, DocSlot, PaperDocument } from '@/types';

export interface EditorPaperSlot {
  slot: DocSlot;
  question: DocQuestion | null;
}

export interface EditorPaperSection {
  section: DocSection;
  slots: EditorPaperSlot[];
}

export interface EditorPaperView {
  document: PaperDocument;
  sections: EditorPaperSection[];
}

export function buildSimplePaperView(document: PaperDocument): EditorPaperView {
  const questionById = Object.fromEntries(
    document.questions.map((question) => [question.id, question]),
  );

  return {
    document,
    sections: document.paper.sections.map((section) => ({
      section,
      slots: section.slots.map((slot) => ({
        slot,
        question: slot.selectedQuestionId
          ? questionById[slot.selectedQuestionId]
          : null,
      })),
    })),
  };
}
