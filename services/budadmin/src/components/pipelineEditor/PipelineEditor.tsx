'use client';

/**
 * Workflow Editor Component
 *
 * Main workflow DAG editor using React Flow.
 * Provides visual editing of workflow steps with drag-and-drop,
 * connection validation, and undo/redo support.
 */

import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
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
import { ActionConfigPanel, type ActionConfigPanelRef } from './components/ActionConfigPanel';

import type { DAGDefinition, PipelineStep } from '@/stores/useBudPipeline';
import { pipelineNodeTypes, SPECIAL_NODE_TYPES, UNDELETABLE_NODE_TYPES } from './config/pipelineNodeTypes';
import { validatePipeline } from './config/pipelineValidation';
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

export type FlushResult = {
  stepId: string;
  updates: { name?: string; params?: Record<string, unknown>; condition?: string };
} | null | false;

export interface PipelineEditorRef {
  /** Flushes unsaved action config panel changes. Returns updates if flushed, null if nothing to flush, false if validation failed. */
  flushUnsavedActionChanges: () => Promise<FlushResult>;
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
    providers?: SelectOption[];
    providerTypeMap?: Record<string, string>;
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
  overflow: 'hidden', // Prevent sidebar from overflowing
};

const defaultEdgeStyle: React.CSSProperties = {
  stroke: '#7f97a6',
  strokeWidth: 1,
  opacity: 0.6,
};

const sidebarStyles: React.CSSProperties = {
  position: 'absolute',
  right: '16px',
  top: '16px',
  bottom: '16px',
  width: '280px',
  maxHeight: 'calc(100vh - 140px)', // Ensure it doesn't overflow viewport
  background: '#0a0a0a',
  border: '1px solid #262626',
  borderRadius: '12px',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  boxShadow: '0 4px 24px rgba(0, 0, 0, 0.4)',
  zIndex: 10,
};

const sidebarHeaderStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '12px',
  paddingLeft: '16px',
  gap: '12px',
  minHeight: '56px',
  boxSizing: 'border-box',
};

const sidebarTitleStyles: React.CSSProperties = {
  fontSize: '13px',
  fontWeight: 600,
  color: '#888',
  letterSpacing: '0.02em',
  flexShrink: 0,
};

const sidebarSearchIconStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '32px',
  height: '32px',
  borderRadius: '6px',
  cursor: 'pointer',
  color: '#666',
  transition: 'all 0.15s ease',
  flexShrink: 0,
};

const sidebarSearchExpandedStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  padding: '0 10px',
  height: '32px',
  backgroundColor: '#161616',
  borderRadius: '8px',
  border: '1px solid #252525',
  flex: 1,
  boxSizing: 'border-box',
};

const sidebarSearchInputStyles: React.CSSProperties = {
  flex: 1,
  border: 'none',
  outline: 'none',
  fontSize: '12px',
  color: '#fff',
  backgroundColor: 'transparent',
  width: '100%',
};

const paletteContainerStyles: React.CSSProperties = {
  flex: 1,
  overflow: 'hidden',
  minHeight: 0, // Important for flex children to properly shrink
};

const helpTextStyles: React.CSSProperties = {
  padding: '12px 16px',
  borderTop: '1px solid #1a1a1a',
  background: '#080808',
  color: '#555',
  fontSize: '11px',
  textAlign: 'center',
  borderRadius: '0 0 12px 12px',
};

// ============================================================================
// Inner Editor (needs ReactFlowProvider)
// ============================================================================

const PipelineEditorInner = forwardRef<PipelineEditorRef, PipelineEditorProps>(function PipelineEditorInner({
  dag,
  onNodeClick,
  onAddStep,
  onSave,
  onStepUpdate,
  onStepDelete,
  readonly = false,
  dataSources,
  loadingDataSources,
}: PipelineEditorProps, ref) {
  // Conversion utilities
  const { createInitialState, flowToDag, createStepNode } = usePipelineConversion();

  // Dynamic actions from API (with fallback to static definitions)
  const { categories: apiCategories, isLoading: actionsLoading } = useActions();

  // Flow state
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  const [actionSearch, setActionSearch] = useState('');
  const [searchExpanded, setSearchExpanded] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const actionConfigPanelRef = useRef<ActionConfigPanelRef>(null);

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

      // Count existing step nodes (excluding start node)
      const stepNodes = nodes.filter((n) => n.type !== SPECIAL_NODE_TYPES.START);
      const stepCount = stepNodes.length;

      // Position new nodes to the right of start node with vertical stacking
      // Use grid-aligned values (snap grid is 20x20)
      // x=440 places node to the right of start node (which is at x=0, width ~280-360)
      // First node at y=140 (same as start node), subsequent nodes 140px below
      const newNode = createStepNode(action, {
        x: 440,
        y: 140 + stepCount * 140,
      });
      setNodes((nds) => [...nds, newNode]);

      // Notify parent
      onAddStep?.(action);
    },
    [readonly, createStepNode, nodes, onAddStep]
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

  // Build node palette config from API categories
  const paletteConfig: NodePaletteConfig = useMemo(() => {
    const categories = apiCategories.map((cat) => ({
      id: cat.name.toLowerCase().replace(/\s+/g, '-'),
      label: cat.name,
      collapsed: false,
    }));

    const items = apiCategories.flatMap((cat) =>
      cat.actions.map((action) => ({
        type: action.type,
        label: action.name,
        description: action.description,
        icon: action.icon || '⚙️',
        color: action.color || '#8c8c8c',
        categoryId: cat.name.toLowerCase().replace(/\s+/g, '-'),
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

  // Expose flush method so parent can auto-save unsaved action changes
  useImperativeHandle(ref, () => ({
    flushUnsavedActionChanges: async () => {
      if (!configPanelOpen || !selectedStepData) return null;
      if (!actionConfigPanelRef.current) return null;

      const result = await actionConfigPanelRef.current.flush();
      if (!result) return false; // validation failed

      // Propagate updates through the normal callback chain
      handleStepUpdate(result);

      return {
        stepId: selectedStepData.stepId || '',
        updates: result,
      };
    },
  }), [configPanelOpen, selectedStepData, handleStepUpdate]);

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
          fitViewOptions={{
            maxZoom: 0.75,
            padding: 0.3,
          }}
          snapToGrid
          snapGrid={[20, 20]}
          defaultEdgeOptions={{
            type: 'smoothstep',
            animated: false,
            style: defaultEdgeStyle,
          }}
          style={{ background: '#060606' }}
        >
          <Background
            variant={BackgroundVariant.Dots}
            color="rgba(255, 255, 255, 0.25)"
            gap={24}
            size={1.5}
          />
          <PipelineToolbar
            position="bottom-left"
            showFitView={true}
            showAutoLayout={false}
            customActions={[]}
          />
        </ReactFlow>

        {/* Config Panel (shown when step node is selected in edit mode) */}
        {!readonly && configPanelOpen && selectedStepData && (
          <ActionConfigPanel
            ref={actionConfigPanelRef}
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

        {/* Action Sidebar (floating) */}
        {!readonly && !configPanelOpen && (
          <div style={sidebarStyles}>
            <div style={sidebarHeaderStyles}>
              <span style={sidebarTitleStyles}>Actions</span>
              {searchExpanded ? (
                <div style={sidebarSearchExpandedStyles}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth="2">
                    <circle cx="11" cy="11" r="8" />
                    <path d="m21 21-4.3-4.3" />
                  </svg>
                  <input
                    ref={searchInputRef}
                    type="text"
                    placeholder="Search..."
                    value={actionSearch}
                    onChange={(e) => setActionSearch(e.target.value)}
                    onBlur={() => {
                      if (!actionSearch) {
                        setSearchExpanded(false);
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Escape') {
                        setActionSearch('');
                        setSearchExpanded(false);
                      }
                    }}
                    style={sidebarSearchInputStyles}
                    autoFocus
                  />
                </div>
              ) : (
                <div
                  style={{
                    ...sidebarSearchIconStyles,
                    backgroundColor: actionSearch ? '#161616' : 'transparent',
                  }}
                  onClick={() => {
                    setSearchExpanded(true);
                    setTimeout(() => searchInputRef.current?.focus(), 0);
                  }}
                  title="Search actions"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="11" cy="11" r="8" />
                    <path d="m21 21-4.3-4.3" />
                  </svg>
                </div>
              )}
            </div>
            <div style={paletteContainerStyles}>
              <NodePalette
                config={{ ...paletteConfig, searchable: false }}
                onItemClick={(item) => handleAddAction(item.type)}
                mimeType="application/reactflow-node"
                theme="dark"
                searchValue={actionSearch}
                onSearchChange={setActionSearch}
              />
            </div>
            <div style={helpTextStyles}>Click or drag to add action</div>
          </div>
        )}
      </div>
    </div>
  );
});

// ============================================================================
// Main Component (with Provider)
// ============================================================================

export const PipelineEditor = forwardRef<PipelineEditorRef, PipelineEditorProps>(function PipelineEditor(props, ref) {
  return (
    <ReactFlowProvider>
      <PipelineEditorInner {...props} ref={ref} />
    </ReactFlowProvider>
  );
});

export default PipelineEditor;
