/** @vitest-environment jsdom */
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GeneratedQuestionCandidate, GenerationBatch } from '@/types';
import { useGenerationProgress } from './useGenerationProgress.hook';

vi.mock('@/lib/api', () => ({
  acceptGenerationCandidates: vi.fn(),
  discardGenerationBatch: vi.fn(),
  fetchGenerationBatch: vi.fn(),
  fetchGenerationCandidates: vi.fn(),
}));

import { fetchGenerationBatch, fetchGenerationCandidates } from '@/lib/api';

const fetchGenerationBatchMock = vi.mocked(fetchGenerationBatch);
const fetchGenerationCandidatesMock = vi.mocked(fetchGenerationCandidates);

function batch(overrides: Partial<GenerationBatch> = {}): GenerationBatch {
  return {
    id: 144,
    status: 'accepted',
    chapter_slugs: ['life-processes'],
    chapter_map_node_ids: ['life-processes:5.1'],
    topic_names: [],
    difficulty_preset: 'balanced',
    requested_count: 10,
    candidate_count: 1,
    error: '',
    ready_at: null,
    accepted_at: '2026-06-21T00:00:00Z',
    expired_at: null,
    discarded_at: null,
    created_at: '2026-06-21T00:00:00Z',
    updated_at: '2026-06-21T00:00:00Z',
    ...overrides,
  };
}

function candidate(
  overrides: Partial<GeneratedQuestionCandidate> = {},
): GeneratedQuestionCandidate {
  return {
    id: 1,
    status: 'accepted',
    payload: {
      chapter_slug: 'life-processes',
      qtype: 'mcq',
      marks: 1,
      raw_text: 'Which process releases energy from glucose?',
      content: {},
      answer: 'A. Respiration',
      topic_names: ['Respiration'],
    },
    question_id: 42,
    accepted_at: '2026-06-21T00:00:00Z',
    created_at: '2026-06-21T00:00:00Z',
    updated_at: '2026-06-21T00:00:00Z',
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useGenerationProgress', () => {
  it('loads candidates for accepted source-review batches', async () => {
    const acceptedBatch = batch();
    const acceptedCandidate = candidate();
    fetchGenerationBatchMock.mockResolvedValue(acceptedBatch);
    fetchGenerationCandidatesMock.mockResolvedValue([acceptedCandidate]);

    const { result } = renderHook(() => useGenerationProgress('144', 3000));

    await waitFor(() => expect(result.current.batch).toEqual(acceptedBatch));
    await waitFor(() =>
      expect(result.current.candidates).toEqual([acceptedCandidate]),
    );
    expect(fetchGenerationCandidatesMock).toHaveBeenCalledWith('144');
  });
});
