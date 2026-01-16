/**
 * Flow Editor
 *
 * Generic, reusable flow editor library built on React Flow.
 * Can be configured for different use cases (workflow editor, prompt editor, etc.)
 *
 * @example
 * ```tsx
 * import { FlowEditor, type FlowEditorConfig } from '@/components/flowEditor';
 *
 * const config: FlowEditorConfig = {
 *   nodeTypes: {
 *     myNode: { component: MyNodeComponent },
 *   },
 * };
 *
 * function MyEditor() {
 *   return <FlowEditor config={config} />;
 * }
 * ```
 */

// Core
export {
  FlowEditor,
  FlowEditorProvider,
  useFlowEditorContext,
  useFlowEditorContextSafe,
  useFlowNodes,
  useFlowEdges,
  useSelectedNode,
  useSelectedEdge,
  useFlowConfig,
  useFlowValidation,
  useLayoutDirection,
  useUndoRedoState,
} from './core';

export type {
  FlowEditorProps,
  FlowEditorProviderProps,
  FlowEditorConfig,
  FlowEditorState,
  FlowEditorActions,
  FlowEditorContextValue,
  NodeTypeConfig,
  NodeTypeRegistry,
  EdgeTypeConfig,
  EdgeTypeRegistry,
  LayoutDirection,
  LayoutConfig,
  ValidationConfig,
  ValidationResult,
  ValidationError,
  ValidationRule,
  OnNodeSelectCallback,
  OnEdgeSelectCallback,
  OnFlowChangeCallback,
  ConnectionValidator,
  NodePaletteCategory,
  NodePaletteItem,
  NodePaletteConfig,
  ToolbarAction,
  ToolbarConfig,
  Position,
  Dimensions,
  TypedNode,
  TypedEdge,
  DEFAULT_LAYOUT_CONFIG,
  DEFAULT_VALIDATION_CONFIG,
  DEFAULT_FLOW_EDITOR_CONFIG,
} from './core';

// Hooks
export {
  useAutoLayout,
  applyDagreLayout,
  useValidation,
  useUndoRedo,
  useDragAndDrop,
  createDragStartHandler,
  DEFAULT_DRAG_MIME_TYPE,
} from './hooks';

export type {
  UseAutoLayoutOptions,
  UseAutoLayoutReturn,
  UseValidationReturn,
  HistoryState,
  UseUndoRedoReturn,
  DragData,
  UseDragAndDropOptions,
  UseDragAndDropReturn,
} from './hooks';

// Nodes
export { BaseNode, CardNode } from './nodes';
export type { BaseNodeData, BaseNodeProps, CardNodeData, CardNodeProps } from './nodes';

// Edges
export { LabeledEdge } from './edges';
export type { LabeledEdgeData, LabeledEdgeProps } from './edges';

// Components
export { FlowToolbar, NodePalette } from './components';
export type { FlowToolbarProps, NodePaletteProps, DragHandleProps } from './components';

// Re-export React Flow types that consumers might need
export type {
  Node,
  Edge,
  Connection,
  NodeProps,
  EdgeProps,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
} from '@xyflow/react';
