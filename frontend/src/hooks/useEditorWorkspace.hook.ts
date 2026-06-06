/**
 * Editor workspace interaction state.
 *
 * Keeps selection, inspector mode, alternatives, drag policy, undo, and paper
 * mutations behind one hook so the editor page can stay focused on layout.
 *
 * @module useEditorWorkspace
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  canEditSlotText,
  canLockSlot,
  canSwapSlot,
  commitStructuredPaperAction,
  getQuestion,
  getSlotOverridesById,
  getSlotQuestionContent,
  normalizePaperDocument,
  removePaperChromeBlock,
  restoreSlotSource,
  setPaperChromeText,
  setSlotLockState,
  setSlotContentOverride,
  setSlotRegionOverride,
  setSlotSelectedQuestion,
  undoStructuredPaperAction,
  type StructuredPaperUndoEntry,
} from '@/lib/paper-document';
import type { PaperFormatRenderer } from '@/lib/paper-format-renderers';
import { useEditorAlternatives } from './useEditorAlternatives.hook';
import { useEditorDragOrdering } from './useEditorDragOrdering.hook';
import { useEditorSelection } from './useEditorSelection.hook';
import type { AlternativesIntent } from '@/components/editor';
import type { ContentItem, DocQuestionContent, PaperDocument } from '@/types';

function contentItemsEqual(left: ContentItem[], right: ContentItem[]) {
  return JSON.stringify(left) === JSON.stringify(right);
}

export function useEditorWorkspace({
  document,
  renderer,
  selectedFixtureId,
}: {
  document: PaperDocument;
  renderer: PaperFormatRenderer;
  selectedFixtureId: string;
}) {
  const initialPaperState = useMemo(
    () => normalizePaperDocument(document),
    [document],
  );
  const [paperState, setPaperState] = useState(initialPaperState);
  const [undoEntry, setUndoEntry] = useState<StructuredPaperUndoEntry | null>(
    null,
  );
  const [chatValue, setChatValue] = useState('');
  const [hoveredSlotId, setHoveredSlotId] = useState<string | null>(null);
  const [hoveredSectionId, setHoveredSectionId] = useState<string | null>(null);
  const [questionEditorOpen, setQuestionEditorOpen] = useState(false);
  const chatInputRef = useRef<HTMLInputElement>(null);
  const {
    activeRailSlotId,
    clearChromeSelection,
    handleSelectChromeBlock,
    handleSelectSlot,
    handleShowInfo,
    inspectorHighlighted,
    inspectorMode,
    resetSelection,
    selectedChromeBlockId,
    selectedSlotId,
    setInspectorMode,
  } = useEditorSelection();
  const {
    alternativesIntent,
    alternativesOverlayOpen,
    closeAlternativesOverlay,
    openAlternativesOverlay,
    resetAlternatives,
    setAlternativesIntent,
  } = useEditorAlternatives();
  const view = useMemo(
    () =>
      renderer.buildEditorPaperView(paperState.document, {
        slotEditsById: getSlotOverridesById(paperState),
        alternativesIntentBySlotId: selectedSlotId
          ? { [selectedSlotId]: alternativesIntent }
          : undefined,
      }),
    [alternativesIntent, paperState, renderer, selectedSlotId],
  );
  const selectedSlot = view.sections
    .flatMap((section) => section.slots)
    .find((slot) => slot.slotId === selectedSlotId);
  const selectedQuestion = selectedSlot?.questionBlockTree.questionId
    ? getQuestion(paperState, selectedSlot.questionBlockTree.questionId)
    : undefined;
  const selectedQuestionContent =
    selectedSlotId && selectedQuestion
      ? getSlotQuestionContent(paperState, selectedSlotId)
      : undefined;

  function commitStructuredAction(nextState: typeof paperState) {
    const result = commitStructuredPaperAction(paperState, nextState);
    setPaperState(result.state);
    setUndoEntry(result.undoEntry);
  }

  const {
    dragNotice,
    dragSensors,
    handleDragEnd,
    handleDragStart,
    sameSectionCollisionDetection,
  } = useEditorDragOrdering({
    paperState,
    commitStructuredAction,
    handleSelectSlot,
  });

  useEffect(() => {
    setPaperState(initialPaperState);
    setUndoEntry(null);
    resetSelection();
    resetAlternatives();
    setQuestionEditorOpen(false);
  }, [initialPaperState, resetAlternatives, resetSelection, selectedFixtureId]);

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
    if (!canEditSlotText(paperState, slotId)) {
      return;
    }
    if (contentItemsEqual(currentContent, content)) return;
    commitStructuredAction(
      setSlotRegionOverride(paperState, slotId, regionKey, content),
    );
  }

  function handleEditQuestion(slotId: string) {
    if (!canEditSlotText(paperState, slotId)) return;
    handleSelectSlot(slotId);
    setQuestionEditorOpen(true);
  }

  function handleApplyQuestionContent(
    slotId: string,
    content: DocQuestionContent,
  ) {
    commitStructuredAction(setSlotContentOverride(paperState, slotId, content));
    setQuestionEditorOpen(false);
  }

  function handlePaperChromeChange(regionKey: string, text: string) {
    commitStructuredAction(setPaperChromeText(paperState, regionKey, text));
  }

  function handleDeletePaperChrome(regionKey: string) {
    const nextState = removePaperChromeBlock(paperState, regionKey);
    if (nextState === paperState) return;
    commitStructuredAction(nextState);
    clearChromeSelection();
  }

  function handleRestoreSelectedSlot() {
    if (!selectedSlotId) return;
    const nextState = restoreSlotSource(paperState, selectedSlotId);
    commitStructuredAction(nextState);
  }

  function handleShowAlternatives(slotId: string, intent: AlternativesIntent) {
    if (!canSwapSlot(paperState, slotId)) {
      return;
    }
    handleSelectSlot(slotId);
    setAlternativesIntent(intent);
    setInspectorMode('alternatives');
    openAlternativesOverlay();
  }

  function handleToggleLock(slotId: string, locked: boolean) {
    if (!canLockSlot(paperState, slotId)) {
      return;
    }
    handleSelectSlot(slotId);
    commitStructuredAction(setSlotLockState(paperState, slotId, !locked));
  }

  function handleUseAlternative(slotId: string, questionId: string) {
    if (!canSwapSlot(paperState, slotId)) {
      return;
    }
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
    commitStructuredAction(
      setSlotSelectedQuestion(paperState, slotId, questionId),
    );
    setAlternativesIntent('swap');
    closeAlternativesOverlay();
  }

  function handleAskQuestion(slotId: string, displayNumber: string) {
    handleSelectSlot(slotId);
    setChatValue(`Question ${displayNumber}: `);
    window.setTimeout(() => chatInputRef.current?.focus(), 0);
  }

  return {
    activeRailSlotId,
    alternativesIntent,
    alternativesOverlayOpen,
    chatInputRef,
    chatValue,
    dragNotice,
    dragSensors,
    handleAskQuestion,
    handleDeletePaperChrome,
    handleDragEnd,
    handleDragStart,
    handleEditQuestion,
    handleApplyQuestionContent,
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
    closeAlternativesOverlay,
    paperState,
    questionEditorOpen,
    sameSectionCollisionDetection,
    selectedChromeBlockId,
    selectedQuestion,
    selectedQuestionContent,
    selectedSlot,
    selectedSlotId,
    setAlternativesIntent,
    setChatValue,
    setHoveredSectionId,
    setHoveredSlotId,
    setInspectorMode,
    setQuestionEditorOpen,
    undoEntry,
    view,
  };
}
