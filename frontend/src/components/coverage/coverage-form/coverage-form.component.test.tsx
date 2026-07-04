/**
 * @vitest-environment jsdom
 * Tests for the minimal paper setup surface.
 *
 * @module coverageFormTests
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CoverageForm } from '@/hooks/useCoverageForm.hook';
import { CoverageFormView } from './coverage-form.component';

function makeForm(overrides: Partial<CoverageForm> = {}): CoverageForm {
  const chapters = [
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
    {
      id: 10,
      slug: 'light-reflection-and-refraction',
      name: 'Light',
      order: 10,
      subject_area: 'Physics',
    },
  ];

  return {
    chapters,
    chapterGroups: [
      { subjectArea: 'Chemistry', chapters: [chapters[0]] },
      { subjectArea: 'Biology', chapters: [chapters[1]] },
      { subjectArea: 'Physics', chapters: [chapters[2]] },
    ],
    chaptersLoading: false,
    chaptersError: '',
    formats: [
      {
        format_id: 'cbse_science_class_10_board_compact_2026_v1',
        name: 'CBSE End Term Exam',
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
    sources: [],
    sourcesLoading: false,
    sourcesError: '',
    selectedFormatId: 'cbse_science_class_10_board_compact_2026_v1',
    selectedFormat: {
      format_id: 'cbse_science_class_10_board_compact_2026_v1',
      name: 'CBSE End Term Exam',
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
    selectedSlugs: new Set(['carbon-and-its-compounds']),
    difficulty: 'standard',
    selectedSourceKeys: new Set(),
    hasSelectedChapters: true,
    toggleSource: vi.fn(),
    selectAllSources: vi.fn(),
    clearAllSources: vi.fn(),
    toggleChapter: vi.fn(),
    selectAllChapters: vi.fn(),
    clearAllChapters: vi.fn(),
    toggleChapterGroup: vi.fn(),
    setDifficulty: vi.fn(),
    setSelectedFormatId: vi.fn(),
    setTotalMarks: vi.fn(),
    toAssemblePayload: vi.fn(),
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  document.body.style.overflow = '';
});

describe('CoverageFormView', () => {
  it('shows fixed context and one paper format selector populated from backend formats', () => {
    const html = renderToStaticMarkup(
      <CoverageFormView form={makeForm()} busy={false} onGenerate={vi.fn()} />,
    );

    expect(html.match(/<select/g)).toHaveLength(1);
    expect(html).toContain('Class 10 · Science');
    expect(html).toContain('Paper format');
    expect(html).toContain('CBSE End Term Exam');
    expect(html).not.toContain('Preset');
  });

  it('shows chapters and sources as compact dropdowns with a live scope panel', () => {
    const html = renderToStaticMarkup(
      <CoverageFormView
        form={makeForm({ selectedSourceKeys: new Set(['upload:new']) })}
        busy={false}
        onGenerate={vi.fn()}
      />,
    );

    expect(html).not.toContain('Select paper filters');
    expect(html).toContain('Choose chapters');
    expect(html).toContain('Choose sources');
    expect(html).toContain('Open choose chapters');
    expect(html).toContain('Open choose sources');
    expect(html).toContain('Paper scope');
    expect(html).toContain('Strict filter');
    expect(html).toContain('First draft only');
  });

  it('shows total marks and live paper structure summary', () => {
    const html = renderToStaticMarkup(
      <CoverageFormView form={makeForm()} busy={false} onGenerate={vi.fn()} />,
    );

    expect(html).toContain('Total marks');
    expect(html).toContain('<output');
    expect(html).toContain('Paper structure');
    expect(html).toContain('Marks by question type');
    expect(html).toContain('≈ 39');
  });

  it('omits Advanced settings for the MVP setup surface', () => {
    const html = renderToStaticMarkup(
      <CoverageFormView form={makeForm()} busy={false} onGenerate={vi.fn()} />,
    );

    expect(html).not.toContain('Advanced settings');
    expect(html).not.toContain('Difficulty');
  });

  it('shows chapter subject groups inside the focused chapter screen', async () => {
    const user = userEvent.setup();
    render(
      <CoverageFormView form={makeForm()} busy={false} onGenerate={vi.fn()} />,
    );

    await user.click(
      screen.getByRole('button', { name: 'Open choose chapters' }),
    );

    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(screen.getByText('Chemistry')).toBeTruthy();
    expect(screen.getByText('Biology')).toBeTruthy();
    expect(screen.getByText('Physics')).toBeTruthy();
    expect(
      screen.getByRole('button', { name: 'Select all chapters' }),
    ).toBeTruthy();
  });

  it('hardens the focused selection screen as an accessible modal', async () => {
    const user = userEvent.setup();
    render(
      <CoverageFormView form={makeForm()} busy={false} onGenerate={vi.fn()} />,
    );

    await user.click(
      screen.getByRole('button', { name: 'Open choose chapters' }),
    );

    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(document.body.style.overflow).toBe('hidden');
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.body.style.overflow).toBe('');

    await user.click(
      screen.getByRole('button', { name: 'Open choose chapters' }),
    );
    await user.click(
      screen.getByRole('button', { name: 'Close selection dialog' }),
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('disables chapter bulk controls while chapters are loading', async () => {
    const user = userEvent.setup();
    render(
      <CoverageFormView
        form={makeForm({ chaptersLoading: true })}
        busy={false}
        onGenerate={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole('button', { name: 'Open choose chapters' }),
    );

    expect(
      screen.getByRole('button', { name: 'Select all chapters' }),
    ).toHaveProperty('disabled', true);
  });

  it('shows source choices directly after chapters in the same list', async () => {
    const user = userEvent.setup();
    const toggleSource = vi.fn();

    render(
      <CoverageFormView
        form={makeForm({
          toggleSource,
          sources: [
            {
              key: 'upload:new',
              kind: 'upload',
              title: 'Newest uploaded paper',
              detail: 'Previous year paper',
              question_count: 12,
              matching_question_count: 5,
              created_at: '2026-06-22T10:00:00Z',
              status: 'ready',
            },
          ],
        })}
        busy={false}
        onGenerate={vi.fn()}
      />,
    );

    expect(
      screen.getByRole('heading', { name: 'Choose sources' }),
    ).toBeTruthy();

    await user.click(
      screen.getByRole('button', { name: 'Open choose sources' }),
    );
    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(screen.getByText('Newest uploaded paper')).toBeTruthy();

    await user.click(screen.getByLabelText(/Newest uploaded paper/));
    await user.click(screen.getByRole('button', { name: 'Approve selection' }));
    expect(toggleSource).toHaveBeenCalledWith('upload:new');
  });

  it('wires chapter group and generate controls to the parent state owner', async () => {
    const user = userEvent.setup();
    const toggleChapter = vi.fn();
    const onGenerate = vi.fn();

    render(
      <CoverageFormView
        form={makeForm({ toggleChapter })}
        busy={false}
        onGenerate={onGenerate}
      />,
    );

    await user.click(
      screen.getByRole('button', { name: 'Open choose chapters' }),
    );
    await user.click(
      screen.getByRole('button', { name: 'Select all chapters' }),
    );
    await user.click(screen.getByRole('button', { name: 'Approve selection' }));
    expect(toggleChapter).toHaveBeenCalledWith('life-processes');
    expect(toggleChapter).toHaveBeenCalledWith(
      'light-reflection-and-refraction',
    );

    await user.click(screen.getByRole('button', { name: 'Generate paper' }));
    expect(onGenerate).toHaveBeenCalledTimes(1);
  });

  it('blocks generation when neither chapters nor sources are selected', () => {
    const html = renderToStaticMarkup(
      <CoverageFormView
        form={makeForm({
          selectedSlugs: new Set(),
          selectedSourceKeys: new Set(),
          hasSelectedChapters: false,
        })}
        busy={false}
        onGenerate={vi.fn()}
      />,
    );

    expect(html).toContain('Choose chapters or sources to generate');
    expect(html).toContain('disabled=""');
  });

  it('allows generation from selected sources without selecting chapters', async () => {
    const user = userEvent.setup();
    const onGenerate = vi.fn();

    render(
      <CoverageFormView
        form={makeForm({
          selectedSlugs: new Set(),
          selectedSourceKeys: new Set(['upload:new']),
          hasSelectedChapters: false,
        })}
        busy={false}
        onGenerate={onGenerate}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Generate paper' }));

    expect(onGenerate).toHaveBeenCalledTimes(1);
  });

  it('shows source selection before choosing chapters', () => {
    render(
      <CoverageFormView
        form={makeForm({
          selectedSlugs: new Set(),
          hasSelectedChapters: false,
          sources: [
            {
              key: 'upload:new',
              kind: 'upload',
              title: 'Newest uploaded paper',
              detail: 'Previous year paper',
              question_count: 12,
              matching_question_count: 5,
              created_at: '2026-06-22T10:00:00Z',
              status: 'ready',
            },
          ],
        })}
        busy={false}
        onGenerate={vi.fn()}
      />,
    );

    expect(
      screen.getByRole('heading', { name: 'Choose sources' }),
    ).toBeTruthy();
  });
});
