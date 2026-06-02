/**
 * Print route browser effect helpers.
 *
 * This module owns the native print scheduling policy for the browser print
 * route while keeping React page files component-only for Fast Refresh.
 *
 * Where it fits:
 * - Used by: `src/pages/print-paper.page.tsx`.
 * - Uses: `PaperDocumentV1`.
 *
 * @module printPaper
 */
import type { PaperDocument } from '@/types';

interface ScheduleMockPrintDialogOptions {
  paper: PaperDocument | null;
  isMockPrint: boolean;
  print?: () => void;
  setTimeout?: (callback: () => void, delay: number) => number;
  clearTimeout?: (timerId: number) => void;
}

export function scheduleMockPrintDialog({
  paper,
  isMockPrint,
  print = window.print.bind(window),
  setTimeout = window.setTimeout.bind(window),
  clearTimeout = window.clearTimeout.bind(window),
}: ScheduleMockPrintDialogOptions) {
  if (!paper || !isMockPrint) return undefined;

  const timerId = setTimeout(() => print(), 500);
  return () => clearTimeout(timerId);
}
