/**
 * Tests for dev-only editor fixture selection.
 *
 * These checks keep the complete extracted paper load path separate from the
 * smaller default mock while proving the route can render the full snapshot.
 *
 * @module editorFixturesTests
 */
import { describe, expect, it } from 'vitest';
import { buildEditorPaperView } from '@/lib/editor-paper';
import { assertPaperDocument } from '@/lib/paper-document';
import {
  extractedPaperDocumentNoImages,
  mockPaperDocumentV1,
  resolveEditorFixture,
} from '@/mocks';

describe('editor fixtures', () => {
  it('keeps the original mock as the default fixture', () => {
    const fixture = resolveEditorFixture(null);

    expect(fixture.id).toBe('mock');
    expect(fixture.paper).toBe(mockPaperDocumentV1);
  });

  it('loads the extracted no-image paper as an explicit dev-only fixture', () => {
    const fixture = resolveEditorFixture('extracted-no-images');
    const document = assertPaperDocument(fixture.paper);
    const view = buildEditorPaperView(document);

    expect(fixture).toMatchObject({
      id: 'extracted-no-images',
      devOnly: true,
    });
    expect(fixture.paper).toBe(extractedPaperDocumentNoImages);
    expect(view.validationSummary).toMatchObject({
      totalSlots: 39,
      filledSlots: 39,
    });
    expect(view.validationSummary.warnings).toEqual([]);
    expect(view.sections.map((section) => section.marks)).toEqual([
      30, 25, 25,
    ]);
    expect(document.questions).toHaveLength(78);
  });

  it('falls back to the original mock for unknown fixture ids', () => {
    const fixture = resolveEditorFixture('missing-fixture');

    expect(fixture.id).toBe('mock');
    expect(fixture.paper).toBe(mockPaperDocumentV1);
  });
});
