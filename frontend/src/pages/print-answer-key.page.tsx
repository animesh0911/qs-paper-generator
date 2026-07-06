/**
 * Print-only answer-key route for browser PDF generation.
 *
 * Fetches the saved editor draft payload and renders from its paper-local
 * `answer_document`; no editor rails, controls, provenance, or review state are
 * present in this surface.
 *
 * @module PrintAnswerKeyPage
 */
import { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { AnswerKeyPrintView } from '@/components/coverage/answer-key-print-view.component';
import { fetchEditorDraft } from '@/lib/api';
import { waitForDocumentImages } from '@/lib/print-paper';
import type { EditorDraftResponse } from '@/types';

export default function PrintAnswerKeyPage() {
  const { paperId } = useParams();
  const [searchParams] = useSearchParams();
  const [draft, setDraft] = useState<EditorDraftResponse | null>(null);
  const [assetsReady, setAssetsReady] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!paperId) return;
    fetchEditorDraft(paperId, searchParams.get('token'))
      .then(setDraft)
      .catch((err) => setError((err as Error).message));
  }, [paperId, searchParams]);

  // Mirror the paper print route: only signal readiness once every image has
  // settled, so the marking-scheme PDF never captures half-loaded figures.
  useEffect(() => {
    if (!draft) return;
    let cancelled = false;
    waitForDocumentImages().then(() => {
      if (!cancelled) setAssetsReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, [draft]);

  if (error) {
    return (
      <main className="print-status">Unable to render answer key: {error}</main>
    );
  }

  if (!draft) {
    return <main className="print-status">Loading answer key...</main>;
  }

  return (
    <main className="print-page" data-print-ready={assetsReady || undefined}>
      <AnswerKeyPrintView
        document={draft.document}
        answerDocument={draft.answer_document}
      />
    </main>
  );
}
