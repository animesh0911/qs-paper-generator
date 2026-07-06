/**
 * PaperDocumentV1 editor shell for persisted papers.
 *
 * `/editor/:paperId` fetches and validates the authenticated teacher's saved
 * paper. `/editor` is handled by the app router and returns teachers to setup.
 *
 * Patterns:
 * - The loaded `PaperDocumentV1` is canonical; BlockNote only renders editable
 *   region surfaces for the shell.
 * - Editor chrome is marked with `data-editor-chrome` so print/export styling
 *   can remove it without hiding paper content.
 *
 * Where it fits:
 * - Used by: `src/App.tsx` at `/editor/:paperId`.
 * - Uses: `src/lib/api.ts`, `src/lib/editor-paper.ts`.
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
  ArrowLeft,
  Download,
  Eye,
  Lock,
  RotateCcw,
  Save,
} from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import '@blocknote/mantine/style.css';
import {
  downloadPaperPdfPackage,
  fetchEditorDraft,
  openPaperPrintPreview,
  persistEditorDraft,
  reservePaperPrintPreview,
} from '@/lib/api';
import {
  getPaperFormatRendererResult,
  type PaperFormatRenderer,
} from '@/lib/paper-format-renderers';
import {
  editorSlotClipboardText,
  type EditorQuestionRegionBlock,
} from '@/lib/editor-paper';
import {
  reconcileAnswerDocumentForPaper,
  saveThenDownloadPdfPackage,
} from '@/lib/editor-download';
import { useEditorWorkspace } from '@/hooks/useEditorWorkspace.hook';
import {
  AssistantChat,
  EditorAlternativesOverlay,
  EditorAnswerOverlay,
  EditorInspector,
  EditorOutlineRail,
  EditorQuestionInfoOverlay,
  PaperChromeEditor,
  QuestionActionRail,
  QuestionCopyButton,
  QuestionRegionEditor,
  SortableQuestionSlot,
} from '@/components/editor';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { PaperAnswerDocument, PaperDocument } from '@/types';

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

function shouldShowInternalChoiceDivider(region: EditorQuestionRegionBlock) {
  return (
    region.blockType === 'internalChoiceBlock' &&
    (region.internalChoiceOptionIndex ?? 0) > 0
  );
}

function startsInternalChoiceGroup(region: EditorQuestionRegionBlock) {
  return (
    region.blockType === 'internalChoiceBlock' &&
    (region.internalChoiceOptionIndex ?? 0) === 0
  );
}

export default function EditorPage() {
  const { paperId } = useParams();

  if (!paperId) {
    return (
      <EditorDocumentStatus
        state="error"
        message="Choose paper setup first, then open a saved paper in the editor."
      />
    );
  }

  return <PersistedEditorPage paperId={paperId} />;
}

function PersistedEditorPage({ paperId }: { paperId: string }) {
  const [document, setDocument] = useState<PaperDocument | null>(null);
  const [answerDocument, setAnswerDocument] =
    useState<PaperAnswerDocument | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setDocument(null);
    setAnswerDocument(null);
    setError('');
    fetchEditorDraft(paperId)
      .then((draft) => {
        if (!active) return;
        setDocument(draft.document);
        setAnswerDocument(draft.answer_document);
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
  if (!document || !answerDocument) {
    return <EditorDocumentStatus state="loading" />;
  }

  return (
    <ResolvedEditorPage
      key={document.paper.id}
      document={document}
      answerDocument={answerDocument}
    />
  );
}

function ResolvedEditorPage({
  document,
  answerDocument,
}: {
  document: PaperDocument;
  answerDocument?: PaperAnswerDocument;
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
      answerDocument={answerDocument}
      renderer={rendererResult.renderer}
      selectedFixtureId={document.paper.id}
      persisted
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
          {state === 'loading'
            ? 'Loading saved paper...'
            : 'Unable to open paper'}
        </h1>
        {message && (
          <p className="mt-2 text-sm text-muted-foreground">{message}</p>
        )}
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
  answerDocument,
  renderer,
  selectedFixtureId,
  persisted,
}: {
  document: PaperDocument;
  answerDocument?: PaperAnswerDocument;
  renderer: PaperFormatRenderer;
  selectedFixtureId: string;
  persisted: boolean;
}) {
  const {
    activeRailSlotId,
    alternativesIntent,
    alternativesOverlayOpen,
    assistantResult,
    assistantStatus,
    chatInputRef,
    chatValue,
    closeAlternativesOverlay,
    dismissResult,
    runReview,
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
  const [currentAnswerDocument, setCurrentAnswerDocument] =
    useState(answerDocument);
  const [actionState, setActionState] = useState<
    'idle' | 'saving' | 'saved' | 'downloading' | 'downloaded' | 'error'
  >('idle');
  const [actionError, setActionError] = useState('');
  const [answerOverlayOpen, setAnswerOverlayOpen] = useState(false);
  const [questionInfoOverlayOpen, setQuestionInfoOverlayOpen] = useState(false);
  const dirty =
    JSON.stringify(paperState.document) !== JSON.stringify(lastSavedDocument);
  const warnings = view.validationSummary.warnings;
  const selectedAnswerEntry = selectedSlot
    ? currentAnswerDocument?.answersBySlotId[selectedSlot.slotId]
    : undefined;
  const currentSelectedAnswerEntry =
    selectedAnswerEntry?.questionId ===
    selectedSlot?.questionBlockTree.questionId
      ? selectedAnswerEntry
      : undefined;

  function handleSelectQuestionSlot(slotId: string) {
    setQuestionInfoOverlayOpen(false);
    handleSelectSlot(slotId);
  }

  function handleOpenQuestionInfo(slotId?: string) {
    if (slotId) {
      handleShowInfo(slotId);
    }
    setQuestionInfoOverlayOpen(true);
  }

  async function saveEditorDraft(documentSnapshot: PaperDocument) {
    if (!currentAnswerDocument) {
      throw new Error('Answer document is still loading.');
    }
    const reconciledAnswerDocument = reconcileAnswerDocumentForPaper(
      documentSnapshot,
      currentAnswerDocument,
    );
    const savedDraft = await persistEditorDraft(
      documentSnapshot,
      reconciledAnswerDocument,
    );
    setCurrentAnswerDocument(savedDraft.answer_document);
    setLastSavedDocument(documentSnapshot);
  }

  async function runAction(action: 'save' | 'download') {
    if (!persisted) return;
    const documentSnapshot = structuredClone(paperState.document);
    setActionError('');
    setActionState(action === 'download' ? 'downloading' : 'saving');
    try {
      if (action === 'download') {
        const reconciledAnswerDocument = await saveThenDownloadPdfPackage({
          documentSnapshot,
          answerDocument: currentAnswerDocument,
          dirty,
          persist: async (paper, answerDocument) => {
            const savedDraft = await persistEditorDraft(paper, answerDocument);
            return savedDraft.answer_document;
          },
          download: downloadPaperPdfPackage,
          preview: openPaperPrintPreview,
          reservePreview: reservePaperPrintPreview,
          onSaved: (savedAnswerDocument) => {
            setCurrentAnswerDocument(savedAnswerDocument);
            setLastSavedDocument(documentSnapshot);
          },
        });
        if (!dirty) {
          setCurrentAnswerDocument(reconciledAnswerDocument);
        }
        setActionState('downloaded');
      } else {
        await saveEditorDraft(documentSnapshot);
        setActionState('saved');
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
        <div className="flex min-w-0 items-center gap-3">
          <Link
            to="/generate"
            aria-label="Back to paper setup"
            className={cn(
              buttonVariants({ variant: 'outline', size: 'sm' }),
              'h-8 shrink-0 border-slate-300 bg-secondary/50 px-2.5 text-xs text-slate-700 hover:bg-secondary hover:text-foreground focus-visible:ring-offset-2',
            )}
          >
            <ArrowLeft className="mr-1.5 size-3.5" />
            <span className="max-sm:hidden">Back to setup</span>
            <span className="sm:hidden">Setup</span>
          </Link>
          <div
            className="h-6 w-px bg-border max-sm:hidden"
            aria-hidden="true"
          />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold leading-5">
              {view.title}
            </p>
            <p className="truncate text-xs text-muted-foreground">
              {view.paperMeta.join(' · ')}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <EditorActionBar
            persisted={persisted}
            dirty={dirty}
            actionState={actionState}
            actionError={actionError}
            warnings={warnings}
            canUndo={Boolean(undoEntry)}
            onUndo={handleUndo}
            onReview={runReview}
            onSave={() => void runAction('save')}
            onDownload={() => void runAction('download')}
          />
        </div>
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
                              onClick={() =>
                                handleSelectQuestionSlot(slot.slotId)
                              }
                              onFocus={() =>
                                handleSelectQuestionSlot(slot.slotId)
                              }
                              onMouseEnter={() => {
                                setHoveredSlotId(slot.slotId);
                                setHoveredSectionId(section.sectionId);
                              }}
                              onMouseLeave={() => setHoveredSlotId(null)}
                            >
                              <div>
                                {slot.internalChoicePrefix && (
                                  <div
                                    data-editor-chrome
                                    className="qpg-internal-choice-divider"
                                  >
                                    {slot.internalChoicePrefix}
                                  </div>
                                )}
                                <div className="space-y-1">
                                  {slot.questionBlockTree.children.map(
                                    (region) => (
                                      <div
                                        key={`${slot.slotId}:${region.regionKey}:${slot.questionBlockTree.questionId}:${slot.modifiedFromSource}`}
                                      >
                                        {shouldShowInternalChoiceDivider(
                                          region,
                                        ) && (
                                          <div
                                            data-editor-chrome
                                            className="qpg-internal-choice-divider qpg-in-question-choice-divider"
                                          >
                                            OR
                                          </div>
                                        )}
                                        <div
                                          className={cn(
                                            'qpg-question-region flex items-start gap-1',
                                            region.blockType ===
                                              'internalChoiceBlock' &&
                                              'qpg-question-region-internal-choice',
                                            startsInternalChoiceGroup(region) &&
                                              'qpg-question-choice-group-start',
                                            region.blockType ===
                                              'subQuestionBlock' &&
                                              'qpg-question-region-subquestion',
                                            region.blockType ===
                                              'mcqOptionBlock' &&
                                              'qpg-question-region-option',
                                          )}
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
                                                selectedSlotId ===
                                                  slot.slotId &&
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
                                      </div>
                                    ),
                                  )}
                                </div>
                                <div
                                  data-editor-chrome
                                  className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
                                >
                                  <QuestionCopyButton
                                    displayNumber={slot.displayNumber}
                                    text={editorSlotClipboardText(slot)}
                                  />
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
                                  onInfo={() =>
                                    handleOpenQuestionInfo(slot.slotId)
                                  }
                                  onAnswer={() => {
                                    handleSelectSlot(slot.slotId);
                                    setAnswerOverlayOpen(true);
                                  }}
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
          onOpenQuestionInfo={() => handleOpenQuestionInfo()}
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

      {answerOverlayOpen && selectedSlot && (
        <div className="editor-answer-overlay">
          <EditorAnswerOverlay
            selectedSlot={selectedSlot}
            answerEntry={currentSelectedAnswerEntry}
            onClose={() => setAnswerOverlayOpen(false)}
          />
        </div>
      )}

      {questionInfoOverlayOpen && selectedSlot && selectedQuestion && (
        <div className="editor-question-info-overlay">
          <EditorQuestionInfoOverlay
            selectedSlot={selectedSlot}
            selectedQuestion={selectedQuestion}
            onClose={() => setQuestionInfoOverlayOpen(false)}
            onRestoreSelectedSlot={handleRestoreSelectedSlot}
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

      <AssistantChat
        status={assistantStatus}
        result={assistantResult}
        chatValue={chatValue}
        selectedSlotLabel={selectedSlot?.displayNumber}
        inputRef={chatInputRef}
        onChatChange={setChatValue}
        onApply={() => undefined}
        onDismiss={dismissResult}
      />
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
  onReview,
  onSave,
  onDownload,
}: {
  persisted: boolean;
  dirty: boolean;
  actionState:
    | 'idle'
    | 'saving'
    | 'saved'
    | 'downloading'
    | 'downloaded'
    | 'error';
  actionError: string;
  warnings: string[];
  canUndo: boolean;
  onUndo: () => void;
  onReview: () => void;
  onSave: () => void;
  onDownload: () => void;
}) {
  const busy = actionState === 'saving' || actionState === 'downloading';
  const unavailable = !persisted;
  const status = unavailable
    ? 'Demo paper · actions unavailable'
    : actionStatus(actionState, actionError, dirty);

  return (
    <div className="flex max-w-full flex-wrap items-center justify-end gap-2">
      <span role="status" className="text-xs text-muted-foreground">
        {status}
      </span>
      {warnings.length > 0 && (
        <details className="flex items-center gap-1 text-xs text-destructive">
          <summary className="flex cursor-pointer list-none items-center gap-1">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            {warnings.length} validation warning
            {warnings.length === 1 ? '' : 's'}
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
        disabled={unavailable || !dirty || busy}
        onClick={onSave}
      >
        <Save className="mr-2 h-4 w-4" aria-hidden="true" />
        Save draft
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={onReview}
        title="Run a sample paper review"
      >
        <Eye className="mr-2 h-4 w-4" aria-hidden="true" />
        Preview
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
    </div>
  );
}

function actionStatus(
  actionState:
    | 'idle'
    | 'saving'
    | 'saved'
    | 'downloading'
    | 'downloaded'
    | 'error',
  actionError: string,
  dirty: boolean,
) {
  if (actionState === 'saving') return 'Saving...';
  if (actionState === 'downloading') return 'Preparing download...';
  if (dirty) return 'Unsaved changes';
  if (actionState === 'downloaded') return 'Download started';
  if (actionState === 'error') return actionError;
  return 'Saved';
}
