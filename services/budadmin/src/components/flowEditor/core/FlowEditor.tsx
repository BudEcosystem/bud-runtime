'use client';

/**
 * Flow Editor
 *
 * Generic, reusable flow editor component built on React Flow.
 * Can be configured for different use cases (workflow editor, prompt editor, etc.)
 */

import React, {
  useState,
  useCallback,
  useMemo,
  useEffect,
  type ReactNode,
  type ComponentType,
} from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  MiniMap,
  Controls,
  useNodesState,
  useEdgesState,
  addEdge,
  type Node,
  type Edge,
  type Connection,
  type OnNodesChange,
  type OnEdgesChange,
  type NodeTypes,
  type EdgeTypes,
  type NodeProps,
  type EdgeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { FlowEditorProvider } from './FlowEditorContext';
import type {
  FlowEditorConfig,
  LayoutDirection,
  ValidationResult,
  ValidationError,
  OnNodeSelectCallback,
  OnEdgeSelectCallback,
  OnFlowChangeCallback,
  ConnectionValidator,
  DEFAULT_FLOW_EDITOR_CONFIG,
} from './types';
import { useAutoLayout } from '../hooks/useAutoLayout';
import { useValidation } from '../hooks/useValidation';
import { useUndoRedo } from '../hooks/useUndoRedo';

// ============================================================================
// Props
// ============================================================================

export interface FlowEditorProps {
  /** Editor configuration */
  config: FlowEditorConfig;

  /** Initial nodes */
  initialNodes?: Node[];

  /** Initial edges */
  initialEdges?: Edge[];

  /** Callback when a node is selected */
  onNodeSelect?: OnNodeSelectCallback;

  /** Callback when an edge is selected */
  onEdgeSelect?: OnEdgeSelectCallback;

  /** Callback when the flow changes */
  onFlowChange?: OnFlowChangeCallback;

  /** Custom connection validator */
  connectionValidator?: ConnectionValidator;

  /** Children (toolbar, sidebars, etc.) */
  children?: ReactNode;

  /** Additional class name */
  className?: string;

  /** Custom node types (merged with config) */
  customNodeTypes?: NodeTypes;

  /** Custom edge types (merged with config) */
  customEdgeTypes?: EdgeTypes;
}

// ============================================================================
// Internal Component (must be inside ReactFlowProvider)
// ============================================================================

function FlowEditorInternal({
  config,
  initialNodes = [],
  initialEdges = [],
  onNodeSelect,
  onEdgeSelect,
  onFlowChange,
  connectionValidator,
  children,
  className = '',
  customNodeTypes,
  customEdgeTypes,
}: FlowEditorProps) {
  // State
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [layoutDirection, setLayoutDirection] = useState<LayoutDirection>(
    config.layout?.direction || 'TB'
  );

  // Hooks
  const { applyLayout } = useAutoLayout(layoutDirection, config.layout);
  const { validate, validateConnection, detectCycle } = useValidation(config.validation);
  const {
    pushState,
    undo,
    redo,
    canUndo,
    canRedo,
  } = useUndoRedo(config.maxHistorySize || 50);

  // Validation result state
  const [validationResult, setValidationResult] = useState<ValidationResult>({
    valid: true,
    errors: [],
  });

  // Build node types from config
  const nodeTypes = useMemo<NodeTypes>(() => {
    const types: NodeTypes = {};
    if (config.nodeTypes) {
      Object.entries(config.nodeTypes).forEach(([key, nodeConfig]) => {
        types[key] = nodeConfig.component as ComponentType<NodeProps>;
      });
    }
    // Merge with custom node types
    if (customNodeTypes) {
      Object.assign(types, customNodeTypes);
    }
    return types;
  }, [config.nodeTypes, customNodeTypes]);

  // Build edge types from config
  const edgeTypes = useMemo<EdgeTypes>(() => {
    const types: EdgeTypes = {};
    if (config.edgeTypes) {
      Object.entries(config.edgeTypes).forEach(([key, edgeConfig]) => {
        // Type assertion needed for React Flow v12 edge types compatibility
        types[key] = edgeConfig.component as EdgeTypes[string];
      });
    }
    // Merge with custom edge types
    if (customEdgeTypes) {
      Object.assign(types, customEdgeTypes);
    }
    return types;
  }, [config.edgeTypes, customEdgeTypes]);

  // Notify parent of flow changes
  useEffect(() => {
    onFlowChange?.(nodes, edges);
  }, [nodes, edges, onFlowChange]);

  // Validate on change if configured
  useEffect(() => {
    if (config.validation?.validateOnChange) {
      const result = validate(nodes, edges);
      setValidationResult(result);
    }
  }, [nodes, edges, config.validation?.validateOnChange, validate]);

  // ============================================================================
  // Node Operations
  // ============================================================================

  const handleAddNode = useCallback(
    (
      type: string,
      position?: { x: number; y: number },
      data?: Record<string, unknown>
    ): string => {
      const id = `${type}_${Date.now()}`;
      const nodeConfig = config.nodeTypes?.[type];
      const newNode: Node = {
        id,
        type,
        position: position || { x: 0, y: 0 },
        data: {
          ...nodeConfig?.defaultData,
          ...data,
        },
      };

      setNodes((nds) => {
        const updatedNodes = [...nds, newNode];
        pushState(updatedNodes, edges);
        return updatedNodes;
      });

      return id;
    },
    [config.nodeTypes, setNodes, edges, pushState]
  );

  const handleUpdateNode = useCallback(
    (id: string, data: Partial<Record<string, unknown>>) => {
      setNodes((nds) => {
        const updatedNodes = nds.map((node) =>
          node.id === id
            ? { ...node, data: { ...node.data, ...data } }
            : node
        );
        pushState(updatedNodes, edges);
        return updatedNodes;
      });
    },
    [setNodes, edges, pushState]
  );

  const handleDeleteNode = useCallback(
    (id: string) => {
      const nodeConfig = config.nodeTypes?.[nodes.find((n) => n.id === id)?.type || ''];
      if (nodeConfig?.deletable === false) return;

      setNodes((nds) => {
        const updatedNodes = nds.filter((node) => node.id !== id);
        // Also remove connected edges
        setEdges((eds) => {
          const updatedEdges = eds.filter(
            (edge) => edge.source !== id && edge.target !== id
          );
          pushState(updatedNodes, updatedEdges);
          return updatedEdges;
        });
        return updatedNodes;
      });

      if (selectedNodeId === id) {
        setSelectedNodeId(null);
        onNodeSelect?.(null, null);
      }
    },
    [config.nodeTypes, nodes, setNodes, setEdges, selectedNodeId, onNodeSelect, pushState]
  );

  const handleSelectNode = useCallback(
    (id: string | null) => {
      setSelectedNodeId(id);
      setSelectedEdgeId(null); // Deselect edge when selecting node
      const node = id ? nodes.find((n) => n.id === id) || null : null;
      onNodeSelect?.(id, node);
    },
    [nodes, onNodeSelect]
  );

  // ============================================================================
  // Edge Operations
  // ============================================================================

  const handleAddEdge = useCallback(
    (
      source: string,
      target: string,
      data?: Record<string, unknown>
    ): string | null => {
      // Check for cycles if validation is enabled
      if (config.validation?.preventCycles) {
        if (detectCycle(nodes, edges, source, target)) {
          console.warn('Cannot add edge: would create a cycle');
          return null;
        }
      }

      // Custom validation
      if (connectionValidator) {
        const connection: Connection = {
          source,
          target,
          sourceHandle: null,
          targetHandle: null,
        };
        if (!connectionValidator(connection)) {
          return null;
        }
      }

      const id = `${source}-${target}`;
      const newEdge: Edge = {
        id,
        source,
        target,
        type: config.defaultEdgeType || 'default',
        data: data || {},
      };

      setEdges((eds) => {
        // Check if edge already exists
        if (eds.some((e) => e.source === source && e.target === target)) {
          return eds;
        }
        const updatedEdges = [...eds, newEdge];
        pushState(nodes, updatedEdges);
        return updatedEdges;
      });

      return id;
    },
    [
      config.validation?.preventCycles,
      config.defaultEdgeType,
      connectionValidator,
      nodes,
      edges,
      setEdges,
      detectCycle,
      pushState,
    ]
  );

  const handleUpdateEdge = useCallback(
    (id: string, data: Partial<Record<string, unknown>>) => {
      setEdges((eds) => {
        const updatedEdges = eds.map((edge) =>
          edge.id === id
            ? { ...edge, data: { ...edge.data, ...data } }
            : edge
        );
        pushState(nodes, updatedEdges);
        return updatedEdges;
      });
    },
    [setEdges, nodes, pushState]
  );

  const handleDeleteEdge = useCallback(
    (id: string) => {
      setEdges((eds) => {
        const updatedEdges = eds.filter((edge) => edge.id !== id);
        pushState(nodes, updatedEdges);
        return updatedEdges;
      });

      if (selectedEdgeId === id) {
        setSelectedEdgeId(null);
        onEdgeSelect?.(null, null);
      }
    },
    [setEdges, nodes, selectedEdgeId, onEdgeSelect, pushState]
  );

  const handleSelectEdge = useCallback(
    (id: string | null) => {
      setSelectedEdgeId(id);
      setSelectedNodeId(null); // Deselect node when selecting edge
      const edge = id ? edges.find((e) => e.id === id) || null : null;
      onEdgeSelect?.(id, edge);
    },
    [edges, onEdgeSelect]
  );

  // ============================================================================
  // Layout Operations
  // ============================================================================

  const handleSetLayoutDirection = useCallback(
    (direction: LayoutDirection) => {
      setLayoutDirection(direction);
      // Save to localStorage
      localStorage.setItem('flowEditor.layoutDirection', direction);
    },
    []
  );

  const handleAutoLayout = useCallback(() => {
    const layoutedNodes = applyLayout(nodes, edges);
    setNodes(layoutedNodes);
    pushState(layoutedNodes, edges);
  }, [nodes, edges, applyLayout, setNodes, pushState]);

  // ============================================================================
  // History Operations
  // ============================================================================

  const handleUndo = useCallback(() => {
    const state = undo();
    if (state) {
      setNodes(state.nodes);
      setEdges(state.edges);
    }
  }, [undo, setNodes, setEdges]);

  const handleRedo = useCallback(() => {
    const state = redo();
    if (state) {
      setNodes(state.nodes);
      setEdges(state.edges);
    }
  }, [redo, setNodes, setEdges]);

  // ============================================================================
  // Validation
  // ============================================================================

  const handleValidate = useCallback((): ValidationResult => {
    const result = validate(nodes, edges);
    setValidationResult(result);
    return result;
  }, [nodes, edges, validate]);

  // ============================================================================
  // Bulk Operations
  // ============================================================================

  const handleSetNodes = useCallback(
    (newNodes: Node[]) => {
      setNodes(newNodes);
      pushState(newNodes, edges);
    },
    [setNodes, edges, pushState]
  );

  const handleSetEdges = useCallback(
    (newEdges: Edge[]) => {
      setEdges(newEdges);
      pushState(nodes, newEdges);
    },
    [setEdges, nodes, pushState]
  );

  const handleClear = useCallback(() => {
    setNodes([]);
    setEdges([]);
    pushState([], []);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  }, [setNodes, setEdges, pushState]);

  // ============================================================================
  // React Flow Handlers
  // ============================================================================

  const handleNodesChange: OnNodesChange = useCallback(
    (changes) => {
      if (config.readonly) return;
      onNodesChange(changes);
    },
    [config.readonly, onNodesChange]
  );

  const handleEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      if (config.readonly) return;
      onEdgesChange(changes);
    },
    [config.readonly, onEdgesChange]
  );

  const handleConnect = useCallback(
    (connection: Connection) => {
      if (config.readonly) return;
      if (!connection.source || !connection.target) return;

      // Validate connection
      if (config.validation?.preventCycles) {
        if (detectCycle(nodes, edges, connection.source, connection.target)) {
          console.warn('Cannot connect: would create a cycle');
          return;
        }
      }

      if (connectionValidator && !connectionValidator(connection)) {
        return;
      }

      setEdges((eds) => {
        const updatedEdges = addEdge(
          {
            ...connection,
            type: config.defaultEdgeType || 'default',
          },
          eds
        );
        pushState(nodes, updatedEdges);
        return updatedEdges;
      });
    },
    [
      config.readonly,
      config.validation?.preventCycles,
      config.defaultEdgeType,
      connectionValidator,
      nodes,
      edges,
      setEdges,
      detectCycle,
      pushState,
    ]
  );

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      handleSelectNode(node.id);
    },
    [handleSelectNode]
  );

  const handleEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      handleSelectEdge(edge.id);
    },
    [handleSelectEdge]
  );

  const handlePaneClick = useCallback(() => {
    handleSelectNode(null);
    handleSelectEdge(null);
  }, [handleSelectNode, handleSelectEdge]);

  // ============================================================================
  // Keyboard Shortcuts
  // ============================================================================

  useEffect(() => {
    if (!config.enableUndoRedo) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        if (e.shiftKey) {
          handleRedo();
        } else {
          handleUndo();
        }
        e.preventDefault();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
        handleRedo();
        e.preventDefault();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [config.enableUndoRedo, handleUndo, handleRedo]);

  // ============================================================================
  // Load layout direction from localStorage
  // ============================================================================

  useEffect(() => {
    const saved = localStorage.getItem('flowEditor.layoutDirection');
    if (saved === 'TB' || saved === 'LR') {
      setLayoutDirection(saved);
    }
  }, []);

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <FlowEditorProvider
      config={config}
      nodes={nodes}
      edges={edges}
      selectedNodeId={selectedNodeId}
      selectedEdgeId={selectedEdgeId}
      layoutDirection={layoutDirection}
      validationResult={validationResult}
      canUndo={canUndo}
      canRedo={canRedo}
      onAddNode={handleAddNode}
      onUpdateNode={handleUpdateNode}
      onDeleteNode={handleDeleteNode}
      onSelectNode={handleSelectNode}
      onAddEdge={handleAddEdge}
      onUpdateEdge={handleUpdateEdge}
      onDeleteEdge={handleDeleteEdge}
      onSelectEdge={handleSelectEdge}
      onSetLayoutDirection={handleSetLayoutDirection}
      onAutoLayout={handleAutoLayout}
      onUndo={handleUndo}
      onRedo={handleRedo}
      onValidate={handleValidate}
      onSetNodes={handleSetNodes}
      onSetEdges={handleSetEdges}
      onClear={handleClear}
    >
      <div className={`flow-editor ${className}`} style={{ width: '100%', height: '100%' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={handleConnect}
          onNodeClick={handleNodeClick}
          onEdgeClick={handleEdgeClick}
          onPaneClick={handlePaneClick}
          nodesDraggable={!config.readonly}
          nodesConnectable={!config.readonly}
          elementsSelectable={true}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
          {config.showMinimap && (
            <MiniMap
              nodeStrokeWidth={3}
              zoomable
              pannable
              style={{ background: '#f8f8f8' }}
            />
          )}
          {config.showControls && <Controls />}
        </ReactFlow>
        {children}
      </div>
    </FlowEditorProvider>
  );
}

// ============================================================================
// Main Component (with ReactFlowProvider)
// ============================================================================

/**
 * Flow Editor Component
 *
 * A generic, reusable flow editor built on React Flow.
 * Wrap with ReactFlowProvider and pass configuration to customize.
 */
export function FlowEditor(props: FlowEditorProps) {
  return (
    <ReactFlowProvider>
      <FlowEditorInternal {...props} />
    </ReactFlowProvider>
  );
}

export default FlowEditor;
