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

/**
 * Resolves once every `<img>` currently in the document has finished loading
 * (successfully or not). The print routes gate `data-print-ready` on this so
 * the backend's Chromium never snapshots a paper whose diagrams are still
 * streaming in — a broken image prints as a blank gap otherwise.
 */
export function waitForDocumentImages(doc: Document = document): Promise<void> {
  const images = Array.from(doc.images);
  if (images.length === 0) return Promise.resolve();
  return Promise.all(
    images.map((image) =>
      image.complete
        ? Promise.resolve()
        : new Promise<void>((resolve) => {
            image.addEventListener('load', () => resolve(), { once: true });
            image.addEventListener('error', () => resolve(), { once: true });
          }),
    ),
  ).then(() => undefined);
}
