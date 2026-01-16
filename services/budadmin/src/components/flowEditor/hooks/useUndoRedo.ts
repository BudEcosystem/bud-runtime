'use client';

/**
 * Undo/Redo Hook
 *
 * Provides history management for the flow editor with:
 * - Undo/redo stack
 * - Keyboard shortcuts support
 * - Configurable max history size
 */

import { useState, useCallback, useRef } from 'react';
import type { Node, Edge } from '@xyflow/react';

/**
 * State snapshot for undo/redo
 */
export interface HistoryState {
  nodes: Node[];
  edges: Edge[];
  timestamp: number;
}

export interface UseUndoRedoReturn {
  /** Push a new state to history */
  pushState: (nodes: Node[], edges: Edge[]) => void;
  /** Undo to previous state */
  undo: () => HistoryState | null;
  /** Redo to next state */
  redo: () => HistoryState | null;
  /** Whether undo is available */
  canUndo: boolean;
  /** Whether redo is available */
  canRedo: boolean;
  /** Clear all history */
  clearHistory: () => void;
  /** Get current history size */
  historySize: number;
  /** Get redo stack size */
  redoSize: number;
}

/**
 * Hook for undo/redo functionality
 */
export function useUndoRedo(maxHistorySize: number = 50): UseUndoRedoReturn {
  // Use refs to avoid unnecessary re-renders
  const historyRef = useRef<HistoryState[]>([]);
  const redoStackRef = useRef<HistoryState[]>([]);
  const [, forceUpdate] = useState({});

  // Force component update
  const triggerUpdate = useCallback(() => {
    forceUpdate({});
  }, []);

  /**
   * Push a new state to history
   */
  const pushState = useCallback(
    (nodes: Node[], edges: Edge[]) => {
      const newState: HistoryState = {
        nodes: JSON.parse(JSON.stringify(nodes)), // Deep clone
        edges: JSON.parse(JSON.stringify(edges)), // Deep clone
        timestamp: Date.now(),
      };

      // Add to history
      historyRef.current.push(newState);

      // Trim history if exceeds max size
      if (historyRef.current.length > maxHistorySize) {
        historyRef.current.shift();
      }

      // Clear redo stack when new action is performed
      redoStackRef.current = [];

      triggerUpdate();
    },
    [maxHistorySize, triggerUpdate]
  );

  /**
   * Undo to previous state
   */
  const undo = useCallback((): HistoryState | null => {
    if (historyRef.current.length <= 1) {
      return null; // Keep at least one state (initial state)
    }

    // Pop current state and push to redo stack
    const currentState = historyRef.current.pop();
    if (currentState) {
      redoStackRef.current.push(currentState);
    }

    // Get previous state
    const previousState = historyRef.current[historyRef.current.length - 1];
    triggerUpdate();

    return previousState
      ? {
          nodes: JSON.parse(JSON.stringify(previousState.nodes)),
          edges: JSON.parse(JSON.stringify(previousState.edges)),
          timestamp: previousState.timestamp,
        }
      : null;
  }, [triggerUpdate]);

  /**
   * Redo to next state
   */
  const redo = useCallback((): HistoryState | null => {
    if (redoStackRef.current.length === 0) {
      return null;
    }

    // Pop from redo stack
    const nextState = redoStackRef.current.pop();
    if (!nextState) return null;

    // Push to history
    historyRef.current.push(nextState);
    triggerUpdate();

    return {
      nodes: JSON.parse(JSON.stringify(nextState.nodes)),
      edges: JSON.parse(JSON.stringify(nextState.edges)),
      timestamp: nextState.timestamp,
    };
  }, [triggerUpdate]);

  /**
   * Clear all history
   */
  const clearHistory = useCallback(() => {
    historyRef.current = [];
    redoStackRef.current = [];
    triggerUpdate();
  }, [triggerUpdate]);

  return {
    pushState,
    undo,
    redo,
    canUndo: historyRef.current.length > 1,
    canRedo: redoStackRef.current.length > 0,
    clearHistory,
    historySize: historyRef.current.length,
    redoSize: redoStackRef.current.length,
  };
}

export default useUndoRedo;
