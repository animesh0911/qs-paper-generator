/** @vitest-environment jsdom */
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { IngestionJob } from '@/types';
import { AppHeader } from './app-header.component';

vi.mock('react-router-dom', () => ({
  useLocation: () => ({ pathname: '/generate' }),
  Link: ({ to, children, ...props }: { to: string; children: ReactNode }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
  NavLink: ({
    to,
    children,
    className,
  }: {
    to: string;
    children: ReactNode;
    className?: string | ((state: { isActive: boolean }) => string);
  }) => (
    <a
      href={to}
      className={
        typeof className === 'function' ? className({ isActive: false }) : className
      }
    >
      {children}
    </a>
  ),
}));

vi.mock('@/hooks/useAuth.hook', () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

vi.mock('@/lib/api', () => ({
  fetchGenerationBatches: vi.fn(async () => []),
  fetchIngestionJobs: vi.fn(),
}));

import { fetchIngestionJobs } from '@/lib/api';

const fetchIngestionJobsMock = vi.mocked(fetchIngestionJobs);

function job(overrides: Partial<IngestionJob> = {}): IngestionJob {
  return {
    id: 11,
    status: 'done',
    source_type: 'previous_year_paper',
    source_file_name: 'paper.pdf',
    total_pages: 2,
    pages_done: 2,
    created_count: 3,
    skipped_count: 0,
    error: '',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AppHeader ingestion activity', () => {
  it('keeps a completed extraction reachable from the top-bar activity chip', async () => {
    fetchIngestionJobsMock.mockResolvedValue([job({ status: 'done' })]);

    render(<AppHeader />);

    const chip = await screen.findByRole('link', {
      name: /3 extracted\. open upload progress/i,
    });

    expect(chip.getAttribute('href')).toBe('/upload');
    await waitFor(() => {
      expect(screen.getByText('3 extracted')).toBeTruthy();
    });
  });
});
