import { describe, expect, it } from 'vitest';
import {
  buildGenerationBatchPayload,
  generationStageDescription,
  generationStageLabel,
  shouldShowNoValidQuestionsMessage,
} from './question-generation';

describe('buildGenerationBatchPayload', () => {
  it('requires at least one canonical Chapter and maps teacher difficulty labels to backend presets', () => {
    expect(() =>
      buildGenerationBatchPayload({
        chapterSlugs: [],
        topicNamesByChapter: {},
        difficulty: 'Standard',
      }),
    ).toThrow('Select at least one Chapter.');

    expect(
      buildGenerationBatchPayload({
        chapterSlugs: ['life-processes'],
        topicNamesByChapter: {
          'life-processes': 'Nutrition, Respiration\nTransport',
          electricity: 'Ohm Law',
        },
        difficulty: 'Challenging',
      }),
    ).toEqual({
      chapter_slugs: ['life-processes'],
      topic_names: ['Nutrition', 'Respiration', 'Transport'],
      difficulty_preset: 'hard',
    });
  });
});

describe('generation progress labels', () => {
  it('renders only real backend stages and no fabricated percentages', () => {
    expect(generationStageLabel('queued')).toBe('Queued');
    expect(generationStageLabel('generating_questions')).toBe(
      'Generating Questions',
    );
    expect(generationStageLabel('validating')).toBe('Validating');
    expect(generationStageLabel('ready_for_review')).toBe('Ready for review');
    expect(generationStageDescription('ready_for_review')).toContain(
      'not in the Question bank',
    );
  });

  it('uses the no-valid-Questions failure state only for failed or empty-ready batches', () => {
    expect(
      shouldShowNoValidQuestionsMessage({ status: 'failed', candidate_count: 0 }),
    ).toBe(true);
    expect(
      shouldShowNoValidQuestionsMessage({
        status: 'ready_for_review',
        candidate_count: 0,
      }),
    ).toBe(true);
    expect(
      shouldShowNoValidQuestionsMessage({
        status: 'ready_for_review',
        candidate_count: 2,
      }),
    ).toBe(false);
  });
});
