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
import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  pointerWithin,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type CollisionDetection,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import {
  CheckCircle2,
  Download,
  FileCheck2,
  Lock,
  MessageSquareText,
  RotateCcw,
  Save,
} from 'lucide-react';
import '@blocknote/mantine/style.css';
import { mockPaperDocumentV1 } from '@/mocks';
import {
  approvePaper,
  downloadPaperPdf,
  savePaperDraft,
} from '@/lib/api';
import { buildEditorPaperView } from '@/lib/editor-paper';
import {
  assertPaperDocument,
  buildOrderZones,
  commitStructuredPaperAction,
  normalizePaperDocument,
  reorderSlotWithinOrderZone,
  restoreSlotSource,
  setPaperChromeText,
  setSlotLockState,
  setSlotSelectedQuestion,
  setSlotRegionOverride,
  undoStructuredPaperAction,
  type StructuredPaperUndoEntry,
} from '@/lib/paper-document';
import {
  EditorAlternativesOverlay,
  EditorInspector,
  EditorOutlineRail,
  PaperChromeEditor,
  QuestionActionRail,
  QuestionRegionEditor,
  SortableQuestionSlot,
  type AlternativesIntent,
  type InspectorMode,
} from '@/components/editor';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { ContentItem } from '@/types';

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
  const [undoEntry, setUndoEntry] = useState<StructuredPaperUndoEntry | null>(
    null,
  );
  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const [activeRailSlotId, setActiveRailSlotId] = useState<string | null>(null);
  const [selectedChromeBlockId, setSelectedChromeBlockId] = useState<
    string | null
  >(null);
  const [inspectorMode, setInspectorMode] = useState<InspectorMode>('info');
  const [inspectorHighlighted, setInspectorHighlighted] = useState(false);
  const [alternativesIntent, setAlternativesIntent] =
    useState<AlternativesIntent>('swap');
  const [alternativesOverlayOpen, setAlternativesOverlayOpen] = useState(false);
  const [chatValue, setChatValue] = useState('');
  const [hoveredSlotId, setHoveredSlotId] = useState<string | null>(null);
  const [hoveredSectionId, setHoveredSectionId] = useState<string | null>(null);
  const [dragNotice, setDragNotice] = useState<string | null>(null);
  const [persistenceStatus, setPersistenceStatus] = useState<string | null>(
    null,
  );
  const [persistenceBusy, setPersistenceBusy] = useState(false);
  const chatInputRef = useRef<HTMLInputElement>(null);
  const alternativesOpenerRef = useRef<HTMLElement | null>(null);
  const inspectorHighlightTimeoutRef = useRef<number | null>(null);
  const blockedCrossSectionDropRef = useRef(false);
  const dragSensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 6,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  const view = useMemo(
    () =>
      buildEditorPaperView(paperState.document, {
        slotEditsById: paperState.slotEditsById,
        alternativesIntentBySlotId: selectedSlotId
          ? { [selectedSlotId]: alternativesIntent }
          : undefined,
      }),
    [alternativesIntent, paperState, selectedSlotId],
  );
  const orderZones = useMemo(() => buildOrderZones(paperState), [paperState]);
  const slotZoneById = useMemo(
    () =>
      Object.fromEntries(
        orderZones.flatMap((zone) =>
          zone.orderedItemIds.map((slotId) => [String(slotId), zone.zoneId]),
        ),
      ),
    [orderZones],
  );
  const sameSectionCollisionDetection = useMemo<CollisionDetection>(
    () => (args) => {
      const activeZoneId = slotZoneById[String(args.active.id)];
      if (!activeZoneId) return closestCenter(args);

      const pointerCollision = pointerWithin(args).find(
        (collision) => collision.id !== args.active.id,
      );
      const pointerZoneId = pointerCollision
        ? slotZoneById[String(pointerCollision.id)]
        : undefined;
      if (pointerZoneId && pointerZoneId !== activeZoneId) {
        blockedCrossSectionDropRef.current = true;
        return [];
      }

      blockedCrossSectionDropRef.current = false;
      return closestCenter({
        ...args,
        droppableContainers: args.droppableContainers.filter(
          (container) => slotZoneById[String(container.id)] === activeZoneId,
        ),
      });
    },
    [slotZoneById],
  );

  const selectedSlot = view.sections
    .flatMap((section) => section.slots)
    .find((slot) => slot.slotId === selectedSlotId);
  const selectedQuestion = selectedSlot?.questionBlockTree.questionId
    ? paperState.questionsById[selectedSlot.questionBlockTree.questionId]
    : undefined;

  useEffect(() => {
    function handleOutsidePointerDown(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (
        target.closest(
          '[data-question-slot], .qpg-question-action-rail, .editor-inspector, .editor-alternatives-overlay, .editor-chat-footer, .editor-left-rail, header',
        )
      ) {
        return;
      }
      setActiveRailSlotId(null);
      setSelectedSlotId(null);
      setSelectedChromeBlockId(null);
    }

    window.document.addEventListener('pointerdown', handleOutsidePointerDown);
    return () => {
      window.document.removeEventListener(
        'pointerdown',
        handleOutsidePointerDown,
      );
    };
  }, []);

  useEffect(() => {
    return () => {
      if (inspectorHighlightTimeoutRef.current !== null) {
        window.clearTimeout(inspectorHighlightTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!dragNotice) return undefined;
    const timeoutId = window.setTimeout(() => setDragNotice(null), 2400);
    return () => window.clearTimeout(timeoutId);
  }, [dragNotice]);

  function commitStructuredAction(nextState: typeof paperState) {
    const result = commitStructuredPaperAction(paperState, nextState);
    setPaperState(result.state);
    setUndoEntry(result.undoEntry);
  }

  function handleUndo() {
    const result = undoStructuredPaperAction(paperState, undoEntry);
    setPaperState(result.state);
    setUndoEntry(result.undoEntry);
  }

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
    const nextState = restoreSlotSource(paperState, slotId);
    commitStructuredAction(nextState);
  }

  function handleSelectSlot(slotId: string) {
    setSelectedChromeBlockId(null);
    setSelectedSlotId(slotId);
    setActiveRailSlotId(slotId);
  }

  function handleSelectChromeBlock(regionKey: string) {
    setSelectedSlotId(null);
    setActiveRailSlotId(null);
    setSelectedChromeBlockId(regionKey);
  }

  function handleShowInfo(slotId: string) {
    handleSelectSlot(slotId);
    setInspectorMode('info');
    setInspectorHighlighted(true);
    if (inspectorHighlightTimeoutRef.current !== null) {
      window.clearTimeout(inspectorHighlightTimeoutRef.current);
    }
    inspectorHighlightTimeoutRef.current = window.setTimeout(() => {
      setInspectorHighlighted(false);
      inspectorHighlightTimeoutRef.current = null;
    }, 900);
  }

  function handleShowAlternatives(slotId: string, intent: AlternativesIntent) {
    handleSelectSlot(slotId);
    setAlternativesIntent(intent);
    setInspectorMode('alternatives');
    openAlternativesOverlay();
  }

  function handleToggleLock(slotId: string, locked: boolean) {
    handleSelectSlot(slotId);
    const nextState = setSlotLockState(paperState, slotId, !locked);
    commitStructuredAction(nextState);
  }

  function handleUseAlternative(slotId: string, questionId: string) {
    const slot = view.sections
      .flatMap((section) => section.slots)
      .find((candidate) => candidate.slotId === slotId);
    if (!slot) return;

    if (
      slot.modifiedFromSource &&
      !window.confirm(
        'Replacing this question will clear manual edits for this slot. Continue?',
      )
    ) {
      return;
    }

    handleSelectSlot(slotId);
    const nextState = setSlotSelectedQuestion(paperState, slotId, questionId);
    commitStructuredAction(nextState);
    setAlternativesOverlayOpen(false);
  }

  function handleDragStart() {
    blockedCrossSectionDropRef.current = false;
    setDragNotice(null);
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) {
      if (blockedCrossSectionDropRef.current) {
        setDragNotice('Questions can only be reordered within their section.');
      }
      blockedCrossSectionDropRef.current = false;
      return;
    }
    if (active.id === over.id) return;

    const slotId = String(active.id);
    const activePosition = getSlotOrderPosition(slotId);
    const overPosition = getSlotOrderPosition(String(over.id));
    if (!activePosition || !overPosition) return;

    const result = reorderSlotWithinOrderZone(paperState, {
      slotId,
      fromZoneId: activePosition.zone.zoneId,
      toZoneId: overPosition.zone.zoneId,
      toIndex: overPosition.index,
    });
    if (result.success) {
      handleSelectSlot(slotId);
      commitStructuredAction(result.state);
    } else {
      setDragNotice(result.error);
    }
    blockedCrossSectionDropRef.current = false;
  }

  function getSlotOrderPosition(slotId: string) {
    for (const zone of orderZones) {
      const index = zone.orderedItemIds.indexOf(slotId);
      if (index !== -1) return { zone, index };
    }
    return undefined;
  }

  function handleAskQuestion(slotId: string, displayNumber: string) {
    handleSelectSlot(slotId);
    setChatValue(`Question ${displayNumber}: `);
    window.setTimeout(() => chatInputRef.current?.focus(), 0);
  }

  async function handleSaveDraft() {
    await runPersistenceAction('Draft saved.', () =>
      savePaperDraft(paperState.document),
    );
  }

  async function handleApprovePaper() {
    if (
      view.validationSummary.warnings.length > 0 &&
      !window.confirm(
        'This paper still has warnings. Approve the final paper anyway?',
      )
    ) {
      return;
    }

    await runPersistenceAction('Paper approved.', () =>
      approvePaper(paperState.document),
    );
  }

  async function handleDownloadPdf() {
    await runPersistenceAction('PDF download started.', async () => {
      await savePaperDraft(paperState.document);
      await downloadPaperPdf(paperState.document.paper.paperId);
    });
  }

  async function runPersistenceAction(
    successMessage: string,
    action: () => Promise<unknown>,
  ) {
    setPersistenceBusy(true);
    setPersistenceStatus(null);
    try {
      await action();
      setPersistenceStatus(successMessage);
    } catch (error) {
      setPersistenceStatus(
        error instanceof Error ? error.message : 'Paper update failed.',
      );
    } finally {
      setPersistenceBusy(false);
    }
  }

  function openAlternativesOverlay() {
    alternativesOpenerRef.current =
      window.document.activeElement instanceof HTMLElement
        ? window.document.activeElement
        : null;
    setAlternativesOverlayOpen(true);
  }

  function closeAlternativesOverlay() {
    setAlternativesOverlayOpen(false);
    window.setTimeout(() => alternativesOpenerRef.current?.focus(), 0);
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
            disabled={!undoEntry}
            onClick={handleUndo}
          >
            <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
            Undo
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="max-sm:flex-1 max-sm:basis-[calc(50%-0.25rem)]"
            disabled={persistenceBusy}
            onClick={handleSaveDraft}
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
            disabled={persistenceBusy}
            onClick={handleDownloadPdf}
          >
            <Download className="mr-2 h-4 w-4" aria-hidden="true" />
            Download PDF
          </Button>
          <Button
            size="sm"
            className="max-sm:flex-1 max-sm:basis-full"
            disabled={persistenceBusy}
            onClick={handleApprovePaper}
          >
            <CheckCircle2 className="mr-2 h-4 w-4" aria-hidden="true" />
            Approve
          </Button>
        </div>
      </header>
      {persistenceStatus && (
        <div
          data-editor-chrome
          role="status"
          className="fixed right-4 top-16 z-30 max-w-sm rounded-md border bg-background px-3 py-2 text-sm shadow-[0_8px_24px_rgba(15,23,42,0.12)]"
        >
          {persistenceStatus}
        </div>
      )}

      <div className="grid min-h-[calc(100vh-3.5rem)] grid-cols-[minmax(12rem,14vw)_minmax(0,1fr)_minmax(14rem,16vw)] gap-4 px-4 pb-36 pt-4 max-lg:grid-cols-1 max-lg:[&_.editor-inspector]:hidden max-lg:[&_.editor-left-rail]:static max-sm:px-3">
        <EditorOutlineRail view={view} />

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

            <DndContext
              sensors={dragSensors}
              collisionDetection={sameSectionCollisionDetection}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
            >
              <div className="space-y-6">
                {view.sections.map((section) => {
                  const subtitleBlock = section.subtitleBlock;
                  const instructionsBlock = section.instructionsBlock;

                  return (
                    <section
                      id={`section-${section.sectionId}`}
                      key={section.sectionId}
                      onMouseEnter={() =>
                        setHoveredSectionId(section.sectionId)
                      }
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
                            selectedChromeBlockId ===
                            section.titleBlock.regionKey
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
                                selectedChromeBlockId ===
                                subtitleBlock.regionKey
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

                      <SortableContext
                        items={section.slots.map((slot) => slot.slotId)}
                        strategy={verticalListSortingStrategy}
                      >
                        <div className="divide-y">
                          {section.slots.map((slot) => (
                            <SortableQuestionSlot
                              key={slot.slotId}
                              slotId={slot.slotId}
                              displayNumber={slot.displayNumber}
                              orderZoneId={`section:${section.sectionId}`}
                              selected={selectedSlotId === slot.slotId}
                              hovered={hoveredSlotId === slot.slotId}
                              onClick={() => handleSelectSlot(slot.slotId)}
                              onFocus={() => handleSelectSlot(slot.slotId)}
                              onMouseEnter={() => {
                                setHoveredSlotId(slot.slotId);
                                setHoveredSectionId(section.sectionId);
                              }}
                              onMouseLeave={() => setHoveredSlotId(null)}
                            >
                              <div>
                                <div className="space-y-1">
                                  {slot.questionBlockTree.children.map(
                                    (region) => (
                                      <div
                                        key={`${slot.slotId}:${region.regionKey}:${slot.questionBlockTree.questionId}:${slot.modifiedFromSource}`}
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
                                    ),
                                  )}
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
                              {activeRailSlotId === slot.slotId && (
                                <QuestionActionRail
                                  locked={slot.locked}
                                  onInfo={() => handleShowInfo(slot.slotId)}
                                  onAlternatives={(intent) =>
                                    handleShowAlternatives(slot.slotId, intent)
                                  }
                                  onToggleLock={() =>
                                    handleToggleLock(slot.slotId, slot.locked)
                                  }
                                  onAsk={() =>
                                    handleAskQuestion(
                                      slot.slotId,
                                      slot.displayNumber,
                                    )
                                  }
                                />
                              )}
                            </SortableQuestionSlot>
                          ))}
                        </div>
                      </SortableContext>
                    </section>
                  );
                })}
              </div>
            </DndContext>
          </article>
        </main>

        <EditorInspector
          selectedSlot={selectedSlot}
          selectedQuestion={selectedQuestion}
          inspectorMode={inspectorMode}
          alternativesIntent={alternativesIntent}
          onInspectorModeChange={setInspectorMode}
          onShowAllAlternatives={() => setAlternativesIntent('swap')}
          onOpenAlternatives={openAlternativesOverlay}
          onRestoreSelectedSlot={handleRestoreSelectedSlot}
          highlighted={inspectorHighlighted}
        />
      </div>

      {alternativesOverlayOpen && selectedSlot && selectedQuestion && (
        <div className="editor-alternatives-overlay">
          <EditorAlternativesOverlay
            selectedSlot={selectedSlot}
            selectedQuestion={selectedQuestion}
            alternativesIntent={alternativesIntent}
            onAlternativesIntentChange={setAlternativesIntent}
            onClose={closeAlternativesOverlay}
            onUseAlternative={(questionId) =>
              handleUseAlternative(selectedSlot.slotId, questionId)
            }
          />
        </div>
      )}

      {dragNotice && (
        <div
          data-editor-chrome
          role="status"
          className="fixed right-4 top-16 z-30 max-w-sm rounded-md border bg-background px-3 py-2 text-sm shadow-[0_8px_24px_rgba(15,23,42,0.12)]"
        >
          {dragNotice}
        </div>
      )}

      <div
        data-editor-chrome
        className="editor-chat-footer fixed bottom-3 left-1/2 z-30 w-[min(calc(100vw-2rem),48rem)] -translate-x-1/2"
      >
        <div className="flex items-center gap-3 rounded-lg border bg-background/95 p-2 shadow-[0_8px_24px_rgba(15,23,42,0.12)] backdrop-blur">
          <MessageSquareText
            className="h-5 w-5 flex-none text-muted-foreground"
            aria-hidden="true"
          />
          <input
            ref={chatInputRef}
            aria-label="Ask about this paper"
            className={cn(
              'min-w-0 flex-1 bg-transparent px-1 text-sm outline-none',
              'placeholder:text-muted-foreground',
            )}
            value={chatValue}
            placeholder={
              selectedSlot
                ? `Ask about question ${selectedSlot.displayNumber}`
                : 'Ask about this paper'
            }
            onChange={(event) => setChatValue(event.target.value)}
          />
          <Button size="sm">Ask</Button>
        </div>
      </div>
    </div>
  );
}
