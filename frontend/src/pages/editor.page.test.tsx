/**
 * Tests for persisted editor loading and failure states.
 *
 * @module editorPageTests
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
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

describe('editor action bar', () => {
  const callbacks = {
    onUndo: () => undefined,
    onSave: () => undefined,
    onDownload: () => undefined,
    onApprove: () => undefined,
  };

  it('surfaces unsaved changes and blocks approval until they are saved', () => {
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
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>.*Approve/);
  });

  it('summarizes validation warnings and blocks approval', () => {
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
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>.*Approve/);
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

  it('clearly disables production actions for demo papers', () => {
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
    expect(html).toContain('Review is unavailable');
  });
});
