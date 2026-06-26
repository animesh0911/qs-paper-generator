import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Dashboard from './dashboard.page';

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ state: null }),
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
  weights: {},
  difficulty: 'standard' as const,
  toggleChapter: vi.fn(),
  setWeight: vi.fn(),
  setDifficulty: vi.fn(),
  setSelectedFormatId: vi.fn(),
  toAssemblePayload: vi.fn(),
};

vi.mock('@/hooks/useCoverageForm.hook', () => ({
  DIFFICULTIES: ['easy', 'standard', 'hard'],
  useCoverageForm: () => coverageForm,
}));

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('keeps Generate paper primary and exposes Generate AI Q&A as the secondary topic-scoped workflow', () => {
    const html = renderToStaticMarkup(<Dashboard />);

    expect(html.indexOf('Generate paper')).toBeLessThan(
      html.indexOf('Generate AI Q&amp;A'),
    );
    expect(html).toContain('Pick Chapter 4, then choose topics');
    expect(html).toContain('NCERT Chapter');
    expect(html).toContain('Select Chapter 4 to show topics.');
    const qnaPanelHtml = html.slice(html.indexOf('Generate AI Q&amp;A'));
    expect(qnaPanelHtml).toContain('Chapter 4: Carbon and its Compounds');
    expect(qnaPanelHtml).not.toContain('5. Life Processes');
    expect(html).not.toContain(
      'Selected NCERT topics define the generation scope',
    );
    expect(html).not.toMatch(/batch size|prompt|instructions|topic hints/i);
  });
});
