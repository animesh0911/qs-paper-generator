import { renderToStaticMarkup } from 'react-dom/server';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Dashboard from './dashboard.page';

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ pathname: '/', state: null }),
  Link: ({ children }: { children: ReactNode }) => <a>{children}</a>,
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
      subject_area: 'Chemistry',
    },
    {
      id: 5,
      slug: 'life-processes',
      name: 'Life Processes',
      order: 5,
      subject_area: 'Biology',
    },
  ],
  chapterGroups: [
    {
      subjectArea: 'Chemistry',
      chapters: [
        {
          id: 4,
          slug: 'carbon-and-its-compounds',
          name: 'Carbon and its Compounds',
          order: 4,
          subject_area: 'Chemistry',
        },
      ],
    },
    {
      subjectArea: 'Biology',
      chapters: [
        {
          id: 5,
          slug: 'life-processes',
          name: 'Life Processes',
          order: 5,
          subject_area: 'Biology',
        },
      ],
    },
  ],
  chaptersLoading: false,
  chaptersError: '',
  sources: [],
  sourcesLoading: false,
  sourcesError: '',
  selectedSourceKeys: new Set<string>(),
  toggleSource: vi.fn(),
  selectAllSources: vi.fn(),
  clearAllSources: vi.fn(),
  formats: [
    {
      format_id: 'board',
      name: 'Board format',
      preset_name: 'board',
      total_marks: 80,
      section_count: 3,
      question_count: 39,
      marks_by_question_type: {
        mcq: 20,
        very_short_answer: 12,
        short_answer: 21,
        long_answer: 15,
        case_based: 12,
      },
    },
  ],
  selectedFormatId: 'board',
  selectedFormat: {
    format_id: 'board',
    name: 'Board format',
    preset_name: 'board',
    total_marks: 80,
    section_count: 3,
    question_count: 39,
    marks_by_question_type: {
      mcq: 20,
      very_short_answer: 12,
      short_answer: 21,
      long_answer: 15,
      case_based: 12,
    },
  },
  totalMarks: 80,
  structureSummary: {
    totalMarks: 80,
    sectionCount: 3,
    approximateQuestionCount: 39,
    marksByQuestionType: {
      mcq: 20,
      very_short_answer: 12,
      short_answer: 21,
      long_answer: 15,
      case_based: 12,
    },
  },
  chapterNameBySlug: {},
  selectedSlugs: new Set<string>(['carbon-and-its-compounds']),
  difficulty: 'standard' as const,
  hasSelectedChapters: true,
  toggleChapter: vi.fn(),
  selectAllChapters: vi.fn(),
  clearAllChapters: vi.fn(),
  toggleChapterGroup: vi.fn(),
  setDifficulty: vi.fn(),
  setSelectedFormatId: vi.fn(),
  setTotalMarks: vi.fn(),
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
    expect(html).toContain('open chapters or sources only when you');
    expect(html).toContain('Choose chapters');
    expect(html).toContain('Choose sources');
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
