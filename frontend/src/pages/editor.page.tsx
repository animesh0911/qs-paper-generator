/**
 * PaperDocumentV1 editor shell for persisted papers and explicit demo fixtures.
 *
 * `/editor/:paperId` fetches and validates the authenticated teacher's saved
 * paper. `/editor` remains the explicit fixture-backed development/demo route.
 *
 * Patterns:
 * - The loaded `PaperDocumentV1` is canonical; BlockNote only renders editable
 *   region surfaces for the shell.
 * - Editor chrome is marked with `data-editor-chrome` so print/export styling
 *   can remove it without hiding paper content.
 *
 * Where it fits:
 * - Used by: `src/App.tsx` at `/editor` and `/editor/:paperId`.
 * - Uses: `src/lib/api.ts`, `src/lib/editor-paper.ts`, `src/mocks`.
 *
 * @module EditorPage
 */
import { useEffect, useMemo, useState } from 'react';
import { DndContext } from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileCheck2,
  Lock,
  MessageSquareText,
  RotateCcw,
  Save,
} from 'lucide-react';
import { useParams, useSearchParams } from 'react-router-dom';
import '@blocknote/mantine/style.css';
import { resolveEditorFixture } from '@/mocks';
import {
  approvePaper,
  downloadPaperPdf,
  fetchPaperDocument,
  persistDraft,
} from '@/lib/api';
import {
  getPaperFormatRendererResult,
  type PaperFormatRenderer,
} from '@/lib/paper-format-renderers';
import { assertPaperDocument } from '@/lib/paper-document';
import { useEditorWorkspace } from '@/hooks/useEditorWorkspace.hook';
import {
  EditorAlternativesOverlay,
  EditorInspector,
  EditorOutlineRail,
  PaperChromeEditor,
  QuestionActionRail,
  QuestionRegionEditor,
  SortableQuestionSlot,
} from '@/components/editor';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { PaperDocument } from '@/types';

function toRoman(value: number) {
  const numerals = [
    'I',
    'II',
    'III',
    'IV',
    'V',
    'VI',
    'VII',
    'VIII',
    'IX',
    'X',
  ];
  return numerals[value - 1] ?? String(value);
}

export default function EditorPage() {
  const { paperId } = useParams();

  if (paperId) {
    return <PersistedEditorPage paperId={paperId} />;
  }

  return <DemoEditorPage />;
}

function PersistedEditorPage({ paperId }: { paperId: string }) {
  const [document, setDocument] = useState<PaperDocument | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setDocument(null);
    setError('');
    fetchPaperDocument(paperId)
      .then((nextDocument) => {
        if (active) setDocument(nextDocument);
      })
      .catch((reason) => {
        if (active) setError((reason as Error).message);
      });
    return () => {
      active = false;
    };
  }, [paperId]);

  if (error) {
    return <EditorDocumentStatus state="error" message={error} />;
  }
  if (!document) {
    return <EditorDocumentStatus state="loading" />;
  }

  return <ResolvedEditorPage document={document} documentKey={document.paper.id} />;
}

function DemoEditorPage() {
  const [searchParams] = useSearchParams();
  const selectedFixture = useMemo(
    () => resolveEditorFixture(searchParams.get('fixture')),
    [searchParams],
  );
  const document = useMemo(
    () => assertPaperDocument(selectedFixture.paper),
    [selectedFixture],
  );
  return (
    <ResolvedEditorPage
      document={document}
      documentKey={`fixture:${selectedFixture.id}`}
    />
  );
}

function ResolvedEditorPage({
  document,
  documentKey,
}: {
  document: PaperDocument;
  documentKey: string;
}) {
  const rendererResult = useMemo(
    () => getPaperFormatRendererResult(document.format.id),
    [document.format.id],
  );

  if (!rendererResult.ok) {
    return <UnsupportedPaperFormatNotice message={rendererResult.error} />;
  }

  return (
    <EditorPageWorkspace
      document={document}
      renderer={rendererResult.renderer}
      selectedFixtureId={documentKey}
      persisted={!documentKey.startsWith('fixture:')}
    />
  );
}

export function EditorDocumentStatus({
  state,
  message,
}: {
  state: 'loading' | 'error';
  message?: string;
}) {
  return (
    <main className="grid min-h-screen place-items-center bg-secondary px-4 text-foreground">
      <section className="w-full max-w-xl rounded-md border bg-background p-6">
        <h1 className="text-base font-semibold">
          {state === 'loading' ? 'Loading saved paper...' : 'Unable to open paper'}
        </h1>
        {message && <p className="mt-2 text-sm text-muted-foreground">{message}</p>}
      </section>
    </main>
  );
}

function UnsupportedPaperFormatNotice({
  message,
}: {
  message: { userMessage: string; message: string };
}) {
  return (
    <main className="grid min-h-screen place-items-center bg-secondary px-4 text-foreground">
      <section className="w-full max-w-xl rounded-md border bg-background p-6">
        <h1 className="text-base font-semibold">{message.userMessage}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{message.message}</p>
      </section>
    </main>
  );
}

function EditorPageWorkspace({
  document,
  renderer,
  selectedFixtureId,
  persisted,
}: {
  document: PaperDocument;
  renderer: PaperFormatRenderer;
  selectedFixtureId: string;
  persisted: boolean;
}) {
  const {
    activeRailSlotId,
    alternativesIntent,
    alternativesOverlayOpen,
    chatInputRef,
    chatValue,
    closeAlternativesOverlay,
    dragNotice,
    dragSensors,
    handleAskQuestion,
    handleDeletePaperChrome,
    handleDragEnd,
    handleDragStart,
    handlePaperChromeChange,
    handleRegionChange,
    handleRestoreSelectedSlot,
    handleSelectChromeBlock,
    handleSelectSlot,
    handleShowAlternatives,
    handleShowInfo,
    handleToggleLock,
    handleUndo,
    handleUseAlternative,
    hoveredSectionId,
    hoveredSlotId,
    inspectorHighlighted,
    inspectorMode,
    openAlternativesOverlay,
    paperState,
    sameSectionCollisionDetection,
    selectedChromeBlockId,
    selectedQuestion,
    selectedSlot,
    selectedSlotId,
    setAlternativesIntent,
    setChatValue,
    setHoveredSectionId,
    setHoveredSlotId,
    setInspectorMode,
    undoEntry,
    view,
  } = useEditorWorkspace({ document, renderer, selectedFixtureId });
  const [lastSavedDocument, setLastSavedDocument] = useState(document);
  const [actionState, setActionState] = useState<
    'idle' | 'saving' | 'saved' | 'approving' | 'approved' | 'error'
  >('idle');
  const [actionError, setActionError] = useState('');
  const dirty =
    JSON.stringify(paperState.document) !== JSON.stringify(lastSavedDocument);
  const warnings = view.validationSummary.warnings;

  async function runAction(action: 'save' | 'approve' | 'download') {
    if (!persisted) return;
    const documentSnapshot = structuredClone(paperState.document);
    setActionError('');
    setActionState(action === 'approve' ? 'approving' : 'saving');
    try {
      if (action === 'approve') {
        await approvePaper(documentSnapshot);
        setLastSavedDocument(documentSnapshot);
        setActionState('approved');
      } else {
        await persistDraft(documentSnapshot);
        setLastSavedDocument(documentSnapshot);
        setActionState('saved');
        if (action === 'download') await downloadPaperPdf(documentSnapshot);
      }
    } catch (reason) {
      setActionError((reason as Error).message);
      setActionState('error');
    }
  }

  const seriesBlock = view.chromeBlocks.find(
    (block) => block.blockType === 'series',
  );
  const setBlock = view.chromeBlocks.find((block) => block.blockType === 'set');
  const paperCodeBlock = view.chromeBlocks.find(
    (block) => block.blockType === 'paper_code',
  );
  const subjectLabelBlock = view.chromeBlocks.find(
    (block) => block.blockType === 'subject_label',
  );
  const rollNumberBlock = view.chromeBlocks.find(
    (block) => block.blockType === 'roll_number',
  );
  const timeAllowedBlock = view.chromeBlocks.find(
    (block) => block.blockType === 'paper_meta_left',
  );
  const maximumMarksBlock = view.chromeBlocks.find(
    (block) => block.blockType === 'paper_meta_right',
  );
  const noteBlocks = view.instructionBlocks.filter(
    (block) => block.blockType === 'note',
  );
  const generalInstructionBlocks = view.instructionBlocks.filter(
    (block) => block.blockType === 'general_instruction',
  );

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
        <EditorActionBar
          persisted={persisted}
          dirty={dirty}
          actionState={actionState}
          actionError={actionError}
          warnings={warnings}
          canUndo={Boolean(undoEntry)}
          onUndo={handleUndo}
          onSave={() => void runAction('save')}
          onDownload={() => void runAction('download')}
          onApprove={() => void runAction('approve')}
        />
      </header>

      <div className="grid min-h-[calc(100vh-3.5rem)] grid-cols-[minmax(12rem,14vw)_minmax(0,1fr)_minmax(14rem,16vw)] gap-4 px-4 pb-36 pt-4 max-lg:grid-cols-1 max-lg:[&_.editor-inspector]:order-2 max-lg:[&_.editor-left-rail]:static max-sm:px-3">
        <EditorOutlineRail view={view} />

        <main className="flex justify-center max-lg:order-1">
          <article className="paper-canvas editor-paper-sheet w-full bg-background shadow-none max-sm:px-5 max-sm:py-8">
            <header className="editor-paper-masthead">
              <div className="paper-topline">
                {seriesBlock ? (
                  <div
                    className="paper-series"
                    onClick={() =>
                      handleSelectChromeBlock(seriesBlock.regionKey)
                    }
                  >
                    <span>Series : </span>
                    <PaperChromeEditor
                      block={seriesBlock}
                      editable={
                        selectedChromeBlockId === seriesBlock.regionKey &&
                        seriesBlock.editCapabilities.text
                      }
                      className="qpg-paper-inline-chrome"
                      onCommit={(text) =>
                        handlePaperChromeChange(seriesBlock.regionKey, text)
                      }
                      onDelete={() =>
                        handleDeletePaperChrome(seriesBlock.regionKey)
                      }
                    />
                  </div>
                ) : (
                  <div />
                )}
                <div className="paper-code-stack">
                  <div className="paper-barcode" aria-hidden="true" />
                  {setBlock && (
                    <div
                      className="paper-set"
                      onClick={() =>
                        handleSelectChromeBlock(setBlock.regionKey)
                      }
                    >
                      <PaperChromeEditor
                        block={setBlock}
                        editable={
                          selectedChromeBlockId === setBlock.regionKey &&
                          setBlock.editCapabilities.text
                        }
                        className="qpg-paper-inline-chrome"
                        onCommit={(text) =>
                          handlePaperChromeChange(setBlock.regionKey, text)
                        }
                        onDelete={() =>
                          handleDeletePaperChrome(setBlock.regionKey)
                        }
                      />
                    </div>
                  )}
                </div>
              </div>

              <div className="paper-identity-row">
                <div className="paper-roll">
                  <div>रोल नं.</div>
                  <div>Roll No.</div>
                  <div
                    className="paper-roll-blank"
                    onClick={() =>
                      rollNumberBlock &&
                      handleSelectChromeBlock(rollNumberBlock.regionKey)
                    }
                  >
                    {rollNumberBlock && (
                      <PaperChromeEditor
                        block={rollNumberBlock}
                        editable={
                          selectedChromeBlockId === rollNumberBlock.regionKey &&
                          rollNumberBlock.editCapabilities.text
                        }
                        className="qpg-paper-roll-editor"
                        onCommit={(text) =>
                          handlePaperChromeChange(
                            rollNumberBlock.regionKey,
                            text,
                          )
                        }
                        onDelete={() =>
                          handleDeletePaperChrome(rollNumberBlock.regionKey)
                        }
                      />
                    )}
                  </div>
                </div>
                <div
                  className="paper-code-box"
                  onClick={() =>
                    paperCodeBlock &&
                    handleSelectChromeBlock(paperCodeBlock.regionKey)
                  }
                >
                  <span>प्रश्न-पत्र कोड</span>
                  <strong>Q.P. Code</strong>
                  {paperCodeBlock && (
                    <PaperChromeEditor
                      block={paperCodeBlock}
                      editable={
                        selectedChromeBlockId === paperCodeBlock.regionKey &&
                        paperCodeBlock.editCapabilities.text
                      }
                      className="qpg-paper-code-value"
                      onCommit={(text) =>
                        handlePaperChromeChange(paperCodeBlock.regionKey, text)
                      }
                      onDelete={() =>
                        handleDeletePaperChrome(paperCodeBlock.regionKey)
                      }
                    />
                  )}
                </div>
              </div>

              <div className="paper-title-block">
                {subjectLabelBlock && (
                  <div
                    onClick={() =>
                      handleSelectChromeBlock(subjectLabelBlock.regionKey)
                    }
                  >
                    <PaperChromeEditor
                      block={subjectLabelBlock}
                      editable={
                        selectedChromeBlockId === subjectLabelBlock.regionKey &&
                        subjectLabelBlock.editCapabilities.text
                      }
                      className="paper-title-local"
                      onCommit={(text) =>
                        handlePaperChromeChange(
                          subjectLabelBlock.regionKey,
                          text,
                        )
                      }
                      onDelete={() =>
                        handleDeletePaperChrome(subjectLabelBlock.regionKey)
                      }
                    />
                  </div>
                )}
                <div onClick={() => handleSelectChromeBlock('paper:title')}>
                  <PaperChromeEditor
                    block={view.paperChromeBlocks[0]}
                    editable={selectedChromeBlockId === 'paper:title'}
                    className="qpg-paper-title editor-paper-title"
                    onCommit={(text) =>
                      handlePaperChromeChange('paper:title', text)
                    }
                    onDelete={() => handleDeletePaperChrome('paper:title')}
                  />
                </div>
                {view.subtitle && view.paperChromeBlocks[1] && (
                  <div
                    onClick={() => handleSelectChromeBlock('paper:subtitle')}
                  >
                    <PaperChromeEditor
                      block={view.paperChromeBlocks[1]}
                      editable={selectedChromeBlockId === 'paper:subtitle'}
                      className="qpg-paper-subtitle editor-paper-subtitle"
                      onCommit={(text) =>
                        handlePaperChromeChange('paper:subtitle', text)
                      }
                      onDelete={() => handleDeletePaperChrome('paper:subtitle')}
                    />
                  </div>
                )}
              </div>

              <div className="paper-meta-grid">
                {timeAllowedBlock ? (
                  <div
                    onClick={() =>
                      handleSelectChromeBlock(timeAllowedBlock.regionKey)
                    }
                  >
                    <PaperChromeEditor
                      block={timeAllowedBlock}
                      editable={
                        selectedChromeBlockId === timeAllowedBlock.regionKey &&
                        timeAllowedBlock.editCapabilities.text
                      }
                      className="qpg-paper-chrome-text editor-paper-meta-text"
                      onCommit={(text) =>
                        handlePaperChromeChange(
                          timeAllowedBlock.regionKey,
                          text,
                        )
                      }
                      onDelete={() =>
                        handleDeletePaperChrome(timeAllowedBlock.regionKey)
                      }
                    />
                  </div>
                ) : (
                  <span>Time allowed : 3 hours</span>
                )}
                {maximumMarksBlock ? (
                  <div
                    onClick={() =>
                      handleSelectChromeBlock(maximumMarksBlock.regionKey)
                    }
                  >
                    <PaperChromeEditor
                      block={maximumMarksBlock}
                      editable={
                        selectedChromeBlockId === maximumMarksBlock.regionKey &&
                        maximumMarksBlock.editCapabilities.text
                      }
                      className="qpg-paper-chrome-text editor-paper-meta-text"
                      onCommit={(text) =>
                        handlePaperChromeChange(
                          maximumMarksBlock.regionKey,
                          text,
                        )
                      }
                      onDelete={() =>
                        handleDeletePaperChrome(maximumMarksBlock.regionKey)
                      }
                    />
                  </div>
                ) : (
                  <span>
                    Maximum Marks : {paperState.document.paper.totalMarks}
                  </span>
                )}
              </div>
            </header>

            {view.instructionBlocks.length > 0 && (
              <section className="editor-paper-instructions">
                {noteBlocks.length > 0 && (
                  <div className="paper-note-table">
                    <h2>नोट / NOTE</h2>
                    {noteBlocks.map((block, index) => (
                      <div key={block.regionKey} className="paper-note-row">
                        <span>({toRoman(index + 1)})</span>
                        <div
                          onClick={() =>
                            handleSelectChromeBlock(block.regionKey)
                          }
                          className={cn(
                            'qpg-paper-chrome-hit rounded-sm transition-colors duration-150 ease-out hover:bg-secondary/45',
                            selectedChromeBlockId === block.regionKey &&
                              'bg-secondary/70 ring-1 ring-inset ring-ring',
                          )}
                        >
                          <PaperChromeEditor
                            block={block}
                            editable={
                              selectedChromeBlockId === block.regionKey &&
                              block.editCapabilities.text
                            }
                            className="qpg-instruction-line"
                            onCommit={(text) =>
                              handlePaperChromeChange(block.regionKey, text)
                            }
                            onDelete={() =>
                              handleDeletePaperChrome(block.regionKey)
                            }
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {generalInstructionBlocks.length > 0 && (
                  <div className="paper-general-instructions">
                    <h2>General Instructions :</h2>
                    <p>
                      Read the following instructions carefully and follow them
                      :
                    </p>
                    {generalInstructionBlocks.map((block, index) => (
                      <div key={block.regionKey} className="paper-general-row">
                        <span>({toRoman(index + 1).toLowerCase()})</span>
                        <div
                          onClick={() =>
                            handleSelectChromeBlock(block.regionKey)
                          }
                          className={cn(
                            'qpg-paper-chrome-hit rounded-sm transition-colors duration-150 ease-out hover:bg-secondary/45',
                            selectedChromeBlockId === block.regionKey &&
                              'bg-secondary/70 ring-1 ring-inset ring-ring',
                          )}
                        >
                          <PaperChromeEditor
                            block={block}
                            editable={
                              selectedChromeBlockId === block.regionKey &&
                              block.editCapabilities.text
                            }
                            className="qpg-instruction-line"
                            onCommit={(text) =>
                              handlePaperChromeChange(block.regionKey, text)
                            }
                            onDelete={() =>
                              handleDeletePaperChrome(block.regionKey)
                            }
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
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
                        'editor-paper-section transition-colors duration-150 ease-out',
                        hoveredSectionId === section.sectionId &&
                          'bg-secondary/20',
                        section.slots.some(
                          (slot) => slot.slotId === selectedSlotId,
                        ) && 'ring-1 ring-inset ring-border',
                      )}
                    >
                      <header
                        className="editor-paper-section-header"
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
                          onDelete={() =>
                            handleDeletePaperChrome(
                              section.titleBlock.regionKey,
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
                              onDelete={() =>
                                handleDeletePaperChrome(subtitleBlock.regionKey)
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
                              onDelete={() =>
                                handleDeletePaperChrome(
                                  instructionsBlock.regionKey,
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
                              reorderEnabled={slot.editCapabilities.reorder}
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
                                              region.editable &&
                                              slot.editCapabilities.editText
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
                                          <span className="qpg-question-region-suffix select-none">
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
                              <div className="qpg-question-mark-cell">
                                {slot.showMarksLabel ? (
                                  <span className="qpg-question-mark-label">
                                    {slot.marksLabel}
                                  </span>
                                ) : null}
                              </div>
                              {activeRailSlotId === slot.slotId && (
                                <QuestionActionRail
                                  locked={slot.locked}
                                  lockEnabled={slot.editCapabilities.lock}
                                  swapEnabled={slot.editCapabilities.swap}
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

export function EditorActionBar({
  persisted,
  dirty,
  actionState,
  actionError,
  warnings,
  canUndo,
  onUndo,
  onSave,
  onDownload,
  onApprove,
}: {
  persisted: boolean;
  dirty: boolean;
  actionState: 'idle' | 'saving' | 'saved' | 'approving' | 'approved' | 'error';
  actionError: string;
  warnings: string[];
  canUndo: boolean;
  onUndo: () => void;
  onSave: () => void;
  onDownload: () => void;
  onApprove: () => void;
}) {
  const busy = actionState === 'saving' || actionState === 'approving';
  const unavailable = !persisted;
  const approved = actionState === 'approved';
  const approvalBlocked =
    unavailable || warnings.length > 0 || dirty || busy || approved;
  const status = unavailable
    ? 'Demo paper · actions unavailable'
    : actionStatus(actionState, actionError, dirty);

  return (
    <div className="flex max-w-full flex-wrap items-center justify-end gap-2">
      <span role="status" className="text-xs text-muted-foreground">
        {status}
      </span>
      {warnings.length > 0 && (
        <details
          className="flex items-center gap-1 text-xs text-destructive"
        >
          <summary className="flex cursor-pointer list-none items-center gap-1">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            {warnings.length} validation warning{warnings.length === 1 ? '' : 's'}
          </summary>
          <ul className="absolute right-4 top-14 z-30 max-w-md space-y-1 rounded-md border bg-background p-3 text-foreground shadow-lg">
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </details>
      )}
      <Button variant="outline" size="sm" disabled={!canUndo} onClick={onUndo}>
        <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
        Undo
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={unavailable || !dirty || busy || approved}
        onClick={onSave}
      >
        <Save className="mr-2 h-4 w-4" aria-hidden="true" />
        Save draft
      </Button>
      <Button variant="outline" size="sm" disabled title="Review is unavailable">
        <FileCheck2 className="mr-2 h-4 w-4" aria-hidden="true" />
        Review paper
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={unavailable || busy}
        onClick={onDownload}
      >
        <Download className="mr-2 h-4 w-4" aria-hidden="true" />
        Download PDF
      </Button>
      <Button
        size="sm"
        disabled={approvalBlocked}
        title={
          approvalBlocked
            ? 'Save changes and resolve validation warnings before approval'
            : undefined
        }
        onClick={onApprove}
      >
        <CheckCircle2 className="mr-2 h-4 w-4" aria-hidden="true" />
        Approve
      </Button>
    </div>
  );
}

function actionStatus(
  actionState: 'idle' | 'saving' | 'saved' | 'approving' | 'approved' | 'error',
  actionError: string,
  dirty: boolean,
) {
  if (actionState === 'saving') return 'Saving...';
  if (actionState === 'approving') return 'Approving...';
  if (dirty) return 'Unsaved changes';
  if (actionState === 'approved') return 'Approved';
  if (actionState === 'error') return actionError;
  return 'Saved';
}
