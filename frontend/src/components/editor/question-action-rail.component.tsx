/**
 * Floating action rail for the selected paper Slot.
 *
 * Keeps question-level commands and disabled replacement rules local to the
 * editor chrome, while the page owns the actual state transitions.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `src/components/editor/editor-types.ts`.
 *
 * @module QuestionActionRail
 */
import {
  Info,
  Lock,
  MessageSquareText,
  Pencil,
  Shuffle,
  Unlock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { AlternativesIntent } from './editor-types';

export function QuestionActionRail({
  locked,
  lockEnabled = true,
  swapEnabled = true,
  editEnabled = true,
  onEdit,
  onInfo,
  onAlternatives,
  onToggleLock,
  onAsk,
}: {
  locked: boolean;
  lockEnabled?: boolean;
  swapEnabled?: boolean;
  editEnabled?: boolean;
  onEdit: () => void;
  onInfo: () => void;
  onAlternatives: (intent: AlternativesIntent) => void;
  onToggleLock: () => void;
  onAsk: () => void;
}) {
  const replacementDisabledLabel = !swapEnabled
    ? 'Swapping is disabled for this slot.'
    : 'Unlock this question before choosing replacements.';

  return (
    <div
      data-editor-chrome
      className="qpg-question-action-rail absolute right-[calc(100%+0.5rem)] top-3 z-10 flex w-28 flex-col gap-1 rounded-lg border bg-background p-1 shadow-[0_8px_24px_rgba(15,23,42,0.12)] max-lg:left-auto max-lg:right-3"
      onClick={(event) => event.stopPropagation()}
    >
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="justify-start px-2 text-xs"
        title={
          editEnabled
            ? 'Edit this question'
            : 'Editing is disabled for this slot.'
        }
        aria-label="Edit question"
        disabled={!editEnabled}
        onClick={onEdit}
      >
        <Pencil className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
        Edit
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="justify-start px-2 text-xs"
        title="Show question info"
        aria-label="Show question info"
        onClick={onInfo}
      >
        <Info className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
        Info
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="justify-start px-2 text-xs"
        title={
          locked || !swapEnabled
            ? replacementDisabledLabel
            : 'Show swap alternatives'
        }
        aria-label="Show swap alternatives"
        disabled={locked || !swapEnabled}
        onClick={() => onAlternatives('swap')}
      >
        <Shuffle className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
        Swap
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="justify-start px-2 text-xs"
        title={
          lockEnabled
            ? locked
              ? 'Unlock question'
              : 'Lock question'
            : 'Locking is disabled for this slot.'
        }
        aria-label={locked ? 'Unlock question' : 'Lock question'}
        disabled={!lockEnabled}
        onClick={onToggleLock}
      >
        {locked ? (
          <Unlock className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
        ) : (
          <Lock className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
        )}
        {locked ? 'Unlock' : 'Lock'}
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="justify-start px-2 text-xs"
        title="Ask about this question"
        aria-label="Ask about this question"
        onClick={onAsk}
      >
        <MessageSquareText className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
        Ask
      </Button>
    </div>
  );
}
