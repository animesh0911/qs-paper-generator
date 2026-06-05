/**
 * Selection and inspector state for the Paper editor workspace.
 *
 * @module useEditorSelection
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { InspectorMode } from '@/components/editor';

export function useEditorSelection() {
  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const [activeRailSlotId, setActiveRailSlotId] = useState<string | null>(null);
  const [selectedChromeBlockId, setSelectedChromeBlockId] = useState<
    string | null
  >(null);
  const [inspectorMode, setInspectorMode] = useState<InspectorMode>('info');
  const [inspectorHighlighted, setInspectorHighlighted] = useState(false);
  const inspectorHighlightTimeoutRef = useRef<number | null>(null);

  const clearSelection = useCallback(() => {
    setActiveRailSlotId(null);
    setSelectedSlotId(null);
    setSelectedChromeBlockId(null);
  }, []);

  const resetSelection = useCallback(() => {
    clearSelection();
    setInspectorMode('info');
  }, [clearSelection]);

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
      if (window.document.activeElement instanceof HTMLElement) {
        window.document.activeElement.blur();
      }
      clearSelection();
    }

    window.document.addEventListener('pointerdown', handleOutsidePointerDown);
    return () => {
      window.document.removeEventListener(
        'pointerdown',
        handleOutsidePointerDown,
      );
    };
  }, [clearSelection]);

  useEffect(() => {
    return () => {
      if (inspectorHighlightTimeoutRef.current !== null) {
        window.clearTimeout(inspectorHighlightTimeoutRef.current);
      }
    };
  }, []);

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

  function clearChromeSelection() {
    setSelectedChromeBlockId(null);
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

  return {
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
  };
}
