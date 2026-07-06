import type { EditorQuestionRegionBlock } from '@/lib/editor-paper';

export function toRoman(value: number) {
  const numerals = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'];
  return numerals[value - 1] ?? String(value);
}

export function shouldShowInternalChoiceDivider(
  region: EditorQuestionRegionBlock,
) {
  return (
    region.blockType === 'internalChoiceBlock' &&
    (region.internalChoiceOptionIndex ?? 0) > 0
  );
}

export function startsInternalChoiceGroup(region: EditorQuestionRegionBlock) {
  return (
    region.blockType === 'internalChoiceBlock' &&
    (region.internalChoiceOptionIndex ?? 0) === 0
  );
}
