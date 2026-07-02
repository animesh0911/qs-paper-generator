import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { IngestionUploadState } from '@/hooks/useIngestionUpload.hook';
import type { IngestionJob } from '@/types';
import UploadPapersPage from './upload-papers.page';

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
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
    sourceType: 'previous_year_paper',
    validationError: '',
    uploading: false,
    uploadError: '',
    job: null,
    polling: false,
    pollError: '',
    parsedQuestions: [],
    loadingQuestions: false,
    selectFile: vi.fn(),
    setSourceType: vi.fn(),
    upload: vi.fn(),
    reset: vi.fn(),
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

afterEach(() => vi.clearAllMocks());

describe('UploadPapersPage', () => {
  it('shows the dropzone and source-type picker when idle', () => {
    mockState = baseState({});
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Upload previous papers');
    expect(html).toContain('Drop a PDF here');
    expect(html).toContain('Source type');
    expect(html).toContain('Upload &amp; extract');
  });

  it('reports progress while a queued job extracts', () => {
    mockState = baseState({ job: job({ status: 'running' }) });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Extracting questions');
    expect(html).toContain('CBSE-2023.pdf');
    expect(html).not.toContain('Drop a PDF here');
  });

  it('reports the extracted count when a job is done', () => {
    mockState = baseState({
      job: job({ status: 'done', created_count: 12, skipped_count: 3 }),
    });
    const html = renderToStaticMarkup(<UploadPapersPage />);

    expect(html).toContain('Added 12 questions to your bank');
    expect(html).toContain('3 questions were skipped');
    expect(html).toContain('Upload another');
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
