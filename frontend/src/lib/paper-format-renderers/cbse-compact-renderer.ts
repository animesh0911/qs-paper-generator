/**
 * CBSE compact Paper Format adapter.
 *
 * Owns the editor and print mappings for the
 * `cbse_science_class_10_board_compact_2026_v1` format id.
 *
 * @module cbseCompactRenderer
 */
import { buildSimplePaperView } from '@/components/coverage/paper-document-view/build-simple-paper-view';
import { buildEditorPaperView } from '@/lib/editor-paper';
import type { PaperFormatRenderer } from '@/lib/paper-format-renderers';

export const CBSE_COMPACT_FORMAT_ID =
  'cbse_science_class_10_board_compact_2026_v1';

export const cbseCompactRenderer: PaperFormatRenderer = {
  formatId: CBSE_COMPACT_FORMAT_ID,
  label: 'CBSE Class 10 Science compact',
  buildEditorPaperView,
  buildPrintPaperView: buildSimplePaperView,
};
