'use client';

/**
 * Drag and Drop Hook
 *
 * Provides drag and drop functionality for adding nodes from a palette.
 */

import { useCallback, useState, type DragEvent } from 'react';
import { useReactFlow } from '@xyflow/react';

/** Default MIME type for drag data */
export const DEFAULT_DRAG_MIME_TYPE = 'application/flow-node';

export interface DragData {
  type: string;
  data?: Record<string, unknown>;
}

export interface UseDragAndDropOptions {
  /** MIME type for drag data */
  mimeType?: string;
  /** Callback when a node is dropped */
  onDrop?: (type: string, position: { x: number; y: number }, data?: Record<string, unknown>) => void;
}

export interface UseDragAndDropReturn {
  /** Handler for drag start (call from palette item) */
  onDragStart: (event: DragEvent, type: string, data?: Record<string, unknown>) => void;
  /** Handler for drag over (call from drop zone) */
  onDragOver: (event: DragEvent) => void;
  /** Handler for drop (call from drop zone) */
  onDrop: (event: DragEvent) => void;
  /** Whether something is being dragged over the drop zone */
  isDragOver: boolean;
}

/**
 * Hook for drag and drop node creation
 */
export function useDragAndDrop(options: UseDragAndDropOptions = {}): UseDragAndDropReturn {
  const { mimeType = DEFAULT_DRAG_MIME_TYPE, onDrop: onDropCallback } = options;
  const [isDragOver, setIsDragOver] = useState(false);
  const reactFlow = useReactFlow();

  /**
   * Handle drag start from palette
   */
  const onDragStart = useCallback(
    (event: DragEvent, type: string, data?: Record<string, unknown>) => {
      const dragData: DragData = { type, data };
      event.dataTransfer.setData(mimeType, JSON.stringify(dragData));
      event.dataTransfer.effectAllowed = 'move';
    },
    [mimeType]
  );

  /**
   * Handle drag over drop zone
   */
  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    setIsDragOver(true);
  }, []);

  /**
   * Handle drop on drop zone
   */
  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();
      setIsDragOver(false);

      // Get drag data
      const dragDataStr = event.dataTransfer.getData(mimeType);
      if (!dragDataStr) return;

      let dragData: DragData;
      try {
        dragData = JSON.parse(dragDataStr);
      } catch {
        console.error('Failed to parse drag data');
        return;
      }

      // Calculate drop position in flow coordinates
      const bounds = (event.target as HTMLElement).closest('.react-flow')?.getBoundingClientRect();
      if (!bounds) return;

      const position = reactFlow.screenToFlowPosition({
        x: event.clientX - bounds.left,
        y: event.clientY - bounds.top,
      });

      // Notify callback
      onDropCallback?.(dragData.type, position, dragData.data);
    },
    [mimeType, reactFlow, onDropCallback]
  );

  return {
    onDragStart,
    onDragOver,
    onDrop,
    isDragOver,
  };
}

/**
 * Create drag start handler (utility function for palette items)
 */
export function createDragStartHandler(
  type: string,
  data?: Record<string, unknown>,
  mimeType: string = DEFAULT_DRAG_MIME_TYPE
) {
  return (event: DragEvent) => {
    const dragData: DragData = { type, data };
    event.dataTransfer.setData(mimeType, JSON.stringify(dragData));
    event.dataTransfer.effectAllowed = 'move';
  };
}

export default useDragAndDrop;
