/**
 * Schema-aware conversion between canonical Question content and overlay blocks.
 *
 * The converter is the guardrail between transient BlockNote state and
 * paper-local `PaperDocumentV1` overrides. Region identity and original
 * ContentItem metadata travel in block props so unsupported edits fail before
 * canonical state changes.
 *
 * @module questionEditing
 */
import type {
  ChoiceGroup,
  ChoiceOption,
  ContentItem,
  DocQuestion,
  DocQuestionContent,
  KnownQuestionType,
  QuestionType,
  SubQuestion,
} from '@/types';

export type QuestionSemanticBlockType =
  | 'qpgStem'
  | 'qpgPassage'
  | 'qpgAssertion'
  | 'qpgReason'
  | 'qpgOption'
  | 'qpgSubpart'
  | 'qpgChoiceOption'
  | 'qpgImage'
  | 'qpgTable'
  | 'qpgEquation';

export interface QuestionSemanticBlock {
  type: QuestionSemanticBlockType;
  props: {
    regionKey: string;
    region: string;
    label: string;
    groupIndex: number;
    marks: number;
    itemJson: string;
  };
  content: string;
}

export type QuestionContentConversionResult =
  | { ok: true; content: DocQuestionContent }
  | { ok: false; message: string };

const editableRegionsByType = {
  mcq: ['stem', 'options'],
  assertion_reason: ['stem', 'assertion', 'reason', 'options'],
  very_short_answer: ['stem'],
  short_answer: ['stem', 'subparts'],
  long_answer: ['stem', 'subparts'],
  case_based: ['passage', 'stem', 'subparts'],
  internal_choice: ['stem', 'choices'],
  diagram_based: ['stem'],
  table_based: ['stem'],
  custom: [],
} as const satisfies Record<KnownQuestionType, readonly string[]>;

function isKnownQuestionType(type: QuestionType): type is KnownQuestionType {
  return type in editableRegionsByType;
}

export function questionToSemanticBlocks(
  question: DocQuestion,
): QuestionSemanticBlock[] {
  if (
    !isKnownQuestionType(question.type) ||
    editableRegionsByType[question.type].length === 0
  ) {
    return [];
  }

  const blocks: QuestionSemanticBlock[] = [];
  pushItems(blocks, 'passage', question.content.passage);
  pushItems(blocks, 'assertion', question.content.assertion);
  pushItems(blocks, 'reason', question.content.reason);
  pushItems(blocks, 'stem', question.content.stem);
  pushLabelledItems(blocks, 'option', question.content.options);
  pushLabelledItems(blocks, 'subpart', question.content.subparts);
  question.content.choices?.forEach((group, groupIndex) => {
    pushLabelledItems(blocks, 'choice', group.options, groupIndex);
  });
  return blocks;
}

export function semanticBlocksToQuestionContent(
  questionType: QuestionType,
  blocks: QuestionSemanticBlock[],
  originalContent: DocQuestionContent,
): QuestionContentConversionResult {
  if (
    !isKnownQuestionType(questionType) ||
    editableRegionsByType[questionType].length === 0
  ) {
    return {
      ok: false,
      message:
        'This question can be reviewed, but editing is not available for this type yet.',
    };
  }

  const content = structuredClone(originalContent);
  const grouped = groupBlocksByRegionKey(blocks);
  const editableRegions = editableRegionsByType[questionType];

  for (const region of ['stem', 'passage', 'assertion', 'reason'] as const) {
    const regionBlocks = grouped.get(region);
    if (
      editableRegions.some((editableRegion) => editableRegion === region) &&
      (region in originalContent || regionBlocks)
    ) {
      content[region] = regionBlocks?.map(blockToContentItem) ?? [];
    }
  }

  const options = labelledBlocks(blocks, 'option');
  if (questionType === 'mcq' || questionType === 'assertion_reason') {
    content.options = options;
  }

  const subparts = labelledBlocks(blocks, 'subpart');
  if (
    questionType === 'short_answer' ||
    questionType === 'long_answer' ||
    questionType === 'case_based'
  ) {
    content.subparts = subparts;
  }

  if (questionType === 'internal_choice') {
    const choices = choiceBlocks(blocks, originalContent.choices);
    if (!choices.ok) return choices;
    content.choices = choices.choices;
  }

  return validateQuestionContent(questionType, content);
}

function groupBlocksByRegionKey(blocks: QuestionSemanticBlock[]) {
  const grouped = new Map<string, QuestionSemanticBlock[]>();
  for (const block of blocks) {
    const existing = grouped.get(block.props.regionKey) ?? [];
    existing.push(block);
    grouped.set(block.props.regionKey, existing);
  }
  return grouped;
}

function pushItems(
  blocks: QuestionSemanticBlock[],
  region: 'stem' | 'passage' | 'assertion' | 'reason',
  items: ContentItem[] | undefined,
) {
  items?.forEach((item) => {
    blocks.push(toSemanticBlock(region, region, '', -1, undefined, item));
  });
}

function pushLabelledItems(
  blocks: QuestionSemanticBlock[],
  region: 'option' | 'subpart' | 'choice',
  entries: ChoiceOption[] | SubQuestion[] | undefined,
  groupIndex = -1,
) {
  entries?.forEach((entry) => {
    entry.content.forEach((item) => {
      const regionKey =
        region === 'choice'
          ? `choice:${groupIndex}:${entry.label}`
          : `${region}:${entry.label}`;
      blocks.push(
        toSemanticBlock(
          regionKey,
          region,
          entry.label,
          groupIndex,
          entry.marks,
          item,
        ),
      );
    });
  });
}

function toSemanticBlock(
  regionKey: string,
  region: string,
  label: string,
  groupIndex: number,
  marks: number | undefined,
  item: ContentItem,
): QuestionSemanticBlock {
  return {
    type: semanticType(region, item.type),
    props: {
      regionKey,
      region,
      label,
      groupIndex,
      marks: marks ?? -1,
      itemJson: JSON.stringify(item),
    },
    content: item.text ?? item.latex ?? '',
  };
}

function semanticType(
  region: string,
  itemType: string,
): QuestionSemanticBlockType {
  if (itemType === 'image' || itemType === 'image_placeholder') {
    return 'qpgImage';
  }
  if (itemType === 'table') return 'qpgTable';
  if (itemType === 'equation') return 'qpgEquation';
  if (region === 'stem') return 'qpgStem';
  if (region === 'passage') return 'qpgPassage';
  if (region === 'assertion') return 'qpgAssertion';
  if (region === 'reason') return 'qpgReason';
  if (region === 'option') return 'qpgOption';
  if (region === 'subpart') return 'qpgSubpart';
  return 'qpgChoiceOption';
}

function blockToContentItem(block: QuestionSemanticBlock): ContentItem {
  const original = JSON.parse(block.props.itemJson) as ContentItem;
  if (original.type === 'equation') {
    return { ...original, latex: block.content, text: block.content };
  }
  if (original.type === 'table' || original.type.startsWith('image')) {
    return original;
  }
  return { ...original, text: block.content };
}

function labelledBlocks(
  blocks: QuestionSemanticBlock[],
  region: 'option' | 'subpart',
): ChoiceOption[] {
  const matching = blocks.filter((block) => block.props.region === region);
  const labels = [...new Set(matching.map((block) => block.props.label))];
  return labels.map((label) => {
    const first = matching.find((block) => block.props.label === label)!;
    return {
      label,
      ...(first.props.marks >= 0 ? { marks: first.props.marks } : {}),
      content: matching
        .filter((block) => block.props.label === label)
        .map(blockToContentItem),
    };
  });
}

function choiceBlocks(
  blocks: QuestionSemanticBlock[],
  originalChoices: ChoiceGroup[] | undefined,
): { ok: true; choices: ChoiceGroup[] } | { ok: false; message: string } {
  if (!originalChoices) {
    return {
      ok: false,
      message: 'This question no longer has a valid choice group.',
    };
  }

  const matching = blocks.filter((block) => block.props.region === 'choice');
  const choices = originalChoices.map((group, groupIndex) => {
    const groupBlocks = matching.filter(
      (block) => block.props.groupIndex === groupIndex,
    );
    const labels = [...new Set(groupBlocks.map((block) => block.props.label))];
    return {
      ...group,
      options: labels.map((label) => {
        const first = groupBlocks.find((block) => block.props.label === label)!;
        return {
          label,
          ...(first.props.marks >= 0 ? { marks: first.props.marks } : {}),
          content: groupBlocks
            .filter((block) => block.props.label === label)
            .map(blockToContentItem),
        };
      }),
    };
  });
  return { ok: true, choices };
}

function validateQuestionContent(
  questionType: QuestionType,
  content: DocQuestionContent,
): QuestionContentConversionResult {
  if (
    [
      'mcq',
      'very_short_answer',
      'short_answer',
      'long_answer',
      'diagram_based',
      'table_based',
    ].includes(questionType) &&
    !hasContent(content.stem ?? [])
  ) {
    return {
      ok: false,
      message: 'Keep the question text before using this question.',
    };
  }
  if (questionType === 'mcq' && (content.options?.length ?? 0) < 2) {
    return {
      ok: false,
      message: 'Keep at least two options before using this question.',
    };
  }
  if (
    (questionType === 'mcq' || questionType === 'assertion_reason') &&
    content.options?.some((option) => !hasContent(option.content))
  ) {
    return {
      ok: false,
      message: 'Complete or remove empty options before using this question.',
    };
  }
  if (
    questionType === 'assertion_reason' &&
    (!hasContent(content.assertion ?? []) ||
      !hasContent(content.reason ?? []))
  ) {
    return {
      ok: false,
      message: 'Keep both the assertion and reason before using this question.',
    };
  }
  if (
    questionType === 'case_based' &&
    !hasContent(content.passage ?? [])
  ) {
    return {
      ok: false,
      message: 'Keep the case passage before using this question.',
    };
  }
  if (
    questionType === 'case_based' &&
    (content.subparts?.length ?? 0) === 0
  ) {
    return {
      ok: false,
      message: 'Keep at least one subpart before using this question.',
    };
  }
  if (content.subparts?.some((subpart) => !hasContent(subpart.content))) {
    return {
      ok: false,
      message: 'Complete or remove empty subparts before using this question.',
    };
  }
  if (
    questionType === 'internal_choice' &&
    content.choices?.some(
      (group) =>
        group.options.length < 2 ||
        group.options.some((option) => !hasContent(option.content)),
    )
  ) {
    return {
      ok: false,
      message: 'Keep at least two choices in each choice group.',
    };
  }
  return { ok: true, content };
}

function hasContent(items: ContentItem[]) {
  return items.some(
    (item) =>
      Boolean(item.text?.trim()) ||
      Boolean(item.latex?.trim()) ||
      Boolean(item.assetId) ||
      Boolean(item.rows?.length),
  );
}
