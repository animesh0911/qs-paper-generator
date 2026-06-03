/**
 * Dev-only fixture registry for the mock-backed editor route.
 *
 * The editor remains mock-first while complete extracted-paper snapshots are
 * staged behind explicit query params for visual verification.
 *
 * Patterns:
 * - `mock` is always available and remains the default.
 * - Extracted paper fixtures are DEV-only until promoted to a backend/API path.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `src/mocks`.
 *
 * @module editorFixtures
 */
import type { PaperDocument } from '@/types';
import { extractedPaperDocumentNoImages } from './extracted-paper-document-no-images.mock';
import { mockPaperDocumentV1 } from './paper-document-v1.mock';

export type EditorFixtureId = 'mock' | 'extracted-no-images';

interface EditorFixture {
  id: EditorFixtureId;
  paper: PaperDocument;
  devOnly: boolean;
}

const editorFixtures: Record<EditorFixtureId, EditorFixture> = {
  mock: {
    id: 'mock',
    paper: mockPaperDocumentV1,
    devOnly: false,
  },
  'extracted-no-images': {
    id: 'extracted-no-images',
    paper: extractedPaperDocumentNoImages,
    devOnly: true,
  },
};

export function resolveEditorFixture(fixtureId: string | null): EditorFixture {
  const requestedFixture = fixtureId
    ? editorFixtures[fixtureId as EditorFixtureId]
    : undefined;
  const fixture = requestedFixture ?? editorFixtures.mock;

  if (fixture.devOnly && !import.meta.env.DEV) {
    return editorFixtures.mock;
  }

  return fixture;
}
