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
    polling: false,
    pollError: '',
    parsedQuestions: [],
    loadingQuestions: false,
    selectFile: vi.fn(),
    upload: vi.fn(),
    reset: vi.fn(),
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

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('UploadPapersPage', () => {
  it('shows the dropzone and source-type picker when idle', () => {
    mockState = baseState({});
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Upload a PDF');
    expect(html).toContain(
      'AI extracts the questions from your PDF and adds them to your',
    );
    expect(html).toContain('Drop a PDF here');
    expect(html).not.toContain('Source type');
    expect(html).not.toContain('Confirm source');
    expect(html).toContain('Upload &amp; extract');
  });

  it('reports progress while a queued job extracts', () => {
    mockState = baseState({ job: job({ status: 'running' }) });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Extracting questions');
    expect(html).toContain('CBSE-2023.pdf');
    expect(html).not.toContain('Drop a PDF here');
  });

  it('keeps the upload screen minimal by showing a clickable extracted-question summary when a job is done', () => {
    mockState = baseState({
      job: job({ status: 'done', created_count: 12, skipped_count: 3 }),
      parsedQuestions: [
        question({}),
        question({ id: 2, text: 'Name one strong acid.' }),
      ],
    });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Added 12 questions to your bank');
    expect(html).toContain('3 questions were skipped');
    expect(html).toContain('Review extracted questions');
    expect(html).not.toContain('2 questions grouped across 1 chapter');
    expect(html).not.toContain('They’re ready to use when you generate a paper.');
    expect(html).not.toContain('What is the colour of litmus in acid?');
    expect(html).not.toContain('Name one strong acid.');
    expect(html).toContain('Upload another');
  });

  it('opens the chapter-grouped extracted question screen from the review summary', async () => {
    const user = userEvent.setup();
    mockState = baseState({
      job: job({ status: 'done', created_count: 12, skipped_count: 3 }),
      parsedQuestions: [
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
      ],
    });

    render(<UploadPapersPage />);

    expect(screen.queryByText('Name one strong acid.')).toBeNull();
    const reviewButton = screen.getByRole('button', {
      name: /review extracted questions/i,
    });
    await user.click(reviewButton);

    expect(
      screen.getByRole('dialog', { name: /extracted question review/i }),
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

  it('surfaces the error when a job fails', () => {
    mockState = baseState({
      job: job({ status: 'failed', error: 'Unreadable scan' }),
    });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Extraction failed');
    expect(html).toContain('Unreadable scan');
    expect(html).toContain('Try another upload');
  });
});
