/** @vitest-environment jsdom */
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { BankQuestion, IngestionJob } from '@/types';
import { useIngestionUpload } from './useIngestionUpload.hook';

vi.mock('@/lib/api', () => ({
  fetchIngestionJob: vi.fn(),
  fetchIngestionJobAnswers: vi.fn(),
  fetchIngestionJobQuestions: vi.fn(),
  fetchIngestionJobs: vi.fn(),
  generateIngestionJobAnswers: vi.fn(),
  uploadIngestionPdf: vi.fn(),
}));

import {
  fetchIngestionJobAnswers,
  fetchIngestionJobQuestions,
  fetchIngestionJobs,
} from '@/lib/api';

const fetchIngestionJobsMock = vi.mocked(fetchIngestionJobs);
const fetchIngestionJobQuestionsMock = vi.mocked(fetchIngestionJobQuestions);
const fetchIngestionJobAnswersMock = vi.mocked(fetchIngestionJobAnswers);

function job(overrides: Partial<IngestionJob> = {}): IngestionJob {
  return {
    id: 11,
    status: 'done',
    source_type: 'previous_year_paper',
    source_file_name: 'paper.pdf',
    total_pages: 2,
    pages_done: 2,
    created_count: 1,
    skipped_count: 0,
    error: '',
    created_at: '',
    updated_at: '',
    ...overrides,
  };
}

function question(overrides: Partial<BankQuestion> = {}): BankQuestion {
  return {
    id: 7,
    section: 'A',
    qtype: 'mcq',
    marks: 1,
    chapter: null,
    cognitive_level: 'U',
    text: 'Extracted question?',
    content: { stem: [] },
    options: [],
    primary_form: 'none',
    topic_names: [],
    parse_quality: 'clean',
    review_flags: [],
    verified: false,
    source_type: 'previous_year_paper',
    source_name: '',
    source_file_name: 'paper.pdf',
    created_at: '',
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useIngestionUpload', () => {
  it('keeps the extracted question list visible when the optional answers endpoint fails', async () => {
    fetchIngestionJobsMock.mockResolvedValue([job()]);
    fetchIngestionJobQuestionsMock.mockResolvedValue([question()]);
    fetchIngestionJobAnswersMock.mockRejectedValue(new Error('answers unavailable'));

    const { result } = renderHook(() => useIngestionUpload(10_000));

    await waitFor(() => {
      expect(result.current.parsedQuestions).toHaveLength(1);
    });

    expect(result.current.parsedQuestions[0].text).toBe('Extracted question?');
    expect(result.current.loadingQuestions).toBe(false);
    expect(result.current.loadingAnswers).toBe(false);
    expect(result.current.answerGenerationError).toBe('answers unavailable');
  });
});
