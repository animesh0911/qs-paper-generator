/**
 * Dev fixture for the extracted no-image PaperDocumentV1 snapshot.
 *
 * This module keeps the complete extracted paper separate from the smaller
 * editor mock so exact-count tests and default editor behavior remain stable.
 *
 * Patterns:
 * - The raw JSON is vendored beside this module so Docker/Vite can resolve it.
 * - Runtime validation happens at the editor boundary via `assertPaperDocument`.
 *
 * Where it fits:
 * - Used by: `src/mocks/editor-fixtures.ts`.
 * - Uses: `PaperDocumentV1`.
 *
 * @module extractedPaperDocumentNoImagesMock
 */
import extractedPaperDocumentNoImagesJson from './extracted-paper-document-no-images.json';
import type { PaperDocument } from '@/types';

export const extractedPaperDocumentNoImages =
  extractedPaperDocumentNoImagesJson as PaperDocument;
