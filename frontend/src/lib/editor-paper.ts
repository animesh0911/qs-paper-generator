/**
 * PaperDocumentV1 to editor shell view-model mapper.
 *
 * React pages use this module to keep display decisions close to the contract
 * and out of JSX branching. It builds the paper canvas rows, BlockNote starter
 * blocks, left-rail outline, and validation summary from the normalized
 * document shape.
 *
 * Patterns:
 * - Missing selected questions render as warnings instead of throwing.
 * - BlockNote blocks are display starters; `PaperDocumentV1` stays canonical.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `src/types`.
 *
 * @module editorPaper
 */
import type { PartialBlock } from '@blocknote/core';
import type {
  ChoiceOption,
  ContentItem,
  DocQuestion,
  PaperDocument,
  SubQuestion,
} from '@/types';

export interface EditorPaperSlotView {
  slotId: string;
  displayNumber: string;
  marksLabel: string;
  questionText: string;
  questionType: string;
  locked: boolean;
  modifiedFromSource: boolean;
  blockNoteBlocks: PartialBlock[];
}

export interface EditorPaperSectionView {
  sectionId: string;
  title: string;
  subtitle?: string;
  marks: number;
  instructions?: string;
  slots: EditorPaperSlotView[];
}

export interface EditorPaperOutlineItem {
  sectionId: string;
  title: string;
  slotCount: number;
  marks: number;
}

export interface EditorPaperValidationSummary {
  totalSlots: number;
  filledSlots: number;
  lockedSlots: number;
  warnings: string[];
}

export interface EditorPaperView {
  title: string;
  subtitle?: string;
  paperMeta: string[];
  instructions: string[];
  sections: EditorPaperSectionView[];
  outline: EditorPaperOutlineItem[];
  validationSummary: EditorPaperValidationSummary;
}

export function buildEditorPaperView(document: PaperDocument): EditorPaperView {
  const questionsById = new Map(
    document.questions.map((question) => [question.questionId, question]),
  );
  const warnings: string[] = [];
  let totalSlots = 0;
  let filledSlots = 0;
  let lockedSlots = 0;

  const sections = document.paper.sections.map((section) => {
    const slots = section.slots.map((slot) => {
      totalSlots += 1;
      if (slot.locked) lockedSlots += 1;

      const question = slot.selectedQuestionId
        ? questionsById.get(slot.selectedQuestionId)
        : undefined;

      if (question) {
        filledSlots += 1;
      } else {
        warnings.push(`Slot ${slot.displayNumber} has no selected question.`);
      }

      return {
        slotId: slot.slotId,
        displayNumber: slot.displayNumber,
        marksLabel: marksLabel(slot.marks),
        questionText: question?.rawText ?? 'No question selected.',
        questionType: slot.questionType,
        locked: slot.locked,
        modifiedFromSource: slot.overrides?.modifiedFromSource ?? false,
        blockNoteBlocks: question
          ? questionToBlockNoteBlocks(question)
          : [paragraphBlock('No question selected.')],
      };
    });

    return {
      sectionId: section.sectionId,
      title: section.title,
      subtitle: section.subtitle,
      marks: section.marks,
      instructions: section.instructions,
      slots,
    };
  });

  return {
    title: document.paper.title,
    subtitle: document.paper.subtitle,
    paperMeta: [
      document.paper.subtitle,
      `Maximum Marks: ${document.paper.totalMarks}`,
      `Time: ${durationLabel(document.paper.durationMinutes)}`,
    ].filter((value): value is string => Boolean(value)),
    instructions:
      document.paper.instructionBlocks?.map((block) => block.text) ?? [],
    sections,
    outline: sections.map((section) => ({
      sectionId: section.sectionId,
      title: section.title,
      slotCount: section.slots.length,
      marks: section.marks,
    })),
    validationSummary: {
      totalSlots,
      filledSlots,
      lockedSlots,
      warnings,
    },
  };
}

function questionToBlockNoteBlocks(question: DocQuestion): PartialBlock[] {
  const blocks: PartialBlock[] = [];
  pushContentBlocks(blocks, question.content.passage);
  pushContentBlocks(blocks, question.content.assertion, 'Assertion: ');
  pushContentBlocks(blocks, question.content.reason, 'Reason: ');
  pushContentBlocks(blocks, question.content.stem);
  pushOptionBlocks(blocks, question.content.options);
  pushSubQuestionBlocks(blocks, question.content.subparts);

  for (const choiceGroup of question.content.choices ?? []) {
    blocks.push(paragraphBlock('OR'));
    choiceGroup.options.forEach((option) => {
      blocks.push(
        paragraphBlock(`${option.label}. ${contentItemsToText(option.content)}`),
      );
    });
  }

  return blocks.length > 0 ? blocks : [paragraphBlock(question.rawText)];
}

function pushContentBlocks(
  blocks: PartialBlock[],
  items: ContentItem[] | undefined,
  prefix = '',
) {
  for (const item of items ?? []) {
    blocks.push(paragraphBlock(`${prefix}${contentItemToText(item)}`));
  }
}

function pushOptionBlocks(
  blocks: PartialBlock[],
  options: ChoiceOption[] | undefined,
) {
  for (const option of options ?? []) {
    blocks.push(paragraphBlock(`(${option.label}) ${contentItemsToText(option.content)}`));
  }
}

function pushSubQuestionBlocks(
  blocks: PartialBlock[],
  subparts: SubQuestion[] | undefined,
) {
  for (const subpart of subparts ?? []) {
    const marks = subpart.marks ? ` (${marksLabel(subpart.marks)})` : '';
    blocks.push(
      paragraphBlock(`${subpart.label}. ${contentItemsToText(subpart.content)}${marks}`),
    );
  }
}

function contentItemsToText(items: ContentItem[]): string {
  return items.map(contentItemToText).filter(Boolean).join(' ');
}

function contentItemToText(item: ContentItem): string {
  if (item.text) return item.text;
  if (item.latex) return item.latex;
  if (item.type === 'table' && item.rows) {
    return item.rows.map((row) => row.join(' | ')).join(' / ');
  }
  if (item.type === 'image_placeholder') {
    return item.caption ? `[Diagram: ${item.caption}]` : '[Diagram]';
  }
  return item.caption ?? '';
}

function paragraphBlock(content: string): PartialBlock {
  return {
    type: 'paragraph',
    content,
  };
}

function marksLabel(marks: number): string {
  return `${marks} mark${marks === 1 ? '' : 's'}`;
}

function durationLabel(durationMinutes: number): string {
  if (durationMinutes % 60 === 0) {
    const hours = durationMinutes / 60;
    return `${hours} hour${hours === 1 ? '' : 's'}`;
  }
  return `${durationMinutes} minutes`;
}
