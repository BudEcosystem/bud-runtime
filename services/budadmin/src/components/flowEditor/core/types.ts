/**
 * Generic Flow Editor Types
 *
 * These types provide the foundation for building domain-specific
 * flow editors (workflow editor, prompt editor, etc.)
 */

import type { ComponentType } from 'react';
import type {
  Node,
  Edge,
  NodeProps,
  EdgeProps,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
  Connection,
} from '@xyflow/react';

// ============================================================================
// Node Configuration
// ============================================================================

/**
 * Configuration for a node type in the flow editor
 */
export interface NodeTypeConfig<T extends Record<string, unknown> = Record<string, unknown>> {
  /** React component to render the node */
  component: ComponentType<NodeProps<Node<T>>>;
  /** Default data when creating a new node of this type */
  defaultData?: Partial<T>;
  /** Number of input/output handles */
  handles?: {
    inputs: number;
    outputs: number;
  };
  /** Whether this node type can be deleted */
  deletable?: boolean;
  /** Whether this node type can be copied */
  copyable?: boolean;
  /** Display label for the node type */
  label?: string;
  /** Icon for the node type (React component or string) */
  icon?: ComponentType | string;
  /** Color for the node type */
  color?: string;
}

/**
 * Registry of node types for a flow editor
 */
export type NodeTypeRegistry = Record<string, NodeTypeConfig>;

// ============================================================================
// Edge Configuration
// ============================================================================

/**
 * Configuration for an edge type in the flow editor
 */
export interface EdgeTypeConfig {
  /** React component to render the edge */
  component: ComponentType<EdgeProps>;
  /** Whether the edge shows a label */
  labeled?: boolean;
  /** Whether the edge is animated */
  animated?: boolean;
  /** Whether the edge is deletable */
  deletable?: boolean;
}

/**
 * Registry of edge types for a flow editor
 */
export type EdgeTypeRegistry = Record<string, EdgeTypeConfig>;

// ============================================================================
// Layout Configuration
// ============================================================================

/**
 * Layout direction for the flow editor
 */
export type LayoutDirection = 'TB' | 'LR';

/**
 * Configuration for auto-layout
 */
export interface LayoutConfig {
  /** Layout direction */
  direction: LayoutDirection;
  /** Horizontal spacing between nodes */
  nodeSpacingX?: number;
  /** Vertical spacing between nodes */
  nodeSpacingY?: number;
  /** Rank spacing for dagre */
  rankSep?: number;
  /** Node spacing for dagre */
  nodeSep?: number;
  /** Edge spacing for dagre */
  edgeSep?: number;
}

/**
 * Default layout configuration
 */
export const DEFAULT_LAYOUT_CONFIG: LayoutConfig = {
  direction: 'TB',
  nodeSpacingX: 150,
  nodeSpacingY: 80,
  rankSep: 80,
  nodeSep: 50,
  edgeSep: 10,
};

// ============================================================================
// Validation Configuration
// ============================================================================

/**
 * Validation error for a node or edge
 */
export interface ValidationError {
  type: 'node' | 'edge';
  id: string;
  message: string;
  severity: 'error' | 'warning';
}

/**
 * Result of validating the flow
 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

/**
 * Validation rule function
 */
export type ValidationRule = (
  nodes: Node[],
  edges: Edge[]
) => ValidationError[];

/**
 * Configuration for flow validation
 */
export interface ValidationConfig {
  /** Whether to prevent cycles in the graph */
  preventCycles?: boolean;
  /** Whether to validate on every change */
  validateOnChange?: boolean;
  /** Custom validation rules */
  rules?: ValidationRule[];
}

/**
 * Default validation configuration
 */
export const DEFAULT_VALIDATION_CONFIG: ValidationConfig = {
  preventCycles: true,
  validateOnChange: true,
  rules: [],
};

// ============================================================================
// Flow Editor Configuration
// ============================================================================

/**
 * Complete configuration for a flow editor instance
 */
export interface FlowEditorConfig {
  /** Node type registry */
  nodeTypes: NodeTypeRegistry;
  /** Edge type registry (optional, uses defaults if not provided) */
  edgeTypes?: EdgeTypeRegistry;
  /** Layout configuration */
  layout?: LayoutConfig;
  /** Validation configuration */
  validation?: ValidationConfig;
  /** Default edge type */
  defaultEdgeType?: string;
  /** Whether the editor is read-only */
  readonly?: boolean;
  /** Whether to show the minimap */
  showMinimap?: boolean;
  /** Whether to show zoom controls */
  showControls?: boolean;
  /** Whether to show the toolbar */
  showToolbar?: boolean;
  /** Whether to enable undo/redo */
  enableUndoRedo?: boolean;
  /** Max history size for undo/redo */
  maxHistorySize?: number;
}

/**
 * Default flow editor configuration
 */
export const DEFAULT_FLOW_EDITOR_CONFIG: Partial<FlowEditorConfig> = {
  layout: DEFAULT_LAYOUT_CONFIG,
  validation: DEFAULT_VALIDATION_CONFIG,
  defaultEdgeType: 'default',
  readonly: false,
  showMinimap: true,
  showControls: true,
  showToolbar: true,
  enableUndoRedo: true,
  maxHistorySize: 50,
};

// ============================================================================
// Flow Editor State
// ============================================================================

/**
 * State of the flow editor
 */
export interface FlowEditorState {
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  layoutDirection: LayoutDirection;
  validationResult: ValidationResult;
  canUndo: boolean;
  canRedo: boolean;
}

/**
 * Actions for the flow editor
 */
export interface FlowEditorActions {
  // Node operations
  addNode: (type: string, position?: { x: number; y: number }, data?: Record<string, unknown>) => string;
  updateNode: (id: string, data: Partial<Record<string, unknown>>) => void;
  deleteNode: (id: string) => void;
  selectNode: (id: string | null) => void;

  // Edge operations
  addEdge: (source: string, target: string, data?: Record<string, unknown>) => string | null;
  updateEdge: (id: string, data: Partial<Record<string, unknown>>) => void;
  deleteEdge: (id: string) => void;
  selectEdge: (id: string | null) => void;

  // Layout operations
  setLayoutDirection: (direction: LayoutDirection) => void;
  autoLayout: () => void;
  fitView: () => void;

  // History operations
  undo: () => void;
  redo: () => void;

  // Validation
  validate: () => ValidationResult;

  // Bulk operations
  setNodes: (nodes: Node[]) => void;
  setEdges: (edges: Edge[]) => void;
  clear: () => void;
}

/**
 * Combined state and actions for the flow editor context
 */
export interface FlowEditorContextValue extends FlowEditorState, FlowEditorActions {
  config: FlowEditorConfig;
}

// ============================================================================
// Callback Types
// ============================================================================

/**
 * Callback when nodes change
 */
export type OnNodesChangeCallback = OnNodesChange;

/**
 * Callback when edges change
 */
export type OnEdgesChangeCallback = OnEdgesChange;

/**
 * Callback when a connection is made
 */
export type OnConnectCallback = OnConnect;

/**
 * Callback when a node is selected
 */
export type OnNodeSelectCallback = (nodeId: string | null, node: Node | null) => void;

/**
 * Callback when an edge is selected
 */
export type OnEdgeSelectCallback = (edgeId: string | null, edge: Edge | null) => void;

/**
 * Callback when the flow changes (for external state sync)
 */
export type OnFlowChangeCallback = (nodes: Node[], edges: Edge[]) => void;

/**
 * Callback to validate a potential connection
 */
export type ConnectionValidator = (connection: Connection) => boolean;

// ============================================================================
// Node Palette Types
// ============================================================================

/**
 * Category for grouping node types in the palette
 */
export interface NodePaletteCategory {
  id: string;
  label: string;
  icon?: ComponentType | string;
  collapsed?: boolean;
}

/**
 * Item in the node palette
 */
export interface NodePaletteItem {
  type: string;
  label: string;
  description?: string;
  icon?: ComponentType | string;
  color?: string;
  categoryId: string;
}

/**
 * Configuration for the node palette
 */
export interface NodePaletteConfig {
  categories: NodePaletteCategory[];
  items: NodePaletteItem[];
  searchable?: boolean;
  collapsible?: boolean;
}

// ============================================================================
// Toolbar Types
// ============================================================================

/**
 * Action in the toolbar
 */
export interface ToolbarAction {
  id: string;
  label: string;
  icon?: ComponentType | string;
  onClick: () => void;
  disabled?: boolean;
  tooltip?: string;
}

/**
 * Configuration for the toolbar
 */
export interface ToolbarConfig {
  showLayoutToggle?: boolean;
  showUndoRedo?: boolean;
  showFitView?: boolean;
  customActions?: ToolbarAction[];
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * Position type
 */
export interface Position {
  x: number;
  y: number;
}

/**
 * Dimensions type
 */
export interface Dimensions {
  width: number;
  height: number;
}

/**
 * Create a typed node with specific data type
 */
export type TypedNode<T extends Record<string, unknown> = Record<string, unknown>> = Node<T>;

/**
 * Create a typed edge with specific data type
 */
export type TypedEdge<T extends Record<string, unknown> = Record<string, unknown>> = Edge<T>;

/**
 * Generic node props type for custom node components
 */
export type GenericNodeProps<T extends Record<string, unknown> = Record<string, unknown>> = NodeProps<Node<T>>;

/**
 * Generic edge props type for custom edge components
 */
export type GenericEdgeProps<T extends Record<string, unknown> = Record<string, unknown>> = EdgeProps<Edge<T>>;
