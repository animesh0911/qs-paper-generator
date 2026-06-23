import { describe, expect, it } from 'vitest';
import {
  buildGenerationBatchPayload,
  generationStageDescription,
  generationStageLabel,
  shouldShowNoValidQuestionsMessage,
} from './question-generation';

describe('buildGenerationBatchPayload', () => {
  it('requires one canonical Chapter and selected NCERT topic nodes', () => {
    expect(() =>
      buildGenerationBatchPayload({
        chapterSlug: '',
        chapterMapNodeIds: [],
        difficulty: 'Standard',
      }),
    ).toThrow('Select one Chapter.');

    expect(() =>
      buildGenerationBatchPayload({
        chapterSlug: 'life-processes',
        chapterMapNodeIds: [],
        difficulty: 'Standard',
      }),
    ).toThrow('Select at least one NCERT topic.');
  });

  it('maps teacher difficulty labels and selected topic nodes to the backend payload', () => {
    expect(
      buildGenerationBatchPayload({
        chapterSlug: 'life-processes',
        chapterMapNodeIds: ['life-processes:5.1', 'life-processes:activity-5.1'],
        difficulty: 'Challenging',
      }),
    ).toEqual({
      chapter_slugs: ['life-processes'],
      chapter_map_node_ids: ['life-processes:5.1', 'life-processes:activity-5.1'],
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
