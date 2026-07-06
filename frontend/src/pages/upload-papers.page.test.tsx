/** @vitest-environment jsdom */
import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactNode } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { IngestionUploadState } from '@/hooks/useIngestionUpload.hook';
import type { BankQuestion, IngestionJob } from '@/types';
import UploadPapersPage from './upload-papers.page';

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ pathname: '/upload' }),
  Link: ({ children }: { children: ReactNode }) => <a>{children}</a>,
  NavLink: ({ children }: { children: ReactNode }) => <a>{children}</a>,
}));

vi.mock('@/hooks/useAuth.hook', () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

let mockState: IngestionUploadState;
vi.mock('@/hooks/useIngestionUpload.hook', () => ({
  useIngestionUpload: () => mockState,
}));

function baseState(
  overrides: Partial<IngestionUploadState>,
): IngestionUploadState {
  return {
    file: null,
    validationError: '',
    uploading: false,
    uploadError: '',
    job: null,
    queuedJobs: [],
    polling: false,
    pollError: '',
    parsedQuestions: [],
    loadingQuestions: false,
    answerJob: null,
    generatedAnswers: [],
    loadingAnswers: false,
    generatingAnswers: false,
    answerGenerationError: '',
    recentExtractedPapers: [],
    generateAnswers: vi.fn(),
    generateAnswersForJob: vi.fn(),
    selectFile: vi.fn(),
    upload: vi.fn(),
    dismissJob: vi.fn(),
    retryJob: vi.fn(),
    ...overrides,
  };
}

function question(overrides: Partial<BankQuestion>): BankQuestion {
  return {
    id: 1,
    section: 'A',
    qtype: 'mcq',
    marks: 1,
    chapter: {
      id: 1,
      slug: 'acids-bases-and-salts',
      name: 'Acids, Bases and Salts',
      order: 1,
      subject_area: 'Chemistry',
    },
    cognitive_level: 'U',
    text: 'What is the colour of litmus in acid?',
    content: { stem: [] },
    options: [],
    primary_form: 'none',
    topic_names: ['Indicators'],
    parse_quality: 'clean',
    review_flags: [],
    verified: false,
    source_type: 'previous_year_paper',
    source_name: 'CBSE 2023',
    source_file_name: 'CBSE-2023.pdf',
    created_at: '',
    ...overrides,
  };
}

function job(overrides: Partial<IngestionJob>): IngestionJob {
  return {
    id: 1,
    status: 'pending',
    source_type: 'previous_year_paper',
    source_file_name: 'CBSE-2023.pdf',
    total_pages: 0,
    pages_done: 0,
    created_count: 0,
    skipped_count: 0,
    error: '',
    created_at: '',
    updated_at: '',
    ...overrides,
  };
}

function extractedPaper(
  extractedJob: IngestionJob,
  parsedQuestions: BankQuestion[],
  overrides: Partial<IngestionUploadState['recentExtractedPapers'][number]> = {},
): IngestionUploadState['recentExtractedPapers'][number] {
  return {
    job: extractedJob,
    parsedQuestions,
    loadingQuestions: false,
    answerJob: null,
    generatedAnswers: [],
    loadingAnswers: false,
    generatingAnswers: false,
    answerGenerationError: '',
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('UploadPapersPage', () => {
  it('shows the dropzone and source-type picker when idle', () => {
    mockState = baseState({});
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Upload PDF');
    expect(html).toContain(
      'Extract questions from a paper and add them to the question bank.',
    );
    expect(html).toContain('Drop a PDF here');
    expect(html).not.toContain('Source type');
    expect(html).not.toContain('Confirm source');
    expect(html).toContain('Upload &amp; extract');
  });

  it('opens the file picker by overlaying the native input, not a JS click', () => {
    // Safari and some browsers block programmatic inputRef.click() (and even
    // label→hidden-input activation), so the picker popup never opens. The real
    // <input type=file> is laid transparently over the dropzone so a click hits
    // the native control directly. Guard against regressing to a button/label.
    mockState = baseState({});
    render(<UploadPapersPage />);

    const input = document.querySelector<HTMLInputElement>('input[type=file]');
    expect(input).not.toBeNull();
    // The input must cover the dropzone (absolute, full size, clickable).
    expect(input?.className).toContain('absolute');
    expect(input?.className).toContain('inset-0');
    // No JS-click affordance: the browse text is not a button.
    expect(
      screen.queryByRole('button', { name: /drop a pdf here|browse/i }),
    ).toBeNull();
  });

  it('reports progress while a queued job extracts', () => {
    mockState = baseState({ job: job({ status: 'running' }) });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Extracting questions');
    expect(html).toContain('CBSE-2023.pdf');
    expect(html).not.toContain('Drop a PDF here');
  });

  it('shows every other in-flight upload in a queue strip beside the current one', () => {
    // The drain is serial, so extra uploads sit behind the current one. A
    // teacher who queued several PDFs must see them all, not just the newest.
    mockState = baseState({
      job: job({ id: 1, status: 'running', source_file_name: 'current.pdf' }),
      queuedJobs: [
        job({ id: 2, status: 'pending', source_file_name: 'paper_2019.pdf' }),
        job({
          id: 3,
          status: 'running',
          source_file_name: 'sample_3.pdf',
          total_pages: 6,
          pages_done: 1,
        }),
      ],
    });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Other uploads');
    expect(html).toContain('paper_2019.pdf');
    expect(html).toContain('Queued');
    expect(html).toContain('sample_3.pdf');
    expect(html).toContain('page 1 of 6');
  });

  it('keeps a failed extraction visible in the strip instead of dropping it', () => {
    // A failed job that isn't the one in the detail card must not silently
    // vanish — the teacher needs to see it failed (and can hover for the error).
    mockState = baseState({
      job: job({ id: 1, status: 'running', source_file_name: 'current.pdf' }),
      queuedJobs: [
        job({
          id: 4,
          status: 'failed',
          source_file_name: 'unreadable.pdf',
          error: 'Unreadable scan',
        }),
      ],
    });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('unreadable.pdf');
    expect(html).toContain('Failed');
    expect(html).toContain('Unreadable scan'); // surfaced via the row title
  });

  it('retries and removes a failed job from the queue strip', async () => {
    const user = userEvent.setup();
    const retryJob = vi.fn();
    const dismissJob = vi.fn();
    mockState = baseState({
      job: job({ id: 1, status: 'running', source_file_name: 'current.pdf' }),
      queuedJobs: [
        job({ id: 4, status: 'failed', source_file_name: 'unreadable.pdf' }),
      ],
      retryJob,
      dismissJob,
    });

    render(<UploadPapersPage />);
    await user.click(screen.getByRole('button', { name: /retry/i }));
    await user.click(screen.getByRole('button', { name: /remove/i }));

    expect(retryJob).toHaveBeenCalledWith(4);
    expect(dismissJob).toHaveBeenCalledWith(4);
  });

  it('omits the queue strip when nothing else is in flight', () => {
    mockState = baseState({ job: job({ status: 'running' }), queuedJobs: [] });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).not.toContain('Other uploads');
  });

  it('blocks parallel uploads while a job is still processing', () => {
    mockState = baseState({ job: job({ status: 'running' }) });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Extracting questions');
    expect(html).not.toContain('Drop a PDF here');
    expect(html).not.toContain('Upload another');
  });

  it('keeps the upload screen minimal by showing recent extracted-paper summaries', () => {
    const doneJob = job({ status: 'done', created_count: 12, skipped_count: 3 });
    const questions = [
      question({}),
      question({ id: 2, text: 'Name one strong acid.' }),
    ];
    mockState = baseState({
      job: doneJob,
      recentExtractedPapers: [extractedPaper(doneJob, questions)],
    });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Recent extracted papers');
    expect(html).toContain('12 questions extracted');
    expect(html).toContain('3 skipped');
    expect(html).toContain('Extracted questions');
    expect(html).not.toContain('2 questions grouped across 1 chapter');
    expect(html).not.toContain(
      'They’re ready to use when you generate a paper.',
    );
    expect(html).not.toContain('What is the colour of litmus in acid?');
    expect(html).not.toContain('Name one strong acid.');
    expect(html).toContain('Drop a PDF here');
    expect(html).not.toContain('Upload another');
  });

  it('opens the chapter-grouped extracted question screen from the review summary', async () => {
    const user = userEvent.setup();
    const doneJob = job({ status: 'done', created_count: 12, skipped_count: 3 });
    const questions = [
      question({}),
      question({
        id: 2,
        text: 'Name one strong acid.',
        topic_names: ['Acids'],
        parse_quality: 'partial',
        review_flags: ['mcq_too_few_options'],
      }),
      question({
        id: 3,
        text: 'State Ohm’s law.',
        content: {
          stem: [
            { type: 'paragraph', text: 'State Ohm’s law: ' },
            { type: 'equation', latex: 'V = IR' },
          ],
        },
        topic_names: ['Acids'],
        chapter: {
          id: 2,
          slug: 'electricity',
          name: 'Electricity',
          order: 12,
          subject_area: 'Physics',
        },
      }),
    ];
    mockState = baseState({
      job: doneJob,
      recentExtractedPapers: [extractedPaper(doneJob, questions)],
    });

    render(<UploadPapersPage />);

    expect(screen.queryByText('Name one strong acid.')).toBeNull();
    const reviewButton = screen.getByRole('button', {
      name: /review extracted questions/i,
    });
    await user.click(reviewButton);

    expect(
      screen.getByRole('dialog', { name: /extracted questions/i }),
    ).toBeTruthy();
    expect(screen.getByText('Acids, Bases and Salts')).toBeTruthy();
    expect(screen.getByText('Electricity')).toBeTruthy();
    expect(screen.getByText('Name one strong acid.')).toBeTruthy();
    expect(screen.getByText('State Ohm’s law:')).toBeTruthy();
    expect(document.querySelector('.katex')).toBeTruthy();
    expect(screen.queryByText('Needs review: MCQ Too Few Options')).toBeNull();
    expect(screen.queryByText('Apply')).toBeNull();
    expect(screen.queryByText('Understand')).toBeNull();
    expect(screen.queryByText('Clean parse')).toBeNull();

    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
      expect(document.activeElement).toBe(reviewButton);
    });
  });

  it('typesets raw extracted LaTeX and shows MCQ options in the review dialog', async () => {
    const user = userEvent.setup();
    const doneJob = job({ status: 'done', created_count: 1 });
    const questions = [
      question({
        text: 'Consider $$p\\,\\text{Al} + q\\,\\text{H}_2\\text{O} \\longrightarrow r\\,\\text{Al}_2\\text{O}_3 + s\\,\\text{H}_2$$',
        options: [
          { label: 'A', text: '$p=2$' },
          { label: 'B', text: '$p=4$' },
        ],
      }),
    ];
    mockState = baseState({
      job: doneJob,
      recentExtractedPapers: [extractedPaper(doneJob, questions)],
    });

    render(<UploadPapersPage />);
    await user.click(
      screen.getByRole('button', { name: /review extracted questions/i }),
    );

    expect(document.querySelector('.katex-display')).toBeTruthy();
    expect(screen.getByText('A.')).toBeTruthy();
    expect(screen.getByText('B.')).toBeTruthy();
    expect(document.body.textContent).not.toContain('$$p\\,\\text{Al}');
  });

  it('offers optional answer generation after extracted questions are shown', async () => {
    const user = userEvent.setup();
    const generateAnswersForJob = vi.fn();
    const doneJob = job({ status: 'done', created_count: 1 });
    mockState = baseState({
      job: doneJob,
      recentExtractedPapers: [extractedPaper(doneJob, [question({})])],
      generateAnswersForJob,
    });

    render(<UploadPapersPage />);

    const button = screen.getByRole('button', { name: /generate answers/i });
    expect(screen.queryByText(/draft answers/i)).toBeNull();
    expect(screen.queryByText(/auto-save ai answers/i)).toBeNull();
    await user.click(button);

    expect(generateAnswersForJob).toHaveBeenCalledWith(1);
  });

  it('shows generated answers inside the extracted question review', async () => {
    const user = userEvent.setup();
    const doneJob = job({ status: 'done', created_count: 1 });
    const answerJob = {
      id: 3,
      ingestion_job_id: 1,
      status: 'done' as const,
      total_count: 1,
      generated_count: 1,
      skipped_count: 0,
      error: '',
      created_at: '',
      updated_at: '',
    };
    const generatedAnswers = [
      {
        question_id: 7,
        answer: 'Litmus turns red in an acidic solution.',
        answer_source: 'generated_unverified' as const,
      },
    ];
    mockState = baseState({
      job: doneJob,
      recentExtractedPapers: [
        extractedPaper(doneJob, [question({ id: 7 })], {
          answerJob,
          generatedAnswers,
        }),
      ],
    });

    render(<UploadPapersPage />);
    await user.click(
      screen.getByRole('button', { name: /review extracted questions/i }),
    );

    expect(screen.getByText('AI generated answer')).toBeTruthy();
    expect(
      screen.getByText('Litmus turns red in an acidic solution.'),
    ).toBeTruthy();
  });

  it('surfaces the error when a job fails', () => {
    mockState = baseState({
      job: job({ status: 'failed', error: 'Unreadable scan' }),
    });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Extraction failed');
    expect(html).toContain('Unreadable scan');
    expect(html).toContain('Drop a PDF here');
    expect(html).not.toContain('Try another upload');
  });
});
