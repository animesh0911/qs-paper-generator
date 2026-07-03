/**
 * Tests for generation-form request payload construction and setup helpers.
 *
 * @module useCoverageFormTests
 */
import { describe, expect, it } from 'vitest';
import {
  buildChapterGroups,
  buildCoverageAssemblePayload,
  buildPaperStructureSummary,
} from './useCoverageForm.hook';

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
