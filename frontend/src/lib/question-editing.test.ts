/**
 * Intent tests for schema-aware Question editing.
 *
 * The focused overlay is allowed to change paper-local Question content only
 * when semantic blocks can be mapped back without losing region identity.
 *
 * @module questionEditingTests
 */
import { describe, expect, it } from 'vitest';
import type { DocQuestion } from '@/types';
import {
  questionToSemanticBlocks,
  semanticBlocksToQuestionContent,
} from './question-editing';

function question(
  type: DocQuestion['type'],
  content: DocQuestion['content'],
): DocQuestion {
  return {
    id: `q_${type}`,
    language: 'en',
    defaultMarks: 1,
    type,
    rawText: 'Source question',
    content,
    metadata: {
      classLevel: '10',
      subject: 'Science',
      chapterNames: ['Test chapter'],
      difficulty: 'medium',
    },
    source: {
      type: 'question_bank',
      name: 'Test source',
    },
  };
}

describe('schema-aware Question editing', () => {
  it('round-trips an MCQ without flattening its option collection', () => {
    const source = question('mcq', {
      stem: [{ type: 'paragraph', text: 'Choose the conductor.' }],
      options: [
        {
          label: 'A',
          content: [{ type: 'paragraph', text: 'Copper' }],
        },
        {
          label: 'B',
          content: [{ type: 'paragraph', text: 'Rubber' }],
        },
      ],
    });

    const result = semanticBlocksToQuestionContent(
      source.type,
      questionToSemanticBlocks(source),
      source.content,
    );

    expect(result).toEqual({ ok: true, content: source.content });
  });

  it('applies option add, remove, and reorder as one canonical collection edit', () => {
    const source = question('mcq', {
      stem: [{ type: 'paragraph', text: 'Choose the conductor.' }],
      options: [
        {
          label: 'A',
          content: [{ type: 'paragraph', text: 'Copper' }],
        },
        {
          label: 'B',
          content: [{ type: 'paragraph', text: 'Rubber' }],
        },
      ],
    });
    const blocks = questionToSemanticBlocks(source);
    const stem = blocks.filter((block) => block.props.region === 'stem');
    const optionA = blocks.find((block) => block.props.label === 'A')!;
    const optionC = {
      ...optionA,
      props: {
        ...optionA.props,
        regionKey: 'option:C',
        label: 'C',
        itemJson: JSON.stringify({ type: 'paragraph', text: 'Graphite' }),
      },
      content: 'Graphite',
    };

    const result = semanticBlocksToQuestionContent(
      source.type,
      [...stem, optionC, optionA],
      source.content,
    );

    expect(result).toEqual({
      ok: true,
      content: {
        stem: source.content.stem,
        options: [
          {
            label: 'C',
            content: [{ type: 'paragraph', text: 'Graphite' }],
          },
          {
            label: 'A',
            content: [{ type: 'paragraph', text: 'Copper' }],
          },
        ],
      },
    });
  });

  it('rejects an empty added option before paper state changes', () => {
    const source = question('mcq', {
      stem: [{ type: 'paragraph', text: 'Choose one.' }],
      options: [
        {
          label: 'A',
          content: [{ type: 'paragraph', text: 'One' }],
        },
        {
          label: 'B',
          content: [{ type: 'paragraph', text: 'Two' }],
        },
      ],
    });
    const blocks = questionToSemanticBlocks(source);
    blocks.push({
      ...blocks.find((block) => block.props.label === 'A')!,
      props: {
        ...blocks.find((block) => block.props.label === 'A')!.props,
        regionKey: 'option:C',
        label: 'C',
        itemJson: JSON.stringify({ type: 'paragraph', text: '' }),
      },
      content: '',
    });

    expect(
      semanticBlocksToQuestionContent(source.type, blocks, source.content),
    ).toEqual({
      ok: false,
      message: 'Complete or remove empty options before using this question.',
    });
  });

  it('places a case passage before its stem and subparts in the overlay', () => {
    const source = question('case_based', {
      passage: [{ type: 'paragraph', text: 'Case passage.' }],
      stem: [{ type: 'paragraph', text: 'Read the case.' }],
      subparts: [
        {
          label: 'i',
          content: [{ type: 'paragraph', text: 'Answer this.' }],
        },
      ],
    });

    expect(
      questionToSemanticBlocks(source).map((block) => block.props.region),
    ).toEqual(['passage', 'stem', 'subpart']);
  });

  it('rejects deleting required question text instead of restoring it silently', () => {
    const source = question('short_answer', {
      stem: [{ type: 'paragraph', text: 'Explain the observation.' }],
    });

    expect(
      semanticBlocksToQuestionContent(source.type, [], source.content),
    ).toEqual({
      ok: false,
      message: 'Keep the question text before using this question.',
    });
  });

  it('uses canonical region keys for labelled Question content', () => {
    const source = question('case_based', {
      passage: [{ type: 'paragraph', text: 'Case passage.' }],
      subparts: [
        {
          label: 'a',
          content: [{ type: 'paragraph', text: 'First subpart.' }],
        },
      ],
    });

    expect(
      questionToSemanticBlocks(source).map((block) => block.props.regionKey),
    ).toEqual(['passage', 'subpart:a']);
  });

  it.each([
    [
      'assertion_reason',
      {
        assertion: [{ type: 'paragraph', text: 'Metals conduct.' }],
        reason: [{ type: 'paragraph', text: 'They have free electrons.' }],
        options: [
          {
            label: 'A',
            content: [{ type: 'paragraph', text: 'Both are true.' }],
          },
          {
            label: 'B',
            content: [{ type: 'paragraph', text: 'Only assertion is true.' }],
          },
        ],
      },
    ],
    [
      'very_short_answer',
      {
        stem: [
          { type: 'paragraph', text: 'Name the device.' },
          {
            type: 'image',
            assetId: 'asset_meter',
            caption: 'Circuit meter',
          },
        ],
      },
    ],
    [
      'short_answer',
      {
        stem: [{ type: 'paragraph', text: 'Calculate resistance.' }],
        subparts: [
          {
            label: 'a',
            marks: 1,
            content: [
              { type: 'equation', latex: 'R = V / I', text: 'R = V / I' },
            ],
          },
        ],
      },
    ],
    [
      'long_answer',
      {
        stem: [{ type: 'paragraph', text: 'Compare the materials.' }],
        subparts: [
          {
            label: 'a',
            content: [
              {
                type: 'table',
                rows: [
                  ['Material', 'Resistance'],
                  ['Copper', 'Low'],
                ],
              },
            ],
          },
        ],
      },
    ],
    [
      'case_based',
      {
        passage: [{ type: 'paragraph', text: 'Read the experiment.' }],
        subparts: [
          {
            label: 'i',
            content: [{ type: 'paragraph', text: 'State the observation.' }],
          },
        ],
      },
    ],
    [
      'internal_choice',
      {
        choices: [
          {
            displayStyle: 'or',
            chooseCount: 1,
            options: [
              {
                label: 'A',
                content: [{ type: 'paragraph', text: 'Explain refraction.' }],
              },
              {
                label: 'B',
                content: [{ type: 'paragraph', text: 'Explain reflection.' }],
              },
            ],
          },
        ],
      },
    ],
    [
      'diagram_based',
      {
        stem: [
          { type: 'paragraph', text: 'Label the diagram.' },
          {
            type: 'image_placeholder',
            text: 'Diagram from source',
            caption: 'Human eye',
          },
        ],
      },
    ],
    [
      'table_based',
      {
        stem: [
          { type: 'paragraph', text: 'Study the table.' },
          {
            type: 'table',
            rows: [
              ['pH', 'Nature'],
              ['2', 'Acidic'],
            ],
          },
        ],
      },
    ],
  ] satisfies Array<[DocQuestion['type'], DocQuestion['content']]>)(
    'round-trips %s without losing semantic regions',
    (type, content) => {
      const source = question(type, content);

      expect(
        semanticBlocksToQuestionContent(
          source.type,
          questionToSemanticBlocks(source),
          source.content,
        ),
      ).toEqual({ ok: true, content });
    },
  );

  it('keeps custom Questions read-only instead of flattening unknown content', () => {
    const source = question('custom', {
      stem: [{ type: 'paragraph', text: 'Custom source content.' }],
    });

    expect(questionToSemanticBlocks(source)).toEqual([]);
    expect(
      semanticBlocksToQuestionContent(source.type, [], source.content),
    ).toEqual({
      ok: false,
      message:
        'This question can be reviewed, but editing is not available for this type yet.',
    });
  });

  it('keeps future Question types loadable and read-only until registered', () => {
    const source = question('source_analysis', {
      stem: [{ type: 'paragraph', text: 'Analyse the source.' }],
    });

    expect(questionToSemanticBlocks(source)).toEqual([]);
    expect(
      semanticBlocksToQuestionContent(source.type, [], source.content),
    ).toMatchObject({ ok: false });
  });
});
