/**
 * Read-only rendering of a question's structured content as stacked regions —
 * the same layout the editor shows for a locked (non-editable) question.
 *
 * The editor splits a question into regions (passage, assertion/reason, stem,
 * MCQ options, subparts, internal choices), each with a display prefix/suffix
 * and KaTeX-rendered content. This component reproduces that ordering, prefix
 * convention, and markup so the Question Bank presents questions identically to
 * the editor — without the BlockNote editing machinery.
 *
 * @module QuestionRegions
 */
import { MathContent } from '@/components/math/math-content.component';
import type { ContentItem, DocQuestionContent } from '@/types';

interface QuestionRegion {
  regionKey: string;
  prefix: string;
  suffix: string;
  content: ContentItem[];
}

function marksLabel(marks: number): string {
  return `${marks} mark${marks === 1 ? '' : 's'}`;
}

/**
 * Flatten structured question content into the ordered region list the editor
 * renders. Mirrors `questionToBlockTree` in `lib/editor-paper.ts`.
 */
function contentToRegions(
  content: DocQuestionContent | undefined,
  fallbackText: string,
  fallbackOptions: { label: string; text: string }[],
): QuestionRegion[] {
  const regions: QuestionRegion[] = [];
  const push = (
    regionKey: string,
    items: ContentItem[] | undefined,
    prefix = '',
    suffix = '',
  ) => {
    if (!items?.length) return;
    regions.push({ regionKey, prefix, suffix, content: items });
  };

  push('passage', content?.passage);
  push('assertion', content?.assertion, 'Assertion: ');
  push('reason', content?.reason, 'Reason: ');
  push('stem', content?.stem);

  // Prefer structured options; fall back to the flat {label,text} list for
  // questions ingested before structured content carried options.
  const structuredOptions = content?.options ?? [];
  if (structuredOptions.length > 0) {
    for (const option of structuredOptions) {
      push(`option:${option.label}`, option.content, `(${option.label}) `);
    }
  } else {
    for (const option of fallbackOptions) {
      push(
        `option:${option.label}`,
        option.text ? [{ type: 'paragraph', text: option.text }] : undefined,
        option.label ? `(${option.label}) ` : '',
      );
    }
  }

  for (const subpart of content?.subparts ?? []) {
    const suffix = subpart.marks ? ` (${marksLabel(subpart.marks)})` : '';
    push(
      `subquestion:${subpart.label}`,
      subpart.content,
      `${subpart.label}. `,
      suffix,
    );
  }

  content?.choices?.forEach((choiceGroup, groupIndex) => {
    choiceGroup.options.forEach((option, optionIndex) => {
      push(
        `choice:${groupIndex}:${optionIndex}:${option.label}`,
        option.content,
        `${option.label}. `,
      );
    });
  });

  if (regions.length === 0 && fallbackText) {
    regions.push({
      regionKey: 'rawText',
      prefix: '',
      suffix: '',
      content: [{ type: 'paragraph', text: fallbackText }],
    });
  }

  return regions;
}

export function QuestionRegions({
  content,
  fallbackText = '',
  fallbackOptions = [],
}: {
  content: DocQuestionContent | undefined;
  fallbackText?: string;
  fallbackOptions?: { label: string; text: string }[];
}) {
  const regions = contentToRegions(content, fallbackText, fallbackOptions);

  return (
    <div className="qpg-question-readonly space-y-1">
      {regions.map((region) => (
        <div
          key={region.regionKey}
          className="qpg-question-region flex items-start gap-1"
        >
          {region.prefix && (
            <span className="qpg-question-region-prefix select-none font-medium">
              {region.prefix}
            </span>
          )}
          <div className="min-w-0 flex-1">
            <div className="qpg-question-blocknote qpg-question-region-text">
              <MathContent items={region.content} />
            </div>
          </div>
          {region.suffix && (
            <span className="qpg-question-region-suffix select-none">
              {region.suffix}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
