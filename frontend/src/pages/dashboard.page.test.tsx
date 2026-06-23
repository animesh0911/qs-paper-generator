import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Dashboard from './dashboard.page';

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock('@/hooks/useAuth.hook', () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

const coverageForm = {
  chapters: [
    { id: 1, slug: 'life-processes', name: 'Life Processes', order: 5 },
    { id: 2, slug: 'electricity', name: 'Electricity', order: 12 },
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
    expect(html).toContain('Secondary workflow');
    expect(html).toContain('NCERT Chapter');
    expect(html).toContain('The MVP supports one Chapter per run');
    expect(html).not.toMatch(/batch size|prompt|instructions|topic hints/i);
  });
});
