/**
 * Editor-to-print handoff helpers.
 *
 * This module keeps the mock PDF flow's browser side effects out of the editor
 * page so the handoff can be tested without rendering the React shell.
 *
 * Patterns:
 * - Mock PDF generation opens a separate tab to preserve in-progress editor
 *   state in the original tab.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `src/lib/paper-document.ts`, `src/lib/mock-paper-document-storage.ts`.
 *
 * @module editorPrint
 */
import { saveMockPrintDocument } from './mock-paper-document-storage';
import { materializePaperDocument } from './paper-document';
import type { NormalizedPaperDocument } from './paper-document';
import type { PaperDocument } from '@/types';

interface OpenMockPrintDocumentOptions {
  saveDocument?: (paper: PaperDocument) => void;
  openWindow?: (url: string, target: string) => Window | null | void;
}

export function openMockPrintDocument(
  paperState: NormalizedPaperDocument,
  {
    saveDocument = saveMockPrintDocument,
    openWindow = window.open.bind(window),
  }: OpenMockPrintDocumentOptions = {},
) {
  const printDocument = materializePaperDocument(paperState);
  saveDocument(printDocument);
  openWindow(`/editor/${printDocument.paper.id}/print?mock=1`, '_blank');
}
