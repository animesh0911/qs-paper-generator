/** @vitest-environment jsdom */
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { BankQuestion, IngestionJob } from '@/types';
import { useIngestionUpload } from './useIngestionUpload.hook';

vi.mock('@/lib/api', () => ({
  fetchIngestionJob: vi.fn(),
  fetchIngestionJobAnswers: vi.fn(),
  fetchIngestionJobQuestions: vi.fn(),
  fetchIngestionJobs: vi.fn(),
  generateIngestionJobAnswers: vi.fn(),
  retryIngestionJob: vi.fn(),
  uploadIngestionPdf: vi.fn(),
}));

import {
  fetchIngestionJob,
  fetchIngestionJobAnswers,
  fetchIngestionJobQuestions,
  fetchIngestionJobs,
  retryIngestionJob,
  uploadIngestionPdf,
} from '@/lib/api';

const fetchIngestionJobsMock = vi.mocked(fetchIngestionJobs);
const fetchIngestionJobMock = vi.mocked(fetchIngestionJob);
const fetchIngestionJobQuestionsMock = vi.mocked(fetchIngestionJobQuestions);
const fetchIngestionJobAnswersMock = vi.mocked(fetchIngestionJobAnswers);
const retryIngestionJobMock = vi.mocked(retryIngestionJob);
const uploadIngestionPdfMock = vi.mocked(uploadIngestionPdf);

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
  it('does not restore completed uploads when returning to upload', async () => {
    fetchIngestionJobsMock.mockResolvedValue([job({ status: 'done' })]);

    const { result } = renderHook(() => useIngestionUpload(10_000));

    await waitFor(() => {
      expect(fetchIngestionJobsMock).toHaveBeenCalled();
    });

    expect(result.current.job).toBeNull();
    expect(result.current.parsedQuestions).toEqual([]);
    expect(fetchIngestionJobQuestionsMock).not.toHaveBeenCalled();
  });

  it('loads the last 3 completed uploads as recent extracted papers', async () => {
    fetchIngestionJobsMock.mockResolvedValue([
      job({ id: 1, status: 'done', source_file_name: 'paper-1.pdf' }),
      job({ id: 2, status: 'done', source_file_name: 'paper-2.pdf' }),
      job({ id: 3, status: 'done', source_file_name: 'paper-3.pdf' }),
      job({ id: 4, status: 'done', source_file_name: 'paper-4.pdf' }),
    ]);
    fetchIngestionJobQuestionsMock.mockResolvedValue([question()]);
    fetchIngestionJobAnswersMock.mockResolvedValue({ job: null, answers: [] });

    const { result } = renderHook(() => useIngestionUpload(10_000));

    await waitFor(() => {
      expect(result.current.recentExtractedPapers).toHaveLength(3);
    });

    expect(result.current.job).toBeNull();
    expect(
      result.current.recentExtractedPapers.map((paper) =>
        paper.job.source_file_name,
      ),
    ).toEqual(['paper-1.pdf', 'paper-2.pdf', 'paper-3.pdf']);
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

  it('clears previous job questions and answers when starting a new upload', async () => {
    fetchIngestionJobsMock.mockResolvedValue([job({ status: 'running' })]);
    fetchIngestionJobMock.mockImplementation(async (id) =>
      Number(id) === 12
        ? job({ id: 12, status: 'pending', created_count: 0 })
        : job({ id: Number(id), status: 'done' }),
    );
    fetchIngestionJobQuestionsMock.mockResolvedValue([question({ id: 7 })]);
    fetchIngestionJobAnswersMock.mockResolvedValue({
      job: {
        id: 21,
        ingestion_job_id: 11,
        status: 'done',
        total_count: 1,
        generated_count: 1,
        skipped_count: 0,
        error: '',
        created_at: '',
        updated_at: '',
      },
      answers: [
        {
          question_id: 7,
          answer: 'Old generated answer.',
          answer_source: 'generated_unverified',
        },
      ],
    });
    uploadIngestionPdfMock.mockResolvedValue(
      job({ id: 12, status: 'pending', created_count: 0 }),
    );

    const { result } = renderHook(() => useIngestionUpload(1));

    await waitFor(() => {
      expect(result.current.generatedAnswers).toHaveLength(1);
    });

    act(() => {
      result.current.selectFile(
        new File(['%PDF-1.4'], 'next.pdf', { type: 'application/pdf' }),
      );
    });
    await act(async () => {
      await result.current.upload();
    });

    expect(result.current.job?.id).toBe(12);
    expect(result.current.parsedQuestions).toEqual([]);
    expect(result.current.generatedAnswers).toEqual([]);
    expect(result.current.answerJob).toBeNull();
  });

  it('promotes a retried failed job into the main polling card', async () => {
    fetchIngestionJobsMock.mockResolvedValue([
      job({ id: 9, status: 'failed', error: 'Unreadable scan' }),
    ]);
    retryIngestionJobMock.mockResolvedValue(job({ id: 9, status: 'pending' }));

    const { result } = renderHook(() => useIngestionUpload(10_000));

    await waitFor(() => {
      expect(result.current.queuedJobs.map((queued) => queued.id)).toEqual([9]);
    });

    await act(async () => {
      await result.current.retryJob(9);
    });

    expect(result.current.job?.id).toBe(9);
    expect(result.current.job?.status).toBe('pending');
    expect(result.current.polling).toBe(true);
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
