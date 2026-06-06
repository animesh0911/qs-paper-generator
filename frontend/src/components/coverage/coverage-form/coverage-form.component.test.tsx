/**
 * Tests for the generation form's backend-owned format selection.
 *
 * @module coverageFormTests
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { CoverageForm } from '@/hooks/useCoverageForm.hook';
import { CoverageFormView } from './coverage-form.component';

describe('CoverageFormView', () => {
  it('offers one Format selector populated from backend-owned formats', () => {
    const form: CoverageForm = {
      chapters: [],
      formats: [
        {
          format_id: 'cbse_science_class_10_board_compact_2026_v1',
          name: 'CBSE End Term Exam',
        },
      ],
      selectedFormatId: 'cbse_science_class_10_board_compact_2026_v1',
      chapterNameBySlug: {},
      selectedSlugs: new Set(),
      weights: {},
      difficulty: 'standard',
      toggleChapter: vi.fn(),
      setWeight: vi.fn(),
      setDifficulty: vi.fn(),
      setSelectedFormatId: vi.fn(),
      toAssemblePayload: vi.fn(),
    };

    const html = renderToStaticMarkup(
      <CoverageFormView form={form} busy={false} onGenerate={vi.fn()} />,
    );

    expect(html.match(/<select/g)).toHaveLength(1);
    expect(html).toContain('>Format</label>');
    expect(html).toContain('CBSE End Term Exam');
    expect(html).not.toContain('Preset');
  });
});
