/**
 * Stores the mock PaperDocumentV1 for frontend-only print rendering.
 *
 * This adapter is intentionally browser-local. It lets the mock-backed editor
 * hand the current edited contract to the print route without involving the
 * backend while the real API team works separately.
 *
 * Patterns:
 * - Session storage is used so stale mock papers do not survive browser
 *   restarts.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`, `src/pages/print-paper.page.tsx`.
 * - Uses: `PaperDocumentV1`.
 *
 * @module mockPaperDocumentStorage
 */
import type { PaperDocument } from '@/types';

const MOCK_PRINT_DOCUMENT_STORAGE_KEY = 'qpg_mock_print_document_v1';

export function saveMockPrintDocument(paper: PaperDocument) {
  window.sessionStorage.setItem(
    MOCK_PRINT_DOCUMENT_STORAGE_KEY,
    JSON.stringify(paper),
  );
}

export function loadMockPrintDocument(): PaperDocument | null {
  const rawDocument = window.sessionStorage.getItem(
    MOCK_PRINT_DOCUMENT_STORAGE_KEY,
  );
  if (!rawDocument) return null;

  try {
    return JSON.parse(rawDocument) as PaperDocument;
  } catch {
    return null;
  }
}
