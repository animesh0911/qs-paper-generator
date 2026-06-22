import { describe, expect, it } from 'vitest';
import type { GeneratedQuestionCandidate } from '@/types';
import {
  candidateAnswerText,
  candidateGroundingText,
  candidateQuestionText,
  candidateReviewCounts,
  candidateTopicLabels,
  toggleRejectedCandidate,
} from './candidate-review';

const candidate: GeneratedQuestionCandidate = {
  id: 9,
  status: 'ready_for_review',
  payload: {
    chapter_slug: 'life-processes',
    qtype: 'mcq',
    marks: 1,
    raw_text: 'Which process releases energy from glucose?',
    answer: 'A. Respiration',
    topic_names: ['Respiration', 'Life processes'],
    source: { citation: 'NCERT p. 84' },
  },
  question_id: null,
  accepted_at: null,
  created_at: '2026-06-21T00:00:00Z',
  updated_at: '2026-06-21T00:00:00Z',
};

describe('candidate review helpers', () => {
  it('treats all candidates as accepted until rejected and supports undo', () => {
    let rejected = new Set<number>();
    expect(candidateReviewCounts([{ id: 1 }, { id: 2 }], rejected)).toEqual({
      accepted: 2,
      rejected: 0,
    });

    rejected = toggleRejectedCandidate(rejected, 2);
    expect(candidateReviewCounts([{ id: 1 }, { id: 2 }], rejected)).toEqual({
      accepted: 1,
      rejected: 1,
    });

    rejected = toggleRejectedCandidate(rejected, 2);
    expect(candidateReviewCounts([{ id: 1 }, { id: 2 }], rejected)).toEqual({
      accepted: 2,
      rejected: 0,
    });
  });

  it('extracts visible question, answer, topic, and grounding text', () => {
    expect(candidateQuestionText(candidate)).toBe(
      'Which process releases energy from glucose?',
    );
    expect(candidateAnswerText(candidate)).toBe('A. Respiration');
    expect(candidateTopicLabels(candidate)).toEqual(['Respiration', 'Life processes']);
    expect(candidateGroundingText(candidate)).toBe('NCERT p. 84');
  });
});
