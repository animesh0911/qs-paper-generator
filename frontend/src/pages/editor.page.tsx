/**
 * Mock-backed PaperDocumentV1 editor shell.
 *
 * This page loads the issue #21 mock, maps it into a print-faithful paper
 * view model, and renders the V1 shell around the paper: top bar, outline
 * rail, inspector, BlockNote-backed question regions, and bottom chat.
 *
 * Patterns:
 * - The mocked `PaperDocumentV1` is canonical; BlockNote only renders editable
 *   region surfaces for the shell.
 * - Editor chrome is marked with `data-editor-chrome` so print/export styling
 *   can remove it without hiding paper content.
 *
 * Where it fits:
 * - Used by: `src/App.tsx` at `/editor`.
 * - Uses: `src/lib/editor-paper.ts`, `src/mocks/paper-document-v1.mock.ts`.
 *
 * @module EditorPage
 */
import { useMemo } from 'react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
import type { PartialBlock } from '@blocknote/core';
import {
  CheckCircle2,
  Download,
  FileCheck2,
  Lock,
  MessageSquareText,
  RotateCcw,
  Save,
  SearchCheck,
} from 'lucide-react';
import '@blocknote/mantine/style.css';
import { mockPaperDocumentV1 } from '@/mocks';
import { buildEditorPaperView } from '@/lib/editor-paper';
import { assertPaperDocument } from '@/lib/paper-document';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

function QuestionRegionEditor({ blocks }: { blocks: PartialBlock[] }) {
  const editor = useCreateBlockNote(
    {
      animations: false,
      initialContent: blocks,
    },
    [blocks],
  );

  return (
    <BlockNoteView
      editor={editor}
      editable={false}
      formattingToolbar={false}
      linkToolbar={false}
      slashMenu={false}
      sideMenu={false}
      filePanel={false}
      tableHandles={false}
      emojiPicker={false}
      comments={false}
      className="qpg-question-blocknote"
    />
  );
}

export default function EditorPage() {
  const document = useMemo(() => assertPaperDocument(mockPaperDocumentV1), []);
  const view = useMemo(() => buildEditorPaperView(document), [document]);

  return (
    <div className="editor-shell min-h-screen bg-secondary text-foreground">
      <header
        data-editor-chrome
        className="sticky top-0 z-20 flex min-h-14 items-center justify-between gap-3 border-b bg-background px-4 py-2 max-lg:flex-col max-lg:items-start"
      >
        <div className="min-w-0">
          <p className="text-sm font-semibold leading-5">{view.title}</p>
          <p className="text-xs text-muted-foreground">
            {view.paperMeta.join(' · ')}
          </p>
        </div>
        <div className="flex max-w-full flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="max-sm:flex-1 max-sm:basis-[calc(50%-0.25rem)]"
            aria-label="Undo last action"
          >
            <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
            Undo
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="max-sm:flex-1 max-sm:basis-[calc(50%-0.25rem)]"
          >
            <Save className="mr-2 h-4 w-4" aria-hidden="true" />
            Save draft
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="max-sm:flex-1 max-sm:basis-[calc(50%-0.25rem)]"
          >
            <FileCheck2 className="mr-2 h-4 w-4" aria-hidden="true" />
            Review paper
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="max-sm:flex-1 max-sm:basis-[calc(50%-0.25rem)]"
          >
            <Download className="mr-2 h-4 w-4" aria-hidden="true" />
            Download PDF
          </Button>
          <Button size="sm" className="max-sm:flex-1 max-sm:basis-full">
            <CheckCircle2 className="mr-2 h-4 w-4" aria-hidden="true" />
            Approve
          </Button>
        </div>
      </header>

      <div className="grid min-h-[calc(100vh-3.5rem)] grid-cols-[12rem_minmax(0,1fr)_14rem] gap-4 px-4 pb-36 pt-4 max-lg:grid-cols-1 max-lg:[&_.editor-inspector]:hidden max-lg:[&_.editor-left-rail]:static max-sm:px-3">
        <aside
          data-editor-chrome
          className="editor-left-rail sticky top-[4.5rem] h-[calc(100vh-6rem)] overflow-auto rounded-lg border bg-background p-3 max-lg:h-auto"
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

        <main className="flex justify-center">
          <article className="paper-canvas w-full max-w-[44rem] bg-background px-12 py-10 text-[15px] leading-7 shadow-none 2xl:max-w-[52rem] max-sm:px-5 max-sm:py-8">
            <header className="mb-6 text-center">
              <h1 className="text-lg font-bold leading-7">{view.title}</h1>
              {view.subtitle && (
                <p className="text-sm font-medium">{view.subtitle}</p>
              )}
              <div className="mt-4 flex flex-wrap justify-center gap-x-6 gap-y-1 text-sm">
                {view.paperMeta.slice(1).map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            </header>

            {view.instructions.length > 0 && (
              <section className="mb-6 border p-4">
                <h2 className="mb-2 text-sm font-semibold">
                  General Instructions
                </h2>
                <ol className="list-decimal space-y-1 pl-5 text-sm leading-6">
                  {view.instructions.map((instruction) => (
                    <li key={instruction}>{instruction}</li>
                  ))}
                </ol>
              </section>
            )}

            <div className="space-y-6">
              {view.sections.map((section) => (
                <section
                  id={`section-${section.sectionId}`}
                  key={section.sectionId}
                  className="paper-section border"
                >
                  <header className="border-b px-4 py-3 text-center">
                    <h2 className="text-base font-bold">{section.title}</h2>
                    {section.subtitle && (
                      <p className="text-sm">{section.subtitle}</p>
                    )}
                    {section.instructions && (
                      <p className="mt-2 text-sm leading-6">
                        {section.instructions}
                      </p>
                    )}
                  </header>

                  <div className="divide-y">
                    {section.slots.map((slot) => (
                      <div
                        key={slot.slotId}
                        className="grid grid-cols-[2.5rem_minmax(0,1fr)_5rem] gap-3 px-4 py-4 max-sm:grid-cols-[1.75rem_minmax(0,1fr)_4.25rem] max-sm:px-3"
                      >
                        <div className="font-semibold">
                          {slot.displayNumber}.
                        </div>
                        <div>
                          <QuestionRegionEditor blocks={slot.blockNoteBlocks} />
                          <div
                            data-editor-chrome
                            className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground"
                          >
                            <span>{slot.questionType.replace(/_/g, ' ')}</span>
                            {slot.locked && (
                              <span className="inline-flex items-center gap-1">
                                <Lock className="h-3 w-3" aria-hidden="true" />
                                Locked
                              </span>
                            )}
                            {slot.modifiedFromSource && (
                              <span>Modified from source</span>
                            )}
                          </div>
                        </div>
                        <div className="text-right text-sm font-medium">
                          [{slot.marksLabel}]
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </article>
        </main>

        <aside
          data-editor-chrome
          className="editor-inspector sticky top-[4.5rem] h-[calc(100vh-6rem)] rounded-lg border bg-background p-4"
        >
          <h2 className="text-sm font-semibold">Inspector</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Select a question to inspect source, chapter, difficulty, and safe
            swap options.
          </p>
        </aside>
      </div>

      <div
        data-editor-chrome
        className="fixed inset-x-0 bottom-0 z-30 border-t bg-background/95 px-4 py-3 backdrop-blur"
      >
        <div className="mx-auto flex max-w-3xl items-center gap-3 rounded-lg border bg-background p-2">
          <MessageSquareText
            className="h-5 w-5 flex-none text-muted-foreground"
            aria-hidden="true"
          />
          <input
            aria-label="Ask about this paper"
            className={cn(
              'min-w-0 flex-1 bg-transparent px-1 text-sm outline-none',
              'placeholder:text-muted-foreground',
            )}
            placeholder="Ask about this paper"
          />
          <Button size="sm">Ask</Button>
        </div>
      </div>
    </div>
  );
}
