/**
 * @vitest-environment jsdom
 *
 * Tests for generation-form request payload construction and setup helpers.
 *
 * @module useCoverageFormTests
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  fetchChapters,
  fetchPaperFormats,
  fetchPaperSources,
} from '@/lib/api';
import {
  buildChapterGroups,
  buildCoverageAssemblePayload,
  buildPaperStructureSummary,
  sortPaperSourcesByUploadTime,
  useCoverageForm,
} from './useCoverageForm.hook';

vi.mock('@/lib/api', () => ({
  fetchChapters: vi.fn(),
  fetchPaperFormats: vi.fn(),
  fetchPaperSources: vi.fn(),
}));

const mockedFetchChapters = vi.mocked(fetchChapters);
const mockedFetchPaperFormats = vi.mocked(fetchPaperFormats);
const mockedFetchPaperSources = vi.mocked(fetchPaperSources);

describe('useCoverageForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    mockedFetchChapters.mockResolvedValue([
      {
        id: 4,
        slug: 'carbon-and-its-compounds',
        name: 'Carbon and its Compounds',
        order: 4,
        subject_area: 'Chemistry',
      },
    ]);
    mockedFetchPaperFormats.mockResolvedValue([
      {
        format_id: 'cbse_science_class_10_board_compact_2026_v1',
        name: 'CBSE End Term Exam',
        preset_name: 'board',
        total_marks: 80,
        section_count: 3,
        question_count: 39,
        marks_by_question_type: { mcq: 20 },
      },
    ]);
  });

  it('keeps existing source choices visible when a throttled refresh fails', async () => {
    const existingSources = [
      {
        key: 'upload:7',
        kind: 'upload' as const,
        title: 'Recent upload',
        detail: 'Previous year paper',
        question_count: 12,
        matching_question_count: 12,
        created_at: '2026-06-22T10:00:00Z',
        status: 'completed',
      },
    ];
    mockedFetchPaperSources
      .mockResolvedValueOnce(existingSources)
      .mockResolvedValueOnce(existingSources)
      .mockRejectedValueOnce(
        new Error('Request was throttled. Expected available in 1 second.'),
      );

    const { result } = renderHook(() => useCoverageForm());

    await waitFor(() =>
      expect(result.current.sources.map((source) => source.key)).toEqual([
        'upload:7',
      ]),
    );

    act(() => result.current.toggleChapter('carbon-and-its-compounds'));

    await waitFor(() => expect(result.current.sourcesError).toContain('throttled'));
    expect(result.current.sources.map((source) => source.key)).toEqual([
      'upload:7',
    ]);
  });
});

describe('buildCoverageAssemblePayload', () => {
  it('includes the selected backend format with explicit chapters', () => {
    expect(
      buildCoverageAssemblePayload({
        selectedFormatId: 'cbse_science_class_10_board_compact_2026_v1',
        difficulty: 'standard',
        selectedSlugs: new Set(['life-processes']),
        selectedSourceKeys: new Set(['upload:7']),
      }),
    ).toEqual({
      format_id: 'cbse_science_class_10_board_compact_2026_v1',
      difficulty: 'standard',
      chapter_slugs: ['life-processes'],
      preferred_source_keys: ['upload:7'],
    });
  });

  it('supports source-only generation when no chapters are selected', () => {
    expect(
      buildCoverageAssemblePayload({
        selectedFormatId: 'cbse_science_class_10_board_compact_2026_v1',
        difficulty: 'standard',
        selectedSlugs: new Set(),
        selectedSourceKeys: new Set(['upload:7']),
      }),
    ).toEqual({
      format_id: 'cbse_science_class_10_board_compact_2026_v1',
      difficulty: 'standard',
      chapter_slugs: [],
      preferred_source_keys: ['upload:7'],
    });
  });
});

describe('buildChapterGroups', () => {
  it('groups chapters by backend subject area metadata', () => {
    const groups = buildChapterGroups([
      {
        id: 10,
        slug: 'light',
        name: 'Light',
        order: 10,
        subject_area: 'Physics',
      },
      {
        id: 4,
        slug: 'carbon',
        name: 'Carbon',
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
    ]);

    expect(groups.map((group) => group.subjectArea)).toEqual([
      'Chemistry',
      'Biology',
      'Physics',
    ]);
  });

  it('uses NCERT fallback grouping only when backend metadata is absent', () => {
    const groups = buildChapterGroups([
      { id: 5, slug: 'life-processes', name: 'Life Processes', order: 5 },
      { id: 13, slug: 'our-environment', name: 'Our Environment', order: 13 },
      { id: 9, slug: 'electricity', name: 'Electricity', order: 9 },
    ]);

    expect(groups.map((group) => group.subjectArea)).toEqual([
      'Biology',
      'Physics',
    ]);
    expect(groups[0].chapters.map((chapter) => chapter.slug)).toEqual([
      'life-processes',
      'our-environment',
    ]);
  });
});

describe('sortPaperSourcesByUploadTime', () => {
  it('orders selectable sources newest upload first', () => {
    const ordered = sortPaperSourcesByUploadTime([
      {
        key: 'upload:old',
        kind: 'upload',
        title: 'Old upload',
        detail: '',
        question_count: 3,
        created_at: '2026-06-20T10:00:00Z',
        status: 'ready',
      },
      {
        key: 'upload:new',
        kind: 'upload',
        title: 'Newest upload',
        detail: '',
        question_count: 4,
        created_at: '2026-06-22T10:00:00Z',
        status: 'ready',
      },
      {
        key: 'upload:middle',
        kind: 'upload',
        title: 'Middle upload',
        detail: '',
        question_count: 5,
        created_at: '2026-06-21T10:00:00Z',
        status: 'ready',
      },
    ]);

    expect(ordered.map((source) => source.key)).toEqual([
      'upload:new',
      'upload:middle',
      'upload:old',
    ]);
  });
});

describe('buildPaperStructureSummary', () => {
  it('summarizes backend format structure when present', () => {
    expect(
      buildPaperStructureSummary({
        selectedFormat: {
          format_id: 'cbse_science_class_10_board_compact_2026_v1',
          name: 'CBSE End Term Exam',
          preset_name: 'board',
          total_marks: 80,
          section_count: 3,
          question_count: 39,
          marks_by_question_type: { mcq: 20, vsa: 12 },
        },
        totalMarks: 20,
      }),
    ).toEqual({
      totalMarks: 80,
      sectionCount: 3,
      approximateQuestionCount: 39,
      marksByQuestionType: { mcq: 20, vsa: 12 },
    });
  });
});
