/**
 * Tests for persisted editor loading and failure states.
 *
 * @module editorPageTests
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { mockPaperDocumentV1 } from '@/mocks';
import type { PaperAnswerDocument } from '@/types';
import {
  reconcileAnswerDocumentForPaper,
  saveThenDownloadPdfPackage,
} from '@/lib/editor-download';
import { EditorActionBar, EditorDocumentStatus } from './editor.page';

describe('persisted editor document status', () => {
  it('shows a visible loading state while the saved paper is fetched', () => {
    const html = renderToStaticMarkup(<EditorDocumentStatus state="loading" />);

    expect(html).toContain('Loading saved paper');
  });

  it('shows the backend or contract error instead of falling back to a fixture', () => {
    const html = renderToStaticMarkup(
      <EditorDocumentStatus state="error" message="Paper not found." />,
    );

    expect(html).toContain('Unable to open paper');
    expect(html).toContain('Paper not found.');
  });
});

describe('editor final download flow', () => {
  function answerDocument(): PaperAnswerDocument {
    const slot = mockPaperDocumentV1.paper.sections[0].slots[0];
    return {
      schemaVersion: 'paper_answer_document.v1',
      paperId: mockPaperDocumentV1.paper.id,
      answersBySlotId: {
        [slot.id]: {
          slotId: slot.id,
          questionId: slot.selectedQuestionId ?? '',
          content: [{ type: 'paragraph', text: 'Answer' }],
          source: 'source',
          modified: false,
        },
      },
    };
  }

  it('downloads immediately when the draft is clean', async () => {
    const persist = vi.fn(async () => undefined);
    const download = vi.fn(async () => undefined);

    await saveThenDownloadPdfPackage({
      documentSnapshot: mockPaperDocumentV1,
      answerDocument: answerDocument(),
      dirty: false,
      persist,
      download,
    });

    expect(persist).not.toHaveBeenCalled();
    expect(download).toHaveBeenCalledWith(mockPaperDocumentV1);
  });

  it('saves a dirty draft before downloading the package', async () => {
    const persist = vi.fn(async () => undefined);
    const download = vi.fn(async () => undefined);

    await saveThenDownloadPdfPackage({
      documentSnapshot: mockPaperDocumentV1,
      answerDocument: answerDocument(),
      dirty: true,
      persist,
      download,
    });

    expect(persist).toHaveBeenCalledBefore(download);
    expect(download).toHaveBeenCalledWith(mockPaperDocumentV1);
  });

  it('does not download when the dirty save fails', async () => {
    const persist = vi.fn(async () => {
      throw new Error('save failed');
    });
    const download = vi.fn(async () => undefined);

    await expect(
      saveThenDownloadPdfPackage({
        documentSnapshot: mockPaperDocumentV1,
        answerDocument: answerDocument(),
        dirty: true,
        persist,
        download,
      }),
    ).rejects.toThrow('save failed');

    expect(download).not.toHaveBeenCalled();
  });

  it('marks the dirty draft saved before surfacing a download failure', async () => {
    const persist = vi.fn(async () => undefined);
    const download = vi.fn(async () => {
      throw new Error('download failed');
    });
    const onSaved = vi.fn();
    const answers = answerDocument();

    await expect(
      saveThenDownloadPdfPackage({
        documentSnapshot: mockPaperDocumentV1,
        answerDocument: answers,
        dirty: true,
        persist,
        download,
        onSaved,
      }),
    ).rejects.toThrow('download failed');

    expect(onSaved).toHaveBeenCalledWith(answers);
    expect(persist).toHaveBeenCalledBefore(download);
  });

  it('omits swapped-slot answer entries so the backend can rebuild bank answers', () => {
    const document = structuredClone(mockPaperDocumentV1);
    const slot = document.paper.sections[0].slots[0];
    const answers = answerDocument();
    answers.answersBySlotId[slot.id].questionId = 'q_stale_previous';

    const reconciled = reconcileAnswerDocumentForPaper(document, answers);

    expect(reconciled.answersBySlotId[slot.id]).toBeUndefined();
  });
});

describe('editor action bar', () => {
  const callbacks = {
    onUndo: () => undefined,
    onReview: () => undefined,
    onSave: () => undefined,
    onDownload: () => undefined,
  };

  it('surfaces unsaved changes in the V1 action bar', () => {
    const html = renderToStaticMarkup(
      <EditorActionBar
        persisted
        dirty
        actionState="idle"
        actionError=""
        warnings={[]}
        canUndo
        {...callbacks}
      />,
    );

    expect(html).toContain('Unsaved changes');
    expect(html).toContain('Save draft');
    expect(html).not.toContain('Approve');
  });

  it('summarizes validation warnings without showing approval controls', () => {
    const html = renderToStaticMarkup(
      <EditorActionBar
        persisted
        dirty={false}
        actionState="saved"
        actionError=""
        warnings={['Slot 1 has no selected question.']}
        canUndo={false}
        {...callbacks}
      />,
    );

    expect(html).toContain('1 validation warning');
    expect(html).toContain('Slot 1 has no selected question.');
    expect(html).toContain('<details');
    expect(html).not.toContain('Approve');
  });

  it('shows saving state while dirty changes are being persisted', () => {
    const html = renderToStaticMarkup(
      <EditorActionBar
        persisted
        dirty
        actionState="saving"
        actionError=""
        warnings={[]}
        canUndo={false}
        {...callbacks}
      />,
    );

    expect(html).toContain('Saving...');
    expect(html).not.toContain('Unsaved changes');
  });

  it('disables production actions for demo papers but keeps preview available', () => {
    const html = renderToStaticMarkup(
      <EditorActionBar
        persisted={false}
        dirty={false}
        actionState="idle"
        actionError=""
        warnings={[]}
        canUndo={false}
        {...callbacks}
      />,
    );

    expect(html).toContain('Demo paper · actions unavailable');
    expect(html).not.toContain('Approve');
    expect(html).not.toContain('Review paper');
    expect(html).toContain('Preview');
    expect(html).toMatch(
      /<button(?![^>]*disabled="")[^>]*title="Run a sample paper review"/,
    );
  });
});
