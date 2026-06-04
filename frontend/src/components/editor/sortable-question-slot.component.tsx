/**
 * Sortable wrapper for a paper Slot row.
 *
 * Keeps drag-and-drop mechanics local to the editor chrome while the page owns
 * the canonical order-zone state transition.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `@dnd-kit/sortable`.
 *
 * @module SortableQuestionSlot
 */
import type { ReactNode } from 'react';
import { GripVertical } from 'lucide-react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { cn } from '@/lib/utils';

export function SortableQuestionSlot({
  slotId,
  displayNumber,
  orderZoneId,
  reorderEnabled = true,
  selected,
  hovered,
  children,
  onClick,
  onFocus,
  onMouseEnter,
  onMouseLeave,
}: {
  slotId: string;
  displayNumber: string;
  orderZoneId: string;
  reorderEnabled?: boolean;
  selected: boolean;
  hovered: boolean;
  children: ReactNode;
  onClick: () => void;
  onFocus: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const {
    attributes,
    isDragging,
    listeners,
    setActivatorNodeRef,
    setNodeRef,
    transform,
    transition,
  } = useSortable({
    id: slotId,
    data: { orderZoneId },
    disabled: !reorderEnabled,
  });

  return (
    <div
      ref={setNodeRef}
      data-question-slot
      tabIndex={0}
      aria-label={`Question ${displayNumber}`}
      onClick={onClick}
      onFocus={onFocus}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      className={cn(
        'relative grid cursor-text grid-cols-[3.25rem_minmax(0,1fr)_5rem] gap-3 px-4 py-4 outline-none transition-colors duration-150 ease-out focus-visible:ring-2 focus-visible:ring-ring max-sm:grid-cols-[2.5rem_minmax(0,1fr)_4.25rem] max-sm:px-3',
        hovered && !selected && 'bg-secondary/45',
        selected && 'bg-secondary/70 ring-1 ring-inset ring-ring',
        isDragging &&
          'z-20 bg-background opacity-90 shadow-[0_10px_28px_rgba(15,23,42,0.16)]',
      )}
    >
      <div className="flex items-start gap-1 font-semibold">
        <button
          ref={setActivatorNodeRef}
          type="button"
          data-editor-chrome
          className={cn(
            'mt-1 inline-flex h-5 w-5 flex-none items-center justify-center rounded-sm text-muted-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            reorderEnabled
              ? 'cursor-grab hover:bg-secondary hover:text-foreground active:cursor-grabbing'
              : 'cursor-not-allowed opacity-40',
          )}
          aria-label={`Drag question ${displayNumber}`}
          title={
            reorderEnabled
              ? 'Drag to reorder within this section'
              : 'Reorder is disabled for this slot'
          }
          disabled={!reorderEnabled}
          onClick={(event) => event.stopPropagation()}
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
        <span>{displayNumber}.</span>
      </div>
      {children}
    </div>
  );
}
