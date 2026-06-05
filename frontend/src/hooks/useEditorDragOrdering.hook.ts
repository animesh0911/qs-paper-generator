/**
 * Same-section drag ordering policy for Paper Slots.
 *
 * @module useEditorDragOrdering
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  closestCenter,
  KeyboardSensor,
  pointerWithin,
  PointerSensor,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import {
  buildOrderZones,
  reorderSlotWithinOrderZone,
  type NormalizedPaperDocument,
} from '@/lib/paper-document';

export function useEditorDragOrdering({
  paperState,
  commitStructuredAction,
  handleSelectSlot,
}: {
  paperState: NormalizedPaperDocument;
  commitStructuredAction: (nextState: NormalizedPaperDocument) => void;
  handleSelectSlot: (slotId: string) => void;
}) {
  const [dragNotice, setDragNotice] = useState<string | null>(null);
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

  useEffect(() => {
    if (!dragNotice) return undefined;
    const timeoutId = window.setTimeout(() => setDragNotice(null), 2400);
    return () => window.clearTimeout(timeoutId);
  }, [dragNotice]);

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

  return {
    dragNotice,
    dragSensors,
    handleDragEnd,
    handleDragStart,
    sameSectionCollisionDetection,
  };
}
