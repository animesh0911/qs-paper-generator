/**
 * Tests for persisted editor loading and failure states.
 *
 * @module editorPageTests
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { EditorDocumentStatus } from './editor.page';

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
