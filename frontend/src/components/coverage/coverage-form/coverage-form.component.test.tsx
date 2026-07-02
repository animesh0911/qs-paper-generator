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
    hasSelectedChapters: true,
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

afterEach(() => cleanup());

describe('CoverageFormView', () => {
  it('shows fixed context and one PaperFormat selector populated from backend formats', () => {
    const html = renderToStaticMarkup(
      <CoverageFormView form={makeForm()} busy={false} onGenerate={vi.fn()} />,
    );

    expect(html.match(/<select/g)).toHaveLength(1);
    expect(html).toContain('Class 10 · Science');
    expect(html).toContain('PaperFormat');
    expect(html).toContain('CBSE End Term Exam');
    expect(html).not.toContain('Preset');
  });

  it('groups chapters by subject area and exposes select controls', () => {
    const html = renderToStaticMarkup(
      <CoverageFormView form={makeForm()} busy={false} onGenerate={vi.fn()} />,
    );

    expect(html).toContain('Chemistry');
    expect(html).toContain('Biology');
    expect(html).toContain('Physics');
    expect(html).toContain('Select all Chapters');
    expect(html).toContain('Select group');
  });

  it('shows total marks and live paper structure summary', () => {
    const html = renderToStaticMarkup(
      <CoverageFormView form={makeForm()} busy={false} onGenerate={vi.fn()} />,
    );

    expect(html).toContain('Total marks');
    expect(html).toContain('readOnly=""');
    expect(html).toContain('Paper structure');
    expect(html).toContain('Marks by QuestionType');
    expect(html).toContain('≈ 39');
  });

  it('omits Advanced settings for the MVP setup surface', () => {
    const html = renderToStaticMarkup(
      <CoverageFormView form={makeForm()} busy={false} onGenerate={vi.fn()} />,
    );

    expect(html).not.toContain('Advanced settings');
    expect(html).not.toContain('Difficulty');
  });

  it('disables chapter bulk controls while chapters are loading', () => {
    const html = renderToStaticMarkup(
      <CoverageFormView
        form={makeForm({ chaptersLoading: true })}
        busy={false}
        onGenerate={vi.fn()}
      />,
    );

    expect(html).toContain('Select all Chapters');
    expect(html).toContain('disabled=""');
  });

  it('wires chapter group and generate controls to the parent state owner', async () => {
    const user = userEvent.setup();
    const toggleChapterGroup = vi.fn();
    const selectAllChapters = vi.fn();
    const onGenerate = vi.fn();

    render(
      <CoverageFormView
        form={makeForm({ toggleChapterGroup, selectAllChapters })}
        busy={false}
        onGenerate={onGenerate}
      />,
    );

    await user.click(
      screen.getByRole('button', { name: 'Select all Chapters' }),
    );
    expect(selectAllChapters).toHaveBeenCalledTimes(1);

    await user.click(
      screen.getAllByRole('button', { name: 'Select group' })[0],
    );
    expect(toggleChapterGroup).toHaveBeenCalledWith('Biology');

    await user.click(screen.getByRole('button', { name: 'Generate paper' }));
    expect(onGenerate).toHaveBeenCalledTimes(1);
  });

  it('blocks generation when no chapter is selected', () => {
    const html = renderToStaticMarkup(
      <CoverageFormView
        form={makeForm({
          selectedSlugs: new Set(),
          hasSelectedChapters: false,
        })}
        busy={false}
        onGenerate={vi.fn()}
      />,
    );

    expect(html).toContain('Chapter selection required');
    expect(html).toContain('Select at least one Chapter');
    expect(html).toContain('disabled=""');
  });
});
