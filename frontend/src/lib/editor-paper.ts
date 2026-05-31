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
import type { Block, PartialBlock } from '@blocknote/core';
import type {
  ChoiceOption,
  ContentItem,
  DocQuestion,
  EditableTextBlock,
  PaperDocument,
  SlotOverrides,
  SubQuestion,
} from '@/types';

export type QuestionRegionBlockType =
  | 'questionStemBlock'
  | 'mcqOptionBlock'
  | 'passageBlock'
  | 'subQuestionBlock'
  | 'internalChoiceBlock';

export interface EditorPaperChromeBlock {
  blockId: string;
  blockType: string;
  regionKey: string;
  text: string;
  blockNoteBlocks: PartialBlock[];
  editable: boolean;
  sourceKind: 'paper_chrome';
  editTarget: 'paper_document';
  sourceLocked: false;
}

export interface EditorQuestionRegionBlock {
  blockType: QuestionRegionBlockType;
  regionKey: string;
  text: string;
  displayPrefix: string;
  displaySuffix: string;
  content: ContentItem[];
  blockNoteBlocks: PartialBlock[];
  editable: boolean;
  sourceKind: 'source_question_text';
  editTarget: 'slot_override';
  sourceLocked: true;
  isOverridden: boolean;
}

export interface EditorQuestionContainerBlock {
  blockType: 'questionContainerBlock';
  slotId: string;
  questionId: string | null;
  allowRegionReorder: boolean;
  allowRegionDelete: boolean;
  children: EditorQuestionRegionBlock[];
}

export interface EditorQuestionAlternativeView {
  questionId: string;
  questionText: string;
  marks: number;
  questionType: string;
  chapterNames: string[];
  topicNames: string[];
  difficulty: string;
  cbseRelevance?: string | number;
  sourceName: string;
}

export interface EditorPaperSlotView {
  slotId: string;
  displayNumber: string;
  marksLabel: string;
  questionText: string;
  questionType: string;
  locked: boolean;
  modifiedFromSource: boolean;
  questionBlockTree: EditorQuestionContainerBlock;
  alternateQuestions: EditorQuestionAlternativeView[];
  blockNoteBlocks: PartialBlock[];
}

export interface EditorPaperSectionView {
  sectionId: string;
  title: string;
  titleBlock: EditorPaperChromeBlock;
  subtitle?: string;
  subtitleBlock?: EditorPaperChromeBlock;
  marks: number;
  instructions?: string;
  instructionsBlock?: EditorPaperChromeBlock;
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
  paperChromeBlocks: EditorPaperChromeBlock[];
  headerBlocks: EditorPaperChromeBlock[];
  instructionBlocks: EditorPaperChromeBlock[];
  instructions: string[];
  sections: EditorPaperSectionView[];
  outline: EditorPaperOutlineItem[];
  validationSummary: EditorPaperValidationSummary;
}

export interface BuildEditorPaperViewOptions {
  slotEditsById?: Record<string, SlotOverrides>;
}

export function buildEditorPaperView(
  document: PaperDocument,
  options: BuildEditorPaperViewOptions = {},
): EditorPaperView {
  const questionsById = new Map(
    document.questions.map((question) => [question.questionId, question]),
  );
  const warnings: string[] = [];
  let totalSlots = 0;
  let filledSlots = 0;
  let lockedSlots = 0;

  const sections = document.paper.sections.map((section) => {
    const titleBlock = paperChromeBlock(
      `section:${section.sectionId}:title`,
      'section_heading',
      section.title,
    );
    const subtitleBlock = section.subtitle
      ? paperChromeBlock(
          `section:${section.sectionId}:subtitle`,
          'section_subtitle',
          section.subtitle,
        )
      : undefined;
    const instructionsBlock = section.instructions
      ? paperChromeBlock(
          `section:${section.sectionId}:instructions`,
          'section_instructions',
          section.instructions,
        )
      : undefined;
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

      const slotOverrides =
        options.slotEditsById?.[slot.slotId] ?? slot.overrides;
      const questionBlockTree = question
        ? questionToBlockTree(
            slot.slotId,
            question,
            slotOverrides,
            document.format.questionRegions,
          )
        : emptyQuestionBlockTree(slot.slotId);
      const firstRegionText = questionBlockTree.children[0]?.text;

      return {
        slotId: slot.slotId,
        displayNumber: slot.displayNumber,
        marksLabel: marksLabel(slot.marks),
        questionText:
          firstRegionText ?? question?.rawText ?? 'No question selected.',
        questionType: slot.questionType,
        locked: slot.locked,
        modifiedFromSource: slotOverrides?.modifiedFromSource ?? false,
        questionBlockTree,
        alternateQuestions: slot.alternateQuestionIds.flatMap((questionId) => {
          const alternateQuestion = questionsById.get(questionId);
          return alternateQuestion
            ? [questionToAlternativeView(alternateQuestion)]
            : [];
        }),
        blockNoteBlocks:
          questionBlockTree.children.length > 0
            ? questionBlockTree.children.flatMap(
                (region) => region.blockNoteBlocks,
              )
            : [paragraphBlock('No question selected.')],
      };
    });

    return {
      sectionId: section.sectionId,
      title: section.title,
      titleBlock,
      subtitle: section.subtitle,
      subtitleBlock,
      marks: section.marks,
      instructions: section.instructions,
      instructionsBlock,
      slots,
    };
  });
  const headerBlocks = paperChromeBlocks(document.paper.headerBlocks, 'header');
  const instructionBlocks = paperChromeBlocks(
    document.paper.instructionBlocks,
    'instruction',
  );

  return {
    title: document.paper.title,
    subtitle: document.paper.subtitle,
    paperMeta: [
      document.paper.subtitle,
      `Maximum Marks: ${document.paper.totalMarks}`,
      `Time: ${durationLabel(document.paper.durationMinutes)}`,
    ].filter((value): value is string => Boolean(value)),
    paperChromeBlocks: [
      paperChromeBlock('paper:title', 'paper_title', document.paper.title),
      ...(document.paper.subtitle
        ? [
            paperChromeBlock(
              'paper:subtitle',
              'paper_subtitle',
              document.paper.subtitle,
            ),
          ]
        : []),
      paperChromeBlock(
        'paper:totalMarks',
        'paper_marks',
        String(document.paper.totalMarks),
      ),
      ...headerBlocks,
      ...instructionBlocks,
      ...sections.flatMap((section) => [
        section.titleBlock,
        ...(section.subtitleBlock ? [section.subtitleBlock] : []),
        paperChromeBlock(
          `section:${section.sectionId}:marks`,
          'section_marks',
          String(section.marks),
        ),
        ...(section.instructionsBlock ? [section.instructionsBlock] : []),
      ]),
    ],
    headerBlocks,
    instructionBlocks,
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

function questionToAlternativeView(
  question: DocQuestion,
): EditorQuestionAlternativeView {
  return {
    questionId: question.questionId,
    questionText: question.rawText,
    marks: question.marks,
    questionType: question.questionType,
    chapterNames: question.metadata.chapterNames,
    topicNames: question.metadata.topicNames ?? [],
    difficulty: question.metadata.difficulty,
    cbseRelevance: question.metadata.cbseRelevance,
    sourceName: question.source.sourceName,
  };
}

export function blockNoteBlocksToContentItems(blocks: Block[]): ContentItem[] {
  return blockNoteBlocksToText(blocks)
    .filter((text) => text.length > 0)
    .map((text) => ({ type: 'paragraph', text }));
}

export function blockNoteBlocksToText(blocks: Block[]): string[] {
  return blocks.map((block) => blockContentToText(block.content));
}

function questionToBlockTree(
  slotId: string,
  question: DocQuestion,
  overrides: SlotOverrides | undefined,
  questionRegionRules: PaperDocument['format']['questionRegions'],
): EditorQuestionContainerBlock {
  const children: EditorQuestionRegionBlock[] = [];

  pushRegionBlocks(
    children,
    'passageBlock',
    'passage',
    question.content.passage,
    overrides,
  );
  pushRegionBlocks(
    children,
    'questionStemBlock',
    'assertion',
    question.content.assertion,
    overrides,
    'Assertion: ',
  );
  pushRegionBlocks(
    children,
    'questionStemBlock',
    'reason',
    question.content.reason,
    overrides,
    'Reason: ',
  );
  pushRegionBlocks(
    children,
    'questionStemBlock',
    'stem',
    question.content.stem,
    overrides,
  );
  pushOptionRegions(children, question.content.options, overrides);
  pushSubQuestionRegions(children, question.content.subparts, overrides);
  pushInternalChoiceRegions(children, question.content.choices, overrides);

  if (children.length === 0) {
    children.push(
      regionBlock(
        'questionStemBlock',
        'rawText',
        [{ type: 'paragraph', text: question.rawText }],
        overrides,
      ),
    );
  }

  return {
    blockType: 'questionContainerBlock',
    slotId,
    questionId: question.questionId,
    allowRegionReorder: questionRegionRules.allowRegionReorder,
    allowRegionDelete: questionRegionRules.allowRegionDelete,
    children,
  };
}

function emptyQuestionBlockTree(slotId: string): EditorQuestionContainerBlock {
  return {
    blockType: 'questionContainerBlock',
    slotId,
    questionId: null,
    allowRegionReorder: false,
    allowRegionDelete: false,
    children: [],
  };
}

function pushRegionBlocks(
  blocks: EditorQuestionRegionBlock[],
  blockType: QuestionRegionBlockType,
  regionKey: string,
  items: ContentItem[] | undefined,
  overrides: SlotOverrides | undefined,
  prefix = '',
) {
  if (!items?.length) return;
  blocks.push(regionBlock(blockType, regionKey, items, overrides, prefix));
}

function pushOptionRegions(
  blocks: EditorQuestionRegionBlock[],
  options: ChoiceOption[] | undefined,
  overrides: SlotOverrides | undefined,
) {
  for (const option of options ?? []) {
    blocks.push(
      regionBlock(
        'mcqOptionBlock',
        `option:${option.label}`,
        option.content,
        overrides,
        `(${option.label}) `,
      ),
    );
  }
}

function pushSubQuestionRegions(
  blocks: EditorQuestionRegionBlock[],
  subparts: SubQuestion[] | undefined,
  overrides: SlotOverrides | undefined,
) {
  for (const subpart of subparts ?? []) {
    const marks = subpart.marks ? ` (${marksLabel(subpart.marks)})` : '';
    blocks.push(
      regionBlock(
        'subQuestionBlock',
        `subquestion:${subpart.label}`,
        subpart.content,
        overrides,
        `${subpart.label}. `,
        marks,
      ),
    );
  }
}

function pushInternalChoiceRegions(
  blocks: EditorQuestionRegionBlock[],
  choices: DocQuestion['content']['choices'],
  overrides: SlotOverrides | undefined,
) {
  choices?.forEach((choiceGroup, groupIndex) => {
    choiceGroup.options.forEach((option) => {
      blocks.push(
        regionBlock(
          'internalChoiceBlock',
          `choice:${groupIndex}:${option.label}`,
          option.content,
          overrides,
          `${option.label}. `,
        ),
      );
    });
  });
}

function regionBlock(
  blockType: QuestionRegionBlockType,
  regionKey: string,
  sourceContent: ContentItem[],
  overrides: SlotOverrides | undefined,
  prefix = '',
  suffix = '',
): EditorQuestionRegionBlock {
  const overrideContent = overrides?.regions[regionKey];
  const content = overrideContent ?? sourceContent;
  const text = contentItemsToText(content);

  return {
    blockType,
    regionKey,
    text,
    displayPrefix: prefix,
    displaySuffix: suffix,
    content,
    blockNoteBlocks: [paragraphBlock(text)],
    editable: true,
    sourceKind: 'source_question_text',
    editTarget: 'slot_override',
    sourceLocked: true,
    isOverridden: Boolean(overrideContent),
  };
}

function paperChromeBlocks(
  blocks: EditableTextBlock[] | undefined,
  regionPrefix: string,
): EditorPaperChromeBlock[] {
  return (blocks ?? []).map((block) =>
    paperChromeBlock(
      `${regionPrefix}:${block.blockId}`,
      block.blockType,
      block.text,
      block.editable ?? true,
    ),
  );
}

function paperChromeBlock(
  regionKey: string,
  blockType: string,
  text: string,
  editable = true,
): EditorPaperChromeBlock {
  return {
    blockId: regionKey,
    blockType,
    regionKey,
    text,
    blockNoteBlocks: [paragraphBlock(text)],
    editable,
    sourceKind: 'paper_chrome',
    editTarget: 'paper_document',
    sourceLocked: false,
  };
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

function blockContentToText(content: unknown): string {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';

  return content
    .map((item) => {
      if (
        item &&
        typeof item === 'object' &&
        'text' in item &&
        typeof item.text === 'string'
      ) {
        return item.text;
      }
      return '';
    })
    .filter(Boolean)
    .join('');
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
