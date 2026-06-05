/**
 * Alternatives overlay state for the Paper editor workspace.
 *
 * @module useEditorAlternatives
 */
import { useCallback, useRef, useState } from 'react';
import type { AlternativesIntent } from '@/components/editor';

export function useEditorAlternatives() {
  const [alternativesIntent, setAlternativesIntent] =
    useState<AlternativesIntent>('swap');
  const [alternativesOverlayOpen, setAlternativesOverlayOpen] = useState(false);
  const alternativesOpenerRef = useRef<HTMLElement | null>(null);

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

  const resetAlternatives = useCallback(() => {
    setAlternativesIntent('swap');
    setAlternativesOverlayOpen(false);
  }, []);

  return {
    alternativesIntent,
    alternativesOverlayOpen,
    closeAlternativesOverlay,
    openAlternativesOverlay,
    resetAlternatives,
    setAlternativesIntent,
    setAlternativesOverlayOpen,
  };
}
