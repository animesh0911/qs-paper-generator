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
import { useEffect, useMemo, useRef, useState } from 'react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';
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
import {
  blockNoteBlocksToContentItems,
  blockNoteBlocksToText,
  buildEditorPaperView,
  type EditorPaperChromeBlock,
  type EditorQuestionRegionBlock,
} from '@/lib/editor-paper';
import {
  assertPaperDocument,
  normalizePaperDocument,
  restoreSlotSource,
  setPaperChromeText,
  setSlotRegionOverride,
} from '@/lib/paper-document';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { ContentItem } from '@/types';

function QuestionRegionEditor({
  region,
  editable,
  onCommit,
}: {
  region: EditorQuestionRegionBlock;
  editable: boolean;
  onCommit: (content: ContentItem[]) => void;
}) {
  if (!editable) {
    return (
      <div className="qpg-question-blocknote qpg-question-region-text">
        {region.text}
      </div>
    );
  }

  return <ActiveQuestionRegionEditor region={region} onCommit={onCommit} />;
}

function ActiveQuestionRegionEditor({
  region,
  onCommit,
}: {
  region: EditorQuestionRegionBlock;
  onCommit: (content: ContentItem[]) => void;
}) {
  const mountedRef = useRef(false);
  const suppressInitialChangeRef = useRef(true);
  const latestContentRef = useRef(region.content);
  const editor = useCreateBlockNote(
    {
      animations: false,
      initialContent: region.blockNoteBlocks,
    },
    [region.regionKey, region.text],
  );

  useEffect(() => {
    mountedRef.current = true;
    suppressInitialChangeRef.current = true;
    latestContentRef.current = region.content;
    const timeoutId = window.setTimeout(() => {
      suppressInitialChangeRef.current = false;
    }, 0);

    return () => {
      mountedRef.current = false;
      window.clearTimeout(timeoutId);
    };
  }, [region.content, region.regionKey, region.text]);

  function handleCommit() {
    onCommit(latestContentRef.current);
  }

  return (
    <div onBlurCapture={handleCommit}>
      <BlockNoteView
        editor={editor}
        editable
        onChange={(changedEditor) => {
          if (!mountedRef.current || suppressInitialChangeRef.current) return;
          latestContentRef.current = blockNoteBlocksToContentItems(
            changedEditor.document,
          );
        }}
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
    </div>
  );
}

function PaperChromeEditor({
  block,
  editable,
  className,
  onCommit,
}: {
  block: EditorPaperChromeBlock;
  editable: boolean;
  className?: string;
  onCommit: (text: string) => void;
}) {
  if (!editable) {
    return (
      <div className={cn('qpg-paper-chrome-text', className)}>
        {block.text.split('\n').map((line, index) => (
          <p key={`${block.regionKey}:${index}`}>{line}</p>
        ))}
      </div>
    );
  }

  return (
    <ActivePaperChromeEditor
      block={block}
      className={className}
      onCommit={onCommit}
    />
  );
}

function ActivePaperChromeEditor({
  block,
  className,
  onCommit,
}: {
  block: EditorPaperChromeBlock;
  className?: string;
  onCommit: (text: string) => void;
}) {
  const mountedRef = useRef(false);
  const suppressInitialChangeRef = useRef(true);
  const latestTextRef = useRef(block.text);
  const editor = useCreateBlockNote(
    {
      animations: false,
      initialContent: block.blockNoteBlocks,
    },
    [block.regionKey, block.text],
  );

  useEffect(() => {
    mountedRef.current = true;
    suppressInitialChangeRef.current = true;
    latestTextRef.current = block.text;
    const timeoutId = window.setTimeout(() => {
      suppressInitialChangeRef.current = false;
    }, 0);

    return () => {
      mountedRef.current = false;
      window.clearTimeout(timeoutId);
    };
  }, [block.regionKey, block.text]);

  function handleCommit() {
    onCommit(latestTextRef.current);
  }

  return (
    <div onBlurCapture={handleCommit}>
      <BlockNoteView
        editor={editor}
        editable
        onChange={(changedEditor) => {
          if (!mountedRef.current || suppressInitialChangeRef.current) return;
          latestTextRef.current = blockNoteBlocksToText(
            changedEditor.document,
          ).join('\n');
        }}
        formattingToolbar={false}
        linkToolbar={false}
        slashMenu={false}
        sideMenu={false}
        filePanel={false}
        tableHandles={false}
        emojiPicker={false}
        comments={false}
        className={cn('qpg-question-blocknote', className)}
      />
    </div>
  );
}

function contentItemsEqual(left: ContentItem[], right: ContentItem[]) {
  return JSON.stringify(left) === JSON.stringify(right);
}

export default function EditorPage() {
  const document = useMemo(() => assertPaperDocument(mockPaperDocumentV1), []);
  const initialPaperState = useMemo(
    () => normalizePaperDocument(document),
    [document],
  );
  const [paperState, setPaperState] = useState(initialPaperState);
  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const [selectedChromeBlockId, setSelectedChromeBlockId] = useState<
    string | null
  >(null);
  const [hoveredSlotId, setHoveredSlotId] = useState<string | null>(null);
  const [hoveredSectionId, setHoveredSectionId] = useState<string | null>(null);
  const [restoreVersionBySlotId, setRestoreVersionBySlotId] = useState<
    Record<string, number>
  >({});
  const view = useMemo(
    () =>
      buildEditorPaperView(paperState.document, {
        slotEditsById: paperState.slotEditsById,
      }),
    [paperState],
  );

  const selectedSlot = view.sections
    .flatMap((section) => section.slots)
    .find((slot) => slot.slotId === selectedSlotId);
  const selectedQuestion = selectedSlot?.questionBlockTree.questionId
    ? paperState.questionsById[selectedSlot.questionBlockTree.questionId]
    : undefined;

  function handleRegionChange(
    slotId: string,
    regionKey: string,
    currentContent: ContentItem[],
    content: ContentItem[],
  ) {
    if (contentItemsEqual(currentContent, content)) return;
    setPaperState((currentState) =>
      setSlotRegionOverride(currentState, slotId, regionKey, content),
    );
  }

  function handlePaperChromeChange(regionKey: string, text: string) {
    setPaperState((currentState) =>
      setPaperChromeText(currentState, regionKey, text),
    );
  }

  function handleRestoreSelectedSlot() {
    if (!selectedSlotId) return;
    const slotId = selectedSlotId;
    setPaperState((currentState) => restoreSlotSource(currentState, slotId));
    setRestoreVersionBySlotId((currentVersions) => ({
      ...currentVersions,
      [slotId]: (currentVersions[slotId] ?? 0) + 1,
    }));
  }

  function handleSelectSlot(slotId: string) {
    setSelectedChromeBlockId(null);
    setSelectedSlotId(slotId);
  }

  function handleSelectChromeBlock(regionKey: string) {
    setSelectedSlotId(null);
    setSelectedChromeBlockId(regionKey);
  }

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

      <div className="grid min-h-[calc(100vh-3.5rem)] grid-cols-[minmax(12rem,14vw)_minmax(0,1fr)_minmax(14rem,16vw)] gap-4 px-4 pb-36 pt-4 max-lg:grid-cols-1 max-lg:[&_.editor-inspector]:hidden max-lg:[&_.editor-left-rail]:static max-sm:px-3">
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

        <main className="flex justify-center max-lg:order-1">
          <article className="paper-canvas w-full max-w-[56rem] bg-background px-14 py-10 text-[15px] leading-7 shadow-none max-xl:px-10 max-lg:max-w-[48rem] max-sm:px-5 max-sm:py-8">
            <header className="mb-6 text-center">
              <div onClick={() => handleSelectChromeBlock('paper:title')}>
                <PaperChromeEditor
                  block={view.paperChromeBlocks[0]}
                  editable={selectedChromeBlockId === 'paper:title'}
                  className="qpg-paper-title"
                  onCommit={(text) =>
                    handlePaperChromeChange('paper:title', text)
                  }
                />
              </div>
              {view.subtitle && view.paperChromeBlocks[1] && (
                <div onClick={() => handleSelectChromeBlock('paper:subtitle')}>
                  <PaperChromeEditor
                    block={view.paperChromeBlocks[1]}
                    editable={selectedChromeBlockId === 'paper:subtitle'}
                    className="qpg-paper-subtitle"
                    onCommit={(text) =>
                      handlePaperChromeChange('paper:subtitle', text)
                    }
                  />
                </div>
              )}
              <div className="mt-4 flex flex-wrap justify-center gap-x-6 gap-y-1 text-sm">
                {view.paperMeta.slice(1).map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            </header>

            {view.instructionBlocks.length > 0 && (
              <section className="mb-8">
                <div className="space-y-1 text-sm leading-6">
                  {view.instructionBlocks.map((block) => (
                    <div
                      key={block.regionKey}
                      onClick={() => handleSelectChromeBlock(block.regionKey)}
                      className={cn(
                        'qpg-paper-chrome-hit rounded-sm transition-colors duration-150 ease-out hover:bg-secondary/45',
                        selectedChromeBlockId === block.regionKey &&
                          'bg-secondary/70 ring-1 ring-inset ring-ring',
                      )}
                    >
                      <PaperChromeEditor
                        block={block}
                        editable={selectedChromeBlockId === block.regionKey}
                        className={
                          block.blockType.includes('heading')
                            ? 'qpg-instruction-heading'
                            : 'qpg-instruction-line'
                        }
                        onCommit={(text) =>
                          handlePaperChromeChange(block.regionKey, text)
                        }
                      />
                    </div>
                  ))}
                </div>
              </section>
            )}

            <div className="space-y-6">
              {view.sections.map((section) => {
                const subtitleBlock = section.subtitleBlock;
                const instructionsBlock = section.instructionsBlock;

                return (
                  <section
                    id={`section-${section.sectionId}`}
                    key={section.sectionId}
                    onMouseEnter={() => setHoveredSectionId(section.sectionId)}
                    onMouseLeave={() => setHoveredSectionId(null)}
                    className={cn(
                      'paper-section border transition-colors duration-150 ease-out',
                      hoveredSectionId === section.sectionId &&
                        'bg-secondary/20',
                      section.slots.some(
                        (slot) => slot.slotId === selectedSlotId,
                      ) && 'ring-1 ring-inset ring-border',
                    )}
                  >
                    <header
                      className="border-b px-4 py-3 text-center"
                      onClick={() =>
                        handleSelectChromeBlock(section.titleBlock.regionKey)
                      }
                    >
                      <PaperChromeEditor
                        block={section.titleBlock}
                        editable={
                          selectedChromeBlockId === section.titleBlock.regionKey
                        }
                        className="qpg-section-title"
                        onCommit={(text) =>
                          handlePaperChromeChange(
                            section.titleBlock.regionKey,
                            text,
                          )
                        }
                      />
                      {subtitleBlock && (
                        <div
                          onClick={(event) => {
                            event.stopPropagation();
                            handleSelectChromeBlock(subtitleBlock.regionKey);
                          }}
                        >
                          <PaperChromeEditor
                            block={subtitleBlock}
                            editable={
                              selectedChromeBlockId === subtitleBlock.regionKey
                            }
                            className="qpg-section-subtitle"
                            onCommit={(text) =>
                              handlePaperChromeChange(
                                subtitleBlock.regionKey,
                                text,
                              )
                            }
                          />
                        </div>
                      )}
                      {instructionsBlock && (
                        <div
                          className="mt-2"
                          onClick={(event) => {
                            event.stopPropagation();
                            handleSelectChromeBlock(
                              instructionsBlock.regionKey,
                            );
                          }}
                        >
                          <PaperChromeEditor
                            block={instructionsBlock}
                            editable={
                              selectedChromeBlockId ===
                              instructionsBlock.regionKey
                            }
                            className="qpg-section-instructions"
                            onCommit={(text) =>
                              handlePaperChromeChange(
                                instructionsBlock.regionKey,
                                text,
                              )
                            }
                          />
                        </div>
                      )}
                    </header>

                    <div className="divide-y">
                      {section.slots.map((slot) => (
                        <div
                          key={slot.slotId}
                          onClick={() => handleSelectSlot(slot.slotId)}
                          onMouseEnter={() => {
                            setHoveredSlotId(slot.slotId);
                            setHoveredSectionId(section.sectionId);
                          }}
                          onMouseLeave={() => setHoveredSlotId(null)}
                          className={cn(
                            'grid cursor-text grid-cols-[2.5rem_minmax(0,1fr)_5rem] gap-3 px-4 py-4 outline-none transition-colors duration-150 ease-out max-sm:grid-cols-[1.75rem_minmax(0,1fr)_4.25rem] max-sm:px-3',
                            hoveredSlotId === slot.slotId &&
                              selectedSlotId !== slot.slotId &&
                              'bg-secondary/45',
                            selectedSlotId === slot.slotId &&
                              'bg-secondary/70 ring-1 ring-inset ring-ring',
                          )}
                        >
                          <div className="font-semibold">
                            {slot.displayNumber}.
                          </div>
                          <div>
                            <div className="space-y-1">
                              {slot.questionBlockTree.children.map((region) => (
                                <div
                                  key={`${slot.slotId}:${region.regionKey}:${restoreVersionBySlotId[slot.slotId] ?? 0}`}
                                  className="qpg-question-region flex items-start gap-1"
                                >
                                  {region.displayPrefix && (
                                    <span className="qpg-question-region-prefix select-none font-medium">
                                      {region.displayPrefix}
                                    </span>
                                  )}
                                  <div className="min-w-0 flex-1">
                                    <QuestionRegionEditor
                                      region={region}
                                      editable={
                                        selectedSlotId === slot.slotId &&
                                        region.editable
                                      }
                                      onCommit={(content) =>
                                        handleRegionChange(
                                          slot.slotId,
                                          region.regionKey,
                                          region.content,
                                          content,
                                        )
                                      }
                                    />
                                  </div>
                                  {region.displaySuffix && (
                                    <span className="qpg-question-region-suffix select-none text-xs text-muted-foreground">
                                      {region.displaySuffix}
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                            <div
                              data-editor-chrome
                              className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground"
                            >
                              <span>
                                {slot.questionType.replace(/_/g, ' ')}
                              </span>
                              {slot.locked && (
                                <span className="inline-flex items-center gap-1">
                                  <Lock
                                    className="h-3 w-3"
                                    aria-hidden="true"
                                  />
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
                );
              })}
            </div>
          </article>
        </main>

        <aside
          data-editor-chrome
          className="editor-inspector sticky top-[4.5rem] h-[calc(100vh-6rem)] rounded-lg border bg-background p-4"
        >
          <h2 className="text-sm font-semibold">Inspector</h2>
          {selectedSlot && selectedQuestion ? (
            <div className="mt-4 space-y-4 text-sm">
              <div>
                <p className="text-xs uppercase text-muted-foreground">
                  Question {selectedSlot.displayNumber}
                </p>
                <p className="mt-1 font-medium">
                  {selectedQuestion.metadata.chapterNames.join(', ')}
                </p>
                <p className="text-muted-foreground">
                  {selectedQuestion.metadata.topicNames?.join(', ') ??
                    selectedQuestion.metadata.difficulty}
                </p>
              </div>
              <dl className="space-y-2">
                <div>
                  <dt className="text-xs text-muted-foreground">Source</dt>
                  <dd>{selectedQuestion.source.sourceName}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Edit state</dt>
                  <dd>
                    {selectedSlot.modifiedFromSource
                      ? 'Modified from source'
                      : 'Original source text'}
                  </dd>
                </div>
              </dl>
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                disabled={!selectedSlot.modifiedFromSource}
                onMouseDown={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  handleRestoreSelectedSlot();
                }}
                onClick={(event) => {
                  event.stopPropagation();
                  handleRestoreSelectedSlot();
                }}
              >
                <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
                Restore original
              </Button>
            </div>
          ) : (
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Select a question to inspect source, chapter, difficulty, and safe
              swap options.
            </p>
          )}
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
