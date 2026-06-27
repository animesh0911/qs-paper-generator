import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Dashboard from './dashboard.page';

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ state: null }),
  NavLink: ({ children }: { children: ReactNode }) => <a>{children}</a>,
}));

vi.mock('@/hooks/useAuth.hook', () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

const coverageForm = {
  chapters: [
    {
      id: 4,
      slug: 'carbon-and-its-compounds',
      name: 'Carbon and its Compounds',
      order: 4,
    },
    { id: 5, slug: 'life-processes', name: 'Life Processes', order: 5 },
  ],
  chaptersLoading: false,
  chaptersError: '',
  formats: [{ format_id: 'board', name: 'Board format' }],
  selectedFormatId: 'board',
  chapterNameBySlug: {},
  selectedSlugs: new Set<string>(),
  difficulty: 'standard' as const,
  toggleChapter: vi.fn(),
  setDifficulty: vi.fn(),
  setSelectedFormatId: vi.fn(),
  toAssemblePayload: vi.fn(),
};

vi.mock('@/hooks/useCoverageForm.hook', () => ({
  DIFFICULTIES: ['easy', 'standard', 'hard'],
  useCoverageForm: () => coverageForm,
}));

describe('Dashboard (Generate paper page)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the paper-assembly workflow with workflow navigation', () => {
    const html = renderToStaticMarkup(<Dashboard />);

    expect(html).toContain('Generate paper');
    // The three workflows are reachable from the shared header nav.
    expect(html).toContain('Upload papers');
    expect(html).toContain('AI Q&amp;A');
  });

  it('no longer embeds the AI Q&A generation panel (it has its own page)', () => {
    const html = renderToStaticMarkup(<Dashboard />);

    expect(html).not.toContain('Pick Chapter 4, then choose topics');
    expect(html).not.toContain('Select Chapter 4 to show topics.');
  });
});
