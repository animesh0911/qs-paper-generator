/**
 * PaperDocumentV1 format renderer registry.
 *
 * The backend selects known frontend renderers by `format.id`. This module is
 * the single registry seam used by editor and print surfaces so unsupported
 * format IDs fail loudly instead of being interpreted as CBSE by accident.
 *
 * Patterns:
 * - Registry keys are contract `format.id` values, not React component names.
 * - Unsupported formats expose a short user-safe message plus developer detail.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`, `PaperDocumentView`.
 * - Uses: CBSE compact editor and print view-model builders.
 *
 * @module paperFormatRenderers
 */
import {
  buildEditorPaperView,
  type BuildEditorPaperViewOptions,
} from './editor-paper';
import type { buildSimplePaperView } from '@/components/coverage/paper-document-view/build-simple-paper-view';
import {
  CBSE_COMPACT_FORMAT_ID,
  cbseCompactRenderer,
} from './paper-format-renderers/cbse-compact-renderer';
import type { PaperDocument } from '@/types';

export { CBSE_COMPACT_FORMAT_ID };

export interface PaperFormatRenderer {
  formatId: string;
  label: string;
  buildEditorPaperView: (
    document: PaperDocument,
    options?: BuildEditorPaperViewOptions,
  ) => ReturnType<typeof buildEditorPaperView>;
  buildPrintPaperView: typeof buildSimplePaperView;
}

export class UnsupportedPaperFormatError extends Error {
  readonly userMessage =
    'This paper format is not supported by the editor yet.';

  constructor(readonly formatId: string) {
    super(`Unsupported PaperDocument format.id "${formatId}".`);
    this.name = 'UnsupportedPaperFormatError';
  }
}

const rendererByFormatId: Record<string, PaperFormatRenderer> = {
  [CBSE_COMPACT_FORMAT_ID]: cbseCompactRenderer,
};

export type PaperFormatRendererResult =
  | { ok: true; renderer: PaperFormatRenderer }
  | { ok: false; error: UnsupportedPaperFormatError };

export function getPaperFormatRenderer(formatId: string): PaperFormatRenderer {
  const renderer = rendererByFormatId[formatId];
  if (!renderer) {
    throw new UnsupportedPaperFormatError(formatId);
  }
  return renderer;
}

export function getPaperFormatRendererResult(
  formatId: string,
): PaperFormatRendererResult {
  try {
    return { ok: true, renderer: getPaperFormatRenderer(formatId) };
  } catch (error) {
    if (error instanceof UnsupportedPaperFormatError) {
      return { ok: false, error };
    }
    throw error;
  }
}
