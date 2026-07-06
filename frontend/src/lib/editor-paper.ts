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
  DocSlot,
  DocQuestion,
  EditableTextBlock,
  PaperDocument,
  SlotEditCapabilities,
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
  editCapabilities: {
    text: boolean;
    delete: boolean;
    reorder: boolean;
  };
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
  internalChoiceGroupIndex?: number;
  internalChoiceOptionIndex?: number;
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
  questionBlockTree: EditorQuestionContainerBlock;
  marks: number;
  questionType: string;
  chapterNames: string[];
  topicNames: string[];
  difficulty: string;
  cbseRelevance?: string | number;
  sourceName: string;
}

interface EditorSlotCapabilities {
  editText: boolean;
  editMarks: boolean;
  swap: boolean;
  lock: boolean;
  reorder: boolean;
}

export interface EditorPaperSlotView {
  slotId: string;
  displayNumber: string;
  marksLabel: string;
  showMarksLabel: boolean;
  questionText: string;
  questionType: string;
  internalChoicePrefix?: string;
  locked: boolean;
  editCapabilities: EditorSlotCapabilities;
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
  logicalSlotCount: number;
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
  chromeBlocks: EditorPaperChromeBlock[];
  instructionBlocks: EditorPaperChromeBlock[];
  instructions: string[];
  sections: EditorPaperSectionView[];
  outline: EditorPaperOutlineItem[];
  validationSummary: EditorPaperValidationSummary;
}

export interface BuildEditorPaperViewOptions {
  slotEditsById?: Record<string, SlotOverrides>;
  alternativesIntentBySlotId?: Record<string, EditorAlternativesIntent>;
}

export type EditorAlternativesIntent = 'swap' | 'topic' | 'easier' | 'harder';

interface QuestionRegionRules {
  allowRegionReorder: boolean;
  allowRegionDelete: boolean;
}

const defaultQuestionRegionRules: QuestionRegionRules = {
  allowRegionReorder: false,
  allowRegionDelete: false,
};

export function buildEditorPaperView(
  document: PaperDocument,
  options: BuildEditorPaperViewOptions = {},
): EditorPaperView {
  const questionsById = new Map(
    document.questions.map((question) => [question.id, question]),
  );
  const warnings: string[] = [];
  let totalSlots = 0;
  let filledSlots = 0;
  let lockedSlots = 0;

  const sections = document.paper.sections.map((section) => {
    const logicalSlotCount = countLogicalSlots(section.slots);
    totalSlots += logicalSlotCount;
    filledSlots += countFilledLogicalSlots(section.slots);
    lockedSlots += countLockedLogicalSlots(section.slots);
    const titleBlock = paperChromeBlock(
      `section:${section.id}:title`,
      'section_heading',
      section.title,
    );
    const subtitleBlock = section.subtitle
      ? paperChromeBlock(
          `section:${section.id}:subtitle`,
          'section_subtitle',
          section.subtitle,
        )
      : undefined;
    const instructionsBlock = section.instructions
      ? paperChromeBlock(
          `section:${section.id}:instructions`,
          'section_instructions',
          section.instructions,
        )
      : undefined;
    const slotNumberCounts = countSlotNumbers(section.slots);
    const seenSlotNumbers = new Map<string, number>();
    const slots = section.slots.map((slot) => {
      const slotNumberSeen = (seenSlotNumbers.get(slot.number) ?? 0) + 1;
      seenSlotNumbers.set(slot.number, slotNumberSeen);

      const question = slot.selectedQuestionId
        ? questionsById.get(slot.selectedQuestionId)
        : undefined;

      if (!question) {
        warnings.push(
          `${slotWarningLabel(slot, slotNumberSeen, slotNumberCounts.get(slot.number) ?? 1)} has no selected question.`,
        );
      }

      const slotOverrides = options.slotEditsById?.[slot.id] ?? slot.overrides;
      const editCapabilities = slotEditCapabilities(slot.can);
      const questionBlockTree = question
        ? questionToBlockTree(
            slot.id,
            question,
            slotOverrides,
            defaultQuestionRegionRules,
          )
        : emptyQuestionBlockTree(slot.id);
      const firstRegionText = questionBlockTree.children[0]?.text;

      return {
        slotId: slot.id,
        displayNumber: slot.number,
        marksLabel: marksLabel(slot.marks),
        showMarksLabel: question
          ? !questionCarriesMarks(question, questionBlockTree, slot.marks)
          : true,
        questionText:
          firstRegionText ?? question?.rawText ?? 'No question selected.',
        questionType: slot.type,
        internalChoicePrefix:
          slot.orGroup !== undefined && slotNumberSeen > 1 && question
            ? 'OR'
            : undefined,
        locked: slot.locked,
        editCapabilities,
        modifiedFromSource: slotOverrides?.modified ?? false,
        questionBlockTree,
        alternateQuestions: filterAlternatives(
          question,
          slot.alternateQuestionIds.flatMap((questionId) => {
            const alternateQuestion = questionsById.get(questionId);
            return alternateQuestion ? [alternateQuestion] : [];
          }),
          options.alternativesIntentBySlotId?.[slot.id] ?? 'swap',
        ).map((alternativeQuestion) =>
          questionToAlternativeView(
            alternativeQuestion,
            defaultQuestionRegionRules,
          ),
        ),
        blockNoteBlocks:
          questionBlockTree.children.length > 0
            ? questionBlockTree.children.flatMap(
                (region) => region.blockNoteBlocks,
              )
            : [paragraphBlock('No question selected.')],
      };
    });

    return {
      sectionId: section.id,
      title: section.title,
      titleBlock,
      subtitle: section.subtitle,
      subtitleBlock,
      marks: section.marks,
      instructions: section.instructions,
      instructionsBlock,
      slots,
      logicalSlotCount,
    };
  });
  const chromeBlocks = paperChromeBlocks(document.paper.chromeBlocks, 'chrome');
  const instructionBlocks = paperChromeBlocks(
    document.paper.instructionBlocks,
    'instruction',
  );
  warnings.push(...markTotalWarnings(document));

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
      ...chromeBlocks,
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
    chromeBlocks,
    instructionBlocks,
    instructions:
      document.paper.instructionBlocks?.map((block) => block.text) ?? [],
    sections,
    outline: sections.map((section) => ({
      sectionId: section.sectionId,
      title: section.title,
      slotCount: section.logicalSlotCount,
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

function countSlotNumbers(slots: DocSlot[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const slot of slots) {
    counts.set(slot.number, (counts.get(slot.number) ?? 0) + 1);
  }
  return counts;
}

function countLogicalSlots(slots: DocSlot[]): number {
  return logicalSlotGroups(slots).size;
}

function countFilledLogicalSlots(slots: DocSlot[]): number {
  return countLogicalSlotsWhere(slots, (group) =>
    group.every((slot) => Boolean(slot.selectedQuestionId)),
  );
}

function countLockedLogicalSlots(slots: DocSlot[]): number {
  return countLogicalSlotsWhere(slots, (group) =>
    group.some((slot) => slot.locked),
  );
}

function countLogicalSlotsWhere(
  slots: DocSlot[],
  predicate: (group: DocSlot[]) => boolean,
): number {
  return Array.from(logicalSlotGroups(slots).values()).filter(predicate).length;
}

function logicalSlotGroups(slots: DocSlot[]): Map<string, DocSlot[]> {
  const groups = new Map<string, DocSlot[]>();
  for (const slot of slots) {
    const key = logicalSlotKey(slot);
    groups.set(key, [...(groups.get(key) ?? []), slot]);
  }
  return groups;
}

function logicalSlotKey(slot: DocSlot): string {
  return slot.orGroup === undefined ? `slot:${slot.id}` : `or:${slot.orGroup}`;
}

function slotWarningLabel(
  slot: DocSlot,
  occurrence: number,
  totalOccurrences: number,
): string {
  if (totalOccurrences <= 1) return `Slot ${slot.number}`;
  const labelKind = slot.orGroup === undefined ? 'copy' : 'choice';
  return `Slot ${slot.number} (${labelKind} ${occurrence} of ${totalOccurrences})`;
}

function markTotalWarnings(document: PaperDocument) {
  const warnings: string[] = [];
  const paperSlotMarks = document.paper.sections.reduce(
    (sum, section) => sum + effectiveSectionSlotMarks(section.slots),
    0,
  );

  if (paperSlotMarks !== document.paper.totalMarks) {
    warnings.push(
      `Paper total is ${document.paper.totalMarks} marks, but Slot marks total ${paperSlotMarks}.`,
    );
  }

  for (const section of document.paper.sections) {
    const sectionSlotMarks = effectiveSectionSlotMarks(section.slots);
    if (sectionSlotMarks !== section.marks) {
      warnings.push(
        `${section.title} is labelled ${section.marks} marks, but its Slots total ${sectionSlotMarks}.`,
      );
    }
  }

  return warnings;
}

function effectiveSectionSlotMarks(
  slots: { marks: number; orGroup?: number }[],
) {
  let total = 0;
  const orGroupMarks = new Map<number, number>();

  for (const slot of slots) {
    if (slot.orGroup === undefined) {
      total += slot.marks;
      continue;
    }

    orGroupMarks.set(
      slot.orGroup,
      Math.max(orGroupMarks.get(slot.orGroup) ?? 0, slot.marks),
    );
  }

  for (const marks of orGroupMarks.values()) {
    total += marks;
  }

  return total;
}

function filterAlternatives(
  currentQuestion: DocQuestion | undefined,
  alternatives: DocQuestion[],
  intent: EditorAlternativesIntent,
) {
  const candidates = currentQuestion
    ? alternatives.filter((question) => question.id !== currentQuestion.id)
    : alternatives;

  if (!currentQuestion || intent === 'swap') return candidates;

  if (intent === 'topic') {
    const topicMatches = candidates.filter((candidate) =>
      overlaps(
        currentQuestion.metadata.topicNames ?? [],
        candidate.metadata.topicNames ?? [],
      ),
    );
    if (topicMatches.length > 0) return topicMatches;

    return candidates.filter((candidate) =>
      overlaps(
        currentQuestion.metadata.chapterNames,
        candidate.metadata.chapterNames,
      ),
    );
  }

  const currentDifficulty = difficultyRank(currentQuestion.metadata.difficulty);
  if (currentDifficulty === undefined) return [];

  return candidates.filter((candidate) => {
    const candidateDifficulty = difficultyRank(candidate.metadata.difficulty);
    if (candidateDifficulty === undefined) return false;
    return intent === 'easier'
      ? candidateDifficulty < currentDifficulty
      : candidateDifficulty > currentDifficulty;
  });
}

function overlaps(left: string[], right: string[]) {
  const normalizedRight = new Set(right.map(normalizeMetadataToken));
  return left.some((value) =>
    normalizedRight.has(normalizeMetadataToken(value)),
  );
}

function normalizeMetadataToken(value: string) {
  return value.trim().toLowerCase();
}

function difficultyRank(difficulty: string) {
  const normalized = difficulty.trim().toLowerCase();
  if (normalized === 'easy') return 1;
  if (normalized === 'medium' || normalized === 'standard') return 2;
  if (normalized === 'hard') return 3;
  return undefined;
}

function questionToAlternativeView(
  question: DocQuestion,
  questionRegionRules: QuestionRegionRules,
): EditorQuestionAlternativeView {
  return {
    questionId: question.id,
    questionText: question.rawText,
    questionBlockTree: questionToBlockTree(
      `alternative:${question.id}`,
      question,
      undefined,
      questionRegionRules,
    ),
    marks: question.defaultMarks,
    questionType: question.type,
    chapterNames: question.metadata.chapterNames,
    topicNames: question.metadata.topicNames ?? [],
    difficulty: question.metadata.difficulty,
    cbseRelevance: question.metadata.cbseRelevance,
    sourceName: question.source.name,
  };
}

export function blockNoteBlocksToContentItems(blocks: Block[]): ContentItem[] {
  return blocks.flatMap((block): ContentItem[] => {
    if (block.type === 'table') {
      const rows = blockNoteTableRows(block.content);
      return rows.length > 0 ? [{ type: 'table', rows }] : [];
    }

    const text = blockContentToText(block.content);
    return text.length > 0 ? [{ type: 'paragraph', text }] : [];
  });
}

export function blockNoteBlocksToText(blocks: Block[]): string[] {
  return blocks.map((block) => blockContentToText(block.content));
}

function questionToBlockTree(
  slotId: string,
  question: DocQuestion,
  overrides: SlotOverrides | undefined,
  questionRegionRules: QuestionRegionRules,
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
    trimRegionBeforeStructuredSubparts(
      question.content.stem,
      question.content.subparts,
    ),
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
    questionId: question.id,
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

function trimRegionBeforeStructuredSubparts(
  items: ContentItem[] | undefined,
  subparts: SubQuestion[] | undefined,
): ContentItem[] | undefined {
  const firstLabel = subparts?.[0]?.label;
  if (!firstLabel || !items?.length) return items;

  const markerPattern = new RegExp(
    String.raw`(?:^|\s)(?:\(${escapeRegExp(firstLabel)}\)|${escapeRegExp(firstLabel)}\.)\s+`,
    'i',
  );
  const nextItems: ContentItem[] = [];

  for (const item of items) {
    if (!item.text) {
      nextItems.push(item);
      continue;
    }

    const marker = item.text.search(markerPattern);
    if (marker === -1) {
      nextItems.push(item);
      continue;
    }

    const text = item.text.slice(0, marker).trim();
    if (text) nextItems.push({ ...item, text });
    break;
  }

  return nextItems.length > 0 ? nextItems : items;
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
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
    choiceGroup.options.forEach((option, optionIndex) => {
      blocks.push(
        regionBlock(
          'internalChoiceBlock',
          // Include the option index: a choice group may legitimately repeat an
          // option label (ingested case-based questions sometimes label two
          // options the same, e.g. both "c"), and the region key must stay
          // unique so React keys don't collide and per-option edits aren't
          // applied to the wrong option.
          `choice:${groupIndex}:${optionIndex}:${option.label}`,
          option.content,
          overrides,
          '',
          '',
          {
            internalChoiceGroupIndex: groupIndex,
            internalChoiceOptionIndex: optionIndex,
          },
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
  metadata: Pick<
    EditorQuestionRegionBlock,
    'internalChoiceGroupIndex' | 'internalChoiceOptionIndex'
  > = {},
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
    ...metadata,
    content,
    blockNoteBlocks: contentItemsToBlockNoteBlocks(content),
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
      `${regionPrefix}:${block.id}`,
      block.role,
      block.text,
      block.can,
    ),
  );
}

function paperChromeBlock(
  regionKey: string,
  blockType: string,
  text: string,
  editCapabilities?: EditableTextBlock['can'],
): EditorPaperChromeBlock {
  const editable = editCapabilities?.editText ?? true;

  return {
    blockId: regionKey,
    blockType,
    regionKey,
    text,
    blockNoteBlocks: [paragraphBlock(text)],
    editable,
    editCapabilities: {
      text: editCapabilities?.editText ?? editable,
      delete: editCapabilities?.delete ?? false,
      reorder: editCapabilities?.reorder ?? false,
    },
    sourceKind: 'paper_chrome',
    editTarget: 'paper_document',
    sourceLocked: false,
  };
}

function slotEditCapabilities(
  can: SlotEditCapabilities | undefined,
): EditorSlotCapabilities {
  return {
    editText: can?.editText ?? true,
    editMarks: can?.editMarks ?? true,
    swap: can?.swap ?? true,
    lock: can?.lock ?? true,
    reorder: can?.reorder ?? true,
  };
}

function questionCarriesMarks(
  question: DocQuestion,
  questionBlockTree: EditorQuestionContainerBlock,
  marks: number,
) {
  if (questionBlockTree.children.some((block) => block.displaySuffix)) {
    return true;
  }

  return [
    question.rawText,
    ...questionBlockTree.children.map((block) => block.text),
  ]
    .filter(Boolean)
    .some((text) => textContainsMarksLabel(text, marks));
}

function textContainsMarksLabel(text: string, marks: number) {
  const bracketedLabel = new RegExp(
    String.raw`(?:\(|\[)\s*${marks}\s*(?:marks?|m)\s*(?:\)|\])`,
    'i',
  );
  const trailingLabel = new RegExp(
    String.raw`(?:^|\s)${marks}\s*(?:marks?|m)\s*$`,
    'i',
  );

  return bracketedLabel.test(text) || trailingLabel.test(text);
}

export function contentItemsToText(items: ContentItem[]): string {
  return items.map(contentItemToText).filter(Boolean).join('\n');
}

/**
 * Full printable question text for a Slot, for the per-question copy control.
 *
 * Joins the question's source regions (display prefix + region text) and
 * deliberately omits editor-only chrome — marks labels (`displaySuffix`) and
 * the question-type badge — so teachers copy the question as printed, not the
 * editor's metadata.
 */
export function editorSlotClipboardText(slot: EditorPaperSlotView): string {
  const lines: string[] = [];

  for (const region of slot.questionBlockTree.children) {
    if (
      region.blockType === 'internalChoiceBlock' &&
      (region.internalChoiceOptionIndex ?? 0) > 0
    ) {
      lines.push('OR');
    } else if (
      region.blockType === 'internalChoiceBlock' &&
      (region.internalChoiceGroupIndex ?? 0) > 0 &&
      (region.internalChoiceOptionIndex ?? 0) === 0
    ) {
      lines.push('');
    }

    const line = [region.displayPrefix, region.text]
      .map((part) => part.trim())
      .filter(Boolean)
      .join(' ');
    if (line) lines.push(line);
  }

  return lines.join('\n').trim();
}

export function contentItemToText(item: ContentItem): string {
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

function contentItemsToBlockNoteBlocks(items: ContentItem[]): PartialBlock[] {
  const blocks = items.map(contentItemToBlockNoteBlock);

  return blocks.length > 0 ? blocks : [paragraphBlock('')];
}

function contentItemToBlockNoteBlock(item: ContentItem): PartialBlock {
  if (item.type === 'table' && item.rows) {
    return {
      type: 'table',
      content: {
        type: 'tableContent',
        rows: item.rows.map((row) => ({ cells: row })),
      },
    };
  }

  return paragraphBlock(contentItemToText(item));
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

function blockNoteTableRows(content: unknown): string[][] {
  if (
    !content ||
    typeof content !== 'object' ||
    !('type' in content) ||
    content.type !== 'tableContent' ||
    !('rows' in content) ||
    !Array.isArray(content.rows)
  ) {
    return [];
  }

  return content.rows
    .map((row) => {
      if (
        !row ||
        typeof row !== 'object' ||
        !('cells' in row) ||
        !Array.isArray(row.cells)
      ) {
        return [];
      }

      return row.cells.map(cellToText);
    })
    .filter((row) => row.length > 0);
}

function cellToText(cell: unknown): string {
  if (typeof cell === 'string') return cell;
  if (!Array.isArray(cell)) return '';

  return cell
    .map((item) => {
      if (typeof item === 'string') return item;
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
