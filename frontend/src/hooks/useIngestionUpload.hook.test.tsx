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
  fetchIngestionJob,
  fetchIngestionJobAnswers,
  fetchIngestionJobQuestions,
  fetchIngestionJobs,
} from '@/lib/api';

const fetchIngestionJobsMock = vi.mocked(fetchIngestionJobs);
const fetchIngestionJobMock = vi.mocked(fetchIngestionJob);
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
  it('does not restore a settled job, so the teacher lands on a fresh picker', async () => {
    fetchIngestionJobsMock.mockResolvedValue([job({ status: 'done' })]);

    const { result } = renderHook(() => useIngestionUpload(10_000));

    // Give the restore effect a chance to (not) hydrate a job.
    await waitFor(() => {
      expect(fetchIngestionJobsMock).toHaveBeenCalled();
    });

    expect(result.current.job).toBeNull();
    expect(result.current.parsedQuestions).toHaveLength(0);
  });

  it('restores an in-flight job so returning teachers keep watching progress', async () => {
    fetchIngestionJobsMock.mockResolvedValue([job({ status: 'running' })]);
    fetchIngestionJobMock.mockResolvedValue(job({ status: 'running' }));

    const { result } = renderHook(() => useIngestionUpload(10_000));

    await waitFor(() => {
      expect(result.current.job?.status).toBe('running');
    });
    expect(result.current.polling).toBe(true);
  });

  it('exposes other in-flight jobs as a queue, excluding the detail-card one', async () => {
    // Serial drain: the newest upload shows in the card, the rest queue behind
    // it. The strip must list every non-terminal job that isn't the card's.
    fetchIngestionJobsMock.mockResolvedValue([
      job({ id: 1, status: 'running' }),
      job({ id: 2, status: 'pending' }),
      job({ id: 3, status: 'done' }),
    ]);
    fetchIngestionJobMock.mockResolvedValue(job({ id: 1, status: 'running' }));

    const { result } = renderHook(() => useIngestionUpload(10_000));

    await waitFor(() => {
      expect(result.current.job?.id).toBe(1);
    });
    // #2 is still queued; #1 is the card; #3 is terminal — neither belongs.
    expect(result.current.queuedJobs.map((queued) => queued.id)).toEqual([2]);
  });

  it('keeps the extracted question list visible when the optional answers endpoint fails', async () => {
    // Reach `done` the way a real upload does — via polling a live job — since
    // settled jobs are no longer restored on mount.
    fetchIngestionJobsMock.mockResolvedValue([job({ status: 'running' })]);
    fetchIngestionJobMock.mockResolvedValue(job({ status: 'done' }));
    fetchIngestionJobQuestionsMock.mockResolvedValue([question()]);
    fetchIngestionJobAnswersMock.mockRejectedValue(
      new Error('answers unavailable'),
    );

    const { result } = renderHook(() => useIngestionUpload(1));

    await waitFor(() => {
      expect(result.current.parsedQuestions).toHaveLength(1);
    });

    expect(result.current.parsedQuestions[0].text).toBe('Extracted question?');
    expect(result.current.loadingQuestions).toBe(false);
    expect(result.current.loadingAnswers).toBe(false);
    expect(result.current.answerGenerationError).toBe('answers unavailable');
  });
});
