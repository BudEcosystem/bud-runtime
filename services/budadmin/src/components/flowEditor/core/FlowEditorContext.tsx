'use client';

/**
 * Flow Editor Context
 *
 * Provides shared state and actions for the flow editor.
 * This context is used by all child components to access and modify the flow.
 */

import React, {
  createContext,
  useContext,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react';
import { useReactFlow, type Node, type Edge } from '@xyflow/react';
import type {
  FlowEditorContextValue,
  FlowEditorConfig,
  LayoutDirection,
  ValidationResult,
} from './types';

// ============================================================================
// Context Definition
// ============================================================================

const FlowEditorContext = createContext<FlowEditorContextValue | null>(null);

// ============================================================================
// Hook to use the context
// ============================================================================

/**
 * Hook to access the flow editor context
 * @throws Error if used outside of FlowEditorProvider
 */
export function useFlowEditorContext(): FlowEditorContextValue {
  const context = useContext(FlowEditorContext);
  if (!context) {
    throw new Error(
      'useFlowEditorContext must be used within a FlowEditorProvider'
    );
  }
  return context;
}

/**
 * Hook to access flow editor context, returns null if not in provider
 */
export function useFlowEditorContextSafe(): FlowEditorContextValue | null {
  return useContext(FlowEditorContext);
}

// ============================================================================
// Provider Props
// ============================================================================

export interface FlowEditorProviderProps {
  children: ReactNode;
  config: FlowEditorConfig;
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  layoutDirection: LayoutDirection;
  validationResult: ValidationResult;
  canUndo: boolean;
  canRedo: boolean;
  onAddNode: (type: string, position?: { x: number; y: number }, data?: Record<string, unknown>) => string;
  onUpdateNode: (id: string, data: Partial<Record<string, unknown>>) => void;
  onDeleteNode: (id: string) => void;
  onSelectNode: (id: string | null) => void;
  onAddEdge: (source: string, target: string, data?: Record<string, unknown>) => string | null;
  onUpdateEdge: (id: string, data: Partial<Record<string, unknown>>) => void;
  onDeleteEdge: (id: string) => void;
  onSelectEdge: (id: string | null) => void;
  onSetLayoutDirection: (direction: LayoutDirection) => void;
  onAutoLayout: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onValidate: () => ValidationResult;
  onSetNodes: (nodes: Node[]) => void;
  onSetEdges: (edges: Edge[]) => void;
  onClear: () => void;
}

// ============================================================================
// Provider Component
// ============================================================================

/**
 * Provider component for the flow editor context
 */
export function FlowEditorProvider({
  children,
  config,
  nodes,
  edges,
  selectedNodeId,
  selectedEdgeId,
  layoutDirection,
  validationResult,
  canUndo,
  canRedo,
  onAddNode,
  onUpdateNode,
  onDeleteNode,
  onSelectNode,
  onAddEdge,
  onUpdateEdge,
  onDeleteEdge,
  onSelectEdge,
  onSetLayoutDirection,
  onAutoLayout,
  onUndo,
  onRedo,
  onValidate,
  onSetNodes,
  onSetEdges,
  onClear,
}: FlowEditorProviderProps) {
  const reactFlow = useReactFlow();

  // Fit view action
  const fitView = useCallback(() => {
    reactFlow.fitView({ padding: 0.2 });
  }, [reactFlow]);

  // Memoize the context value to prevent unnecessary re-renders
  const contextValue = useMemo<FlowEditorContextValue>(
    () => ({
      // Config
      config,

      // State
      nodes,
      edges,
      selectedNodeId,
      selectedEdgeId,
      layoutDirection,
      validationResult,
      canUndo,
      canRedo,

      // Node actions
      addNode: onAddNode,
      updateNode: onUpdateNode,
      deleteNode: onDeleteNode,
      selectNode: onSelectNode,

      // Edge actions
      addEdge: onAddEdge,
      updateEdge: onUpdateEdge,
      deleteEdge: onDeleteEdge,
      selectEdge: onSelectEdge,

      // Layout actions
      setLayoutDirection: onSetLayoutDirection,
      autoLayout: onAutoLayout,
      fitView,

      // History actions
      undo: onUndo,
      redo: onRedo,

      // Validation
      validate: onValidate,

      // Bulk actions
      setNodes: onSetNodes,
      setEdges: onSetEdges,
      clear: onClear,
    }),
    [
      config,
      nodes,
      edges,
      selectedNodeId,
      selectedEdgeId,
      layoutDirection,
      validationResult,
      canUndo,
      canRedo,
      onAddNode,
      onUpdateNode,
      onDeleteNode,
      onSelectNode,
      onAddEdge,
      onUpdateEdge,
      onDeleteEdge,
      onSelectEdge,
      onSetLayoutDirection,
      onAutoLayout,
      fitView,
      onUndo,
      onRedo,
      onValidate,
      onSetNodes,
      onSetEdges,
      onClear,
    ]
  );

  return (
    <FlowEditorContext.Provider value={contextValue}>
      {children}
    </FlowEditorContext.Provider>
  );
}

// ============================================================================
// Convenience Hooks
// ============================================================================

/**
 * Hook to get the current nodes from context
 */
export function useFlowNodes(): Node[] {
  const context = useFlowEditorContext();
  return context.nodes;
}

/**
 * Hook to get the current edges from context
 */
export function useFlowEdges(): Edge[] {
  const context = useFlowEditorContext();
  return context.edges;
}

/**
 * Hook to get the selected node
 */
export function useSelectedNode(): Node | null {
  const context = useFlowEditorContext();
  if (!context.selectedNodeId) return null;
  return context.nodes.find((n) => n.id === context.selectedNodeId) || null;
}

/**
 * Hook to get the selected edge
 */
export function useSelectedEdge(): Edge | null {
  const context = useFlowEditorContext();
  if (!context.selectedEdgeId) return null;
  return context.edges.find((e) => e.id === context.selectedEdgeId) || null;
}

/**
 * Hook to get the config
 */
export function useFlowConfig(): FlowEditorConfig {
  const context = useFlowEditorContext();
  return context.config;
}

/**
 * Hook to get validation state
 */
export function useFlowValidation(): ValidationResult {
  const context = useFlowEditorContext();
  return context.validationResult;
}

/**
 * Hook to get layout direction
 */
export function useLayoutDirection(): [LayoutDirection, (direction: LayoutDirection) => void] {
  const context = useFlowEditorContext();
  return [context.layoutDirection, context.setLayoutDirection];
}

/**
 * Hook to get undo/redo state and actions
 */
export function useUndoRedoState(): {
  canUndo: boolean;
  canRedo: boolean;
  undo: () => void;
  redo: () => void;
} {
  const context = useFlowEditorContext();
  return {
    canUndo: context.canUndo,
    canRedo: context.canRedo,
    undo: context.undo,
    redo: context.redo,
  };
}

export default FlowEditorContext;
