/**
 * Tests for generation-form request payload construction.
 *
 * @module useCoverageFormTests
 */
import { describe, expect, it } from 'vitest';
import { buildCoverageAssemblePayload } from './useCoverageForm.hook';

describe('buildCoverageAssemblePayload', () => {
  it('includes the selected backend format with the coverage inputs', () => {
    expect(
      buildCoverageAssemblePayload({
        selectedFormatId: 'cbse_science_class_10_board_compact_2026_v1',
        difficulty: 'standard',
        selectedSlugs: new Set(['life-processes']),
        weights: { 'life-processes': '2' },
      }),
    ).toEqual({
      format_id: 'cbse_science_class_10_board_compact_2026_v1',
      difficulty: 'standard',
      chapter_slugs: ['life-processes'],
      weights: { 'life-processes': 2 },
    });
  });
});
