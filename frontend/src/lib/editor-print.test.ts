/**
 * Tests for editor-to-print handoff behavior.
 *
 * These tests pin the mock editor PDF flow so downloading a PDF does not
 * discard local editor state by navigating the active page.
 *
 * @module editorPrintTests
 */
import { describe, expect, it, vi } from 'vitest';
import { mockPaperDocumentV1 } from '@/mocks';
import {
  assertPaperDocument,
  normalizePaperDocument,
  setSlotRegionOverride,
} from './paper-document';
import { openMockPrintDocument } from './editor-print';

describe('editor print handoff', () => {
  it('opens the mock print route in a new tab so the editor stays mounted', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = normalizePaperDocument(document);
    const saveDocument = vi.fn();
    const openWindow = vi.fn();

    openMockPrintDocument(state, { saveDocument, openWindow });

    const savedDocument = saveDocument.mock.calls[0]?.[0];
    expect(savedDocument.paper.id).toBe(document.paper.id);
    expect(savedDocument.paper.sections[0].slots[0].selectedQuestionId).toBe(
      document.paper.sections[0].slots[0].selectedQuestionId,
    );
    expect(openWindow).toHaveBeenCalledWith(
      `/editor/${document.paper.id}/print?mock=1`,
      '_blank',
    );
  });

  it('saves manual Slot edits into the print document', () => {
    const document = assertPaperDocument(mockPaperDocumentV1);
    const state = setSlotRegionOverride(
      normalizePaperDocument(document),
      'slot_A_01',
      'stem',
      [{ type: 'paragraph', text: 'Edited question for print.' }],
    );
    const saveDocument = vi.fn();

    openMockPrintDocument(state, { saveDocument, openWindow: vi.fn() });

    const savedDocument = saveDocument.mock.calls[0]?.[0];
    expect(savedDocument.paper.sections[0].slots[0].overrides).toEqual({
      modified: true,
      regions: {
        stem: [{ type: 'paragraph', text: 'Edited question for print.' }],
      },
    });
  });
});
