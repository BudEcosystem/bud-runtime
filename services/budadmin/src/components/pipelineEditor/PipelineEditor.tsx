'use client';

/**
 * Workflow Editor Component
 *
 * Main workflow DAG editor using React Flow.
 * Provides visual editing of workflow steps with drag-and-drop,
 * connection validation, and undo/redo support.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  type Node,
  type Edge,
  type Connection,
  type OnNodesChange,
  type OnEdgesChange,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import {
  NodePalette,
  useDragAndDrop,
  type NodePaletteConfig,
} from '@/components/flowEditor';
import { PipelineToolbar } from './components/PipelineToolbar';
import { ActionConfigPanel } from './components/ActionConfigPanel';

import type { DAGDefinition, PipelineStep } from '@/stores/useBudPipeline';
import { pipelineNodeTypes, SPECIAL_NODE_TYPES, UNDELETABLE_NODE_TYPES } from './config/pipelineNodeTypes';
import { validatePipeline } from './config/pipelineValidation';
import { actionCategories } from './config/actionRegistry';
import { useActions } from 'src/hooks/useActions';
import { usePipelineConversion } from './hooks/usePipelineConversion';
import type { StepNodeData } from './nodes/StepNode';

// ============================================================================
// Types
// ============================================================================

export interface SelectOption {
  label: string;
  value: string;
}

export interface PipelineEditorProps {
  /** The DAG definition to edit */
  dag: DAGDefinition;
  /** Callback when a node is clicked */
  onNodeClick?: (nodeType: string, nodeId: string, data: Record<string, unknown>) => void;
  /** Callback when a new step is added */
  onAddStep?: (action: string) => void;
  /** Callback when the workflow is saved */
  onSave?: (dag: DAGDefinition) => void;
  /** Callback when a step is updated */
  onStepUpdate?: (stepId: string, updates: Partial<PipelineStep>) => void;
  /** Callback when a step is deleted */
  onStepDelete?: (stepId: string) => void;
  /** Whether the editor is read-only */
  readonly?: boolean;
  /** Data sources for parameter dropdowns */
  dataSources?: {
    models?: SelectOption[];
    clusters?: SelectOption[];
    deployments?: SelectOption[];
    projects?: SelectOption[];
    endpoints?: SelectOption[];
  };
  /** Loading states for data sources */
  loadingDataSources?: Set<string>;
}

// ============================================================================
// Styles
// ============================================================================

const containerStyles: React.CSSProperties = {
  display: 'flex',
  width: '100%',
  height: '100%',
  background: '#060606',
};

const canvasContainerStyles: React.CSSProperties = {
  flex: 1,
  position: 'relative',
  height: '100%',
  minHeight: 0, // Important for flex children to properly shrink
};

const defaultEdgeStyle: React.CSSProperties = {
  stroke: '#7f97a6',
  strokeWidth: 1,
  opacity: 0.6,
};

const sidebarStyles: React.CSSProperties = {
  width: '280px',
  height: '100%',
  background: '#141414',
  borderLeft: '1px solid #333',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
};

const sidebarHeaderStyles: React.CSSProperties = {
  padding: '16px',
  borderBottom: '1px solid #333',
  fontSize: '14px',
  fontWeight: 600,
  color: '#fff',
};

const paletteContainerStyles: React.CSSProperties = {
  flex: 1,
  overflow: 'hidden',
  minHeight: 0, // Important for flex children to properly shrink
};

const helpTextStyles: React.CSSProperties = {
  padding: '12px 16px',
  borderTop: '1px solid #333',
  background: '#0a0a0a',
  color: '#666',
  fontSize: '11px',
  textAlign: 'center',
};

// ============================================================================
// Inner Editor (needs ReactFlowProvider)
// ============================================================================

function PipelineEditorInner({
  dag,
  onNodeClick,
  onAddStep,
  onSave,
  onStepUpdate,
  onStepDelete,
  readonly = false,
  dataSources,
  loadingDataSources,
}: PipelineEditorProps) {
  // Conversion utilities
  const { createInitialState, flowToDag, createStepNode } = usePipelineConversion();

  // Dynamic actions from API (with fallback to static definitions)
  const { categories: apiCategories, isLoading: actionsLoading } = useActions();

  // Flow state
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [configPanelOpen, setConfigPanelOpen] = useState(false);

  // Get selected node data
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return nodes.find((n) => n.id === selectedNodeId);
  }, [nodes, selectedNodeId]);

  const selectedStepData = useMemo(() => {
    if (!selectedNode || selectedNode.type === SPECIAL_NODE_TYPES.START) return null;
    return selectedNode.data as StepNodeData;
  }, [selectedNode]);

  // Get available steps for branch target selection (excluding current node and start node)
  const availableSteps = useMemo(() => {
    return nodes
      .filter((n) => n.type !== SPECIAL_NODE_TYPES.START && n.id !== selectedNodeId)
      .map((n) => {
        const data = n.data as StepNodeData;
        return {
          stepId: data.stepId || n.id,
          name: data.name || data.action || n.id,
        };
      });
  }, [nodes, selectedNodeId]);

  // Initialize from DAG
  useEffect(() => {
    const { nodes: initialNodes, edges: initialEdges } = createInitialState(dag);
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [dag, createInitialState]);

  // Handle node changes
  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      // Filter out deletion of protected nodes
      const filteredChanges = changes.filter((change) => {
        if (change.type === 'remove') {
          const node = nodes.find((n) => n.id === change.id);
          if (node && UNDELETABLE_NODE_TYPES.has(node.type || '')) {
            return false;
          }
        }
        return true;
      });

      setNodes((nds) => applyNodeChanges(filteredChanges, nds));
    },
    [nodes]
  );

  // Handle edge changes
  const onEdgesChange: OnEdgesChange = useCallback((changes) => {
    setEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  // Handle new connections
  const onConnect = useCallback(
    (connection: Connection) => {
      // Validate connection (no cycles, etc.)
      const testEdges = addEdge(connection, edges);
      const validation = validatePipeline(nodes, testEdges);

      // Check for cycle errors
      const hasCycleError = validation.errors.some(
        (e) => e.message.toLowerCase().includes('cycle')
      );

      if (!hasCycleError) {
        setEdges((eds) => addEdge(connection, eds));
      }
    },
    [nodes, edges]
  );

  // Handle node click
  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      setSelectedNodeId(node.id);
      // Open config panel for step nodes (not start node) only in edit mode
      if (node.type !== SPECIAL_NODE_TYPES.START) {
        // Only open config panel in edit mode (not readonly)
        if (!readonly) {
          setConfigPanelOpen(true);
        }
        const data = node.data as StepNodeData;
        onNodeClick?.(node.type || 'step', node.id, data as Record<string, unknown>);
      }
    },
    [onNodeClick, readonly]
  );

  // Handle pane click (deselect)
  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null);
    setConfigPanelOpen(false);
  }, []);

  // Handle step update from config panel
  const handleStepUpdate = useCallback(
    (updates: { name?: string; params?: Record<string, unknown>; condition?: string }) => {
      if (!selectedNodeId) return;

      // Update local node data
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id === selectedNodeId) {
            const data = n.data as StepNodeData;
            return {
              ...n,
              data: {
                ...data,
                name: updates.name ?? data.name,
                params: updates.params ?? data.params,
                condition: updates.condition,
              },
            };
          }
          return n;
        })
      );

      // Handle branch-based edge creation for conditional nodes
      if (updates.params?.branches && selectedStepData?.action === 'conditional') {
        const branches = updates.params.branches as Array<{
          id: string;
          label: string;
          condition: string;
          target_step: string | null;
        }>;

        // Remove old edges from this conditional node
        setEdges((eds) => {
          // Keep edges that are not from this source node
          const nonConditionalEdges = eds.filter((e) => e.source !== selectedNodeId);

          // Create new edges for each branch with a target
          const branchEdges: Edge[] = branches
            .filter((branch) => branch.target_step)
            .map((branch) => {
              // Find the node with matching stepId
              const targetNode = nodes.find((n) => {
                const data = n.data as StepNodeData;
                return data.stepId === branch.target_step;
              });

              return {
                id: `${selectedNodeId}-${branch.id}`,
                source: selectedNodeId,
                target: targetNode?.id || `step_${branch.target_step}`,
                type: 'smoothstep',
                animated: true,
                label: branch.label,
                labelStyle: { fill: '#aaa', fontSize: 10 },
                labelBgStyle: { fill: '#1a1a1a', fillOpacity: 0.9 },
                style: { stroke: '#fa8c16' },
              };
            });

          return [...nonConditionalEdges, ...branchEdges];
        });
      }

      // Notify parent
      if (onStepUpdate && selectedStepData?.stepId) {
        onStepUpdate(selectedStepData.stepId, {
          name: updates.name,
          params: updates.params,
          condition: updates.condition,
        });
      }
    },
    [selectedNodeId, selectedStepData, onStepUpdate, nodes]
  );

  // Handle step deletion from config panel
  const handleStepDelete = useCallback(() => {
    if (!selectedNodeId || !selectedStepData) return;

    // Remove node and connected edges
    setNodes((nds) => nds.filter((n) => n.id !== selectedNodeId));
    setEdges((eds) =>
      eds.filter((e) => e.source !== selectedNodeId && e.target !== selectedNodeId)
    );

    // Close panel
    setSelectedNodeId(null);
    setConfigPanelOpen(false);

    // Notify parent
    if (onStepDelete && selectedStepData.stepId) {
      onStepDelete(selectedStepData.stepId);
    }
  }, [selectedNodeId, selectedStepData, onStepDelete]);

  // Handle adding a new step from the sidebar
  const handleAddAction = useCallback(
    (action: string) => {
      if (readonly) return;

      // Create new node at a default position
      const newNode = createStepNode(action, { x: 250, y: nodes.length * 150 + 100 });
      setNodes((nds) => [...nds, newNode]);

      // Notify parent
      onAddStep?.(action);
    },
    [readonly, createStepNode, nodes.length, onAddStep]
  );

  // Handle dropping a node from the palette
  const { onDragOver, onDrop } = useDragAndDrop({
    onDrop: (type, position) => {
      if (readonly) return;

      const newNode = createStepNode(type, position);
      setNodes((nds) => [...nds, newNode]);
      onAddStep?.(type);
    },
    mimeType: 'application/reactflow-node',
  });

  // Build node palette config from action categories
  // Uses API categories if available, falls back to static definitions
  const paletteConfig: NodePaletteConfig = useMemo(() => {
    // Use API categories if they're loaded, otherwise fall back to static
    const categories =
      apiCategories && apiCategories.length > 0
        ? apiCategories.map((cat) => ({
            id: cat.name.toLowerCase().replace(/\s+/g, '-'),
            label: cat.name,
            collapsed: false,
          }))
        : actionCategories.map((cat) => ({
            id: cat.category.toLowerCase().replace(/\s+/g, '-'),
            label: cat.category,
            collapsed: false,
          }));

    // Build items from API categories or static definitions
    const items =
      apiCategories && apiCategories.length > 0
        ? apiCategories.flatMap((cat) =>
            cat.actions.map((action) => ({
              type: action.type,
              label: action.name,
              description: action.description,
              icon: action.icon || '⚙️',
              color: action.color || '#8c8c8c',
              categoryId: cat.name.toLowerCase().replace(/\s+/g, '-'),
            }))
          )
        : actionCategories.flatMap((cat) =>
            cat.actions.map((action) => ({
              type: action.value,
              label: action.label,
              description: action.description,
              icon: action.icon,
              color: action.color,
              categoryId: cat.category.toLowerCase().replace(/\s+/g, '-'),
            }))
          );

    return {
      categories,
      items,
      searchable: true,
      collapsible: true,
    };
  }, [apiCategories]);

  // Save workflow
  const handleSave = useCallback(() => {
    if (onSave) {
      const updatedDag = flowToDag(nodes, edges, dag);
      onSave(updatedDag);
    }
  }, [nodes, edges, dag, flowToDag, onSave]);

  return (
    <div style={containerStyles}>
      {/* Canvas Area */}
      <div
        style={canvasContainerStyles}
        onDragOver={onDragOver}
        onDrop={onDrop}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={handleNodeClick}
          onPaneClick={handlePaneClick}
          nodeTypes={pipelineNodeTypes}
          fitView
          snapToGrid
          snapGrid={[20, 20]}
          defaultEdgeOptions={{
            type: 'smoothstep',
            animated: false,
            style: defaultEdgeStyle,
          }}
          style={{ background: '#060606' }}
        >
          <Background color="#2a2a2a" gap={8} />
          <PipelineToolbar
            position="bottom-left"
            showFitView={true}
            showAutoLayout={false}
            customActions={[]}
          />
        </ReactFlow>
      </div>

      {/* Config Panel (shown when step node is selected in edit mode) */}
      {!readonly && configPanelOpen && selectedStepData && (
        <ActionConfigPanel
          key={`config-${selectedStepData.stepId}`}
          stepId={selectedStepData.stepId || ''}
          stepName={selectedStepData.name || ''}
          action={selectedStepData.action || ''}
          params={selectedStepData.params || {}}
          condition={selectedStepData.condition}
          onUpdate={handleStepUpdate}
          onClose={() => setConfigPanelOpen(false)}
          onDelete={!readonly ? handleStepDelete : undefined}
          dataSources={dataSources}
          loadingDataSources={loadingDataSources}
          availableSteps={availableSteps}
        />
      )}

      {/* Action Sidebar */}
      {!readonly && !configPanelOpen && (
        <div style={sidebarStyles}>
          <div style={sidebarHeaderStyles}>Actions</div>
          <div style={paletteContainerStyles}>
            <NodePalette
              config={paletteConfig}
              onItemClick={(item) => handleAddAction(item.type)}
              mimeType="application/reactflow-node"
              theme="dark"
            />
          </div>
          <div style={helpTextStyles}>Click or drag to add action</div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component (with Provider)
// ============================================================================

export function PipelineEditor(props: PipelineEditorProps) {
  return (
    <ReactFlowProvider>
      <PipelineEditorInner {...props} />
    </ReactFlowProvider>
  );
}

export default PipelineEditor;
