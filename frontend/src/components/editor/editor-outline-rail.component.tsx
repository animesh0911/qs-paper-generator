/**
 * Left rail for Paper outline and validation status.
 *
 * The rail renders derived EditorPaperView data only; it does not inspect the
 * PaperDocumentV1 contract directly.
 *
 * Where it fits:
 * - Used by: `src/pages/editor.page.tsx`.
 * - Uses: `src/lib/editor-paper.ts`.
 *
 * @module EditorOutlineRail
 */
import { SearchCheck } from 'lucide-react';
import type { EditorPaperView } from '@/lib/editor-paper';

export function EditorOutlineRail({ view }: { view: EditorPaperView }) {
  return (
    <aside
      data-editor-chrome
      className="editor-left-rail sticky top-[4.5rem] h-[calc(100vh-6rem)] overflow-auto rounded-lg border bg-background p-3 max-lg:order-2 max-lg:h-auto"
    >
      <h2 className="mb-3 text-sm font-semibold">Paper outline</h2>
      <nav aria-label="Paper sections" className="space-y-1">
        {view.outline.map((item) => (
          <a
            key={item.sectionId}
            href={`#section-${item.sectionId}`}
            className="flex items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span>{item.title}</span>
            <span className="text-xs text-muted-foreground">
              {item.slotCount} q · {item.marks}m
            </span>
          </a>
        ))}
      </nav>

      <div className="mt-5 border-t pt-4">
        <h2 className="mb-3 text-sm font-semibold">Validation</h2>
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <div className="rounded-md bg-secondary p-2">
            <dt className="text-xs text-muted-foreground">Filled</dt>
            <dd className="font-semibold">
              {view.validationSummary.filledSlots}/
              {view.validationSummary.totalSlots}
            </dd>
          </div>
          <div className="rounded-md bg-secondary p-2">
            <dt className="text-xs text-muted-foreground">Locked</dt>
            <dd className="font-semibold">
              {view.validationSummary.lockedSlots}
            </dd>
          </div>
        </dl>
        {view.validationSummary.warnings.length === 0 ? (
          <p className="mt-3 flex items-center gap-2 text-sm text-emerald-700">
            <SearchCheck className="h-4 w-4" aria-hidden="true" />
            No structural warnings
          </p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm text-destructive">
            {view.validationSummary.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
