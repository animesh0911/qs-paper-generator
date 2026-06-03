/**
 * Tests for the PaperDocumentV1 format renderer registry.
 *
 * These tests pin the public selection seam shared by editor and print routes:
 * backend `format.id` values choose known frontend renderers, and unsupported
 * values fail visibly instead of falling back to guessed CBSE layout.
 *
 * @module paperFormatRenderersTests
 */
import { describe, expect, it } from 'vitest';
import { mockPaperDocumentV1 } from '@/mocks';
import { assertPaperDocument } from './paper-document';
import {
  CBSE_COMPACT_FORMAT_ID,
  UnsupportedPaperFormatError,
  getPaperFormatRenderer,
  getPaperFormatRendererResult,
} from './paper-format-renderers';

describe('paper format renderer registry', () => {
  it('maps the CBSE compact format ID to the current editor and print renderer', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const renderer = getPaperFormatRenderer(document.format.id);
    const editorView = renderer.buildEditorPaperView(document);
    const printView = renderer.buildPrintPaperView(document);

    expect(document.format.id).toBe(CBSE_COMPACT_FORMAT_ID);
    expect(renderer.formatId).toBe(CBSE_COMPACT_FORMAT_ID);
    expect(renderer.label).toBe('CBSE Class 10 Science compact');
    expect(editorView.title).toBe('Science');
    expect(printView.sections[0].section.title).toBe('Section A');
  });

  it('fails loud with a user-safe message for unsupported format IDs', () => {
    expect(() => getPaperFormatRenderer('unknown_format_v1')).toThrow(
      UnsupportedPaperFormatError,
    );

    const result = getPaperFormatRendererResult('unknown_format_v1');

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error.message).toContain(
      'Unsupported PaperDocument format.id "unknown_format_v1"',
    );
    expect(result.error.userMessage).toBe(
      'This paper format is not supported by the editor yet.',
    );
  });
});
