/**
 * Copy-to-clipboard control for a single paper Slot.
 *
 * Lets a teacher lift a question's printed text out of the editor (e.g. to
 * paste into search or another document) without selecting across the canvas.
 *
 * Patterns:
 * - Marked `data-editor-chrome` so print/export styling strips it like the
 *   rest of the editor chrome.
 * - Copy text is supplied by the caller via `editorSlotClipboardText` so the
 *   button stays presentational and does not reach into the view model.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `lucide-react`, `src/lib/utils`.
 *
 * @module QuestionCopyButton
 */
import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { cn } from '@/lib/utils';

export function QuestionCopyButton({
  displayNumber,
  text,
}: {
  displayNumber: string;
  text: string;
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be denied (insecure context / permissions); leave
      // the control in its idle state rather than claiming a copy that failed.
      setCopied(false);
    }
  }

  return (
    <button
      type="button"
      data-editor-chrome
      className={cn(
        'inline-flex items-center gap-1 rounded-sm px-1 py-0.5 text-muted-foreground transition-colors',
        'hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
      )}
      aria-label={`Copy question ${displayNumber}`}
      title="Copy question text"
      onClick={(event) => {
        event.stopPropagation();
        void handleCopy();
      }}
    >
      {copied ? (
        <Check className="h-3.5 w-3.5" aria-hidden="true" />
      ) : (
        <Copy className="h-3.5 w-3.5" aria-hidden="true" />
      )}
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}
