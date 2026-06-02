/**
 * Print-only paper route for browser PDF generation.
 *
 * The backend opens this route with a token query from Playwright. It fetches
 * the saved PaperDocumentV1 and renders only the paper surface: no dashboard,
 * controls, rails, or editor-only metadata.
 *
 * Patterns:
 * - The token query is used only for this request; normal auth state stays in
 *   localStorage through `useAuth`.
 *
 * Where it fits:
 * - Used by: backend `PaperPdfView`
 * - Uses: fetchPaperDocument, PaperDocumentView
 *
 * @module PrintPaperPage
 */
import { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { PaperDocumentView } from '@/components/coverage/paper-document-view';
import { fetchPaperDocument } from '@/lib/api';
import { loadMockPrintDocument } from '@/lib/mock-paper-document-storage';
import { scheduleMockPrintDialog } from '@/lib/print-paper';
import { mockPaperDocumentV1 } from '@/mocks';
import type { PaperDocument } from '@/types';

export default function PrintPaperPage() {
  const { paperId } = useParams();
  const [searchParams] = useSearchParams();
  const [paper, setPaper] = useState<PaperDocument | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!paperId) return;
    if (searchParams.get('mock') === '1') {
      setPaper(loadMockPrintDocument() ?? mockPaperDocumentV1);
      return;
    }
    fetchPaperDocument(paperId, searchParams.get('token'))
      .then(setPaper)
      .catch((err) => setError((err as Error).message));
  }, [paperId, searchParams]);

  useEffect(
    () =>
      scheduleMockPrintDialog({
        paper,
        isMockPrint: searchParams.get('mock') === '1',
      }),
    [paper, searchParams],
  );

  if (error) {
    return (
      <main className="print-status">Unable to render paper: {error}</main>
    );
  }

  if (!paper) {
    return <main className="print-status">Loading paper...</main>;
  }

  return (
    <main className="print-page" data-print-ready="true">
      <PaperDocumentView paper={paper} mode="print" />
    </main>
  );
}
