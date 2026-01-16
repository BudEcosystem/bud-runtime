/**
 * Workflow Conversion Hook
 *
 * Converts between DAGDefinition format and React Flow nodes/edges.
 * Handles bidirectional transformation for editing workflows.
 */

import { useCallback, useMemo } from 'react';
import type { Node, Edge } from '@xyflow/react';
import { nanoid } from 'nanoid';
import type { DAGDefinition, PipelineStep } from '@/stores/useBudPipeline';
import type { StartNodeData } from '../nodes/StartNode';
import type { StepNodeData } from '../nodes/StepNode';
import { SPECIAL_NODE_TYPES } from '../config/pipelineNodeTypes';
import { getDefaultParams, getActionMeta } from '../config/actionRegistry';

// ============================================================================
// Types
// ============================================================================

export interface PipelineFlowState {
  nodes: Node[];
  edges: Edge[];
}

export interface UsePipelineConversionReturn {
  /** Convert DAG to React Flow nodes and edges */
  dagToFlow: (dag: DAGDefinition) => PipelineFlowState;
  /** Convert React Flow state back to DAG */
  flowToDag: (nodes: Node[], edges: Edge[], baseDag: DAGDefinition) => DAGDefinition;
  /** Create initial flow state from DAG or empty workflow */
  createInitialState: (dag?: DAGDefinition) => PipelineFlowState;
  /** Create a new step node */
  createStepNode: (action: string, position?: { x: number; y: number }) => Node;
}

// ============================================================================
// Constants
// ============================================================================

const START_NODE_ID = 'start';
const DEFAULT_NODE_WIDTH = 340;
const DEFAULT_NODE_HEIGHT = 200;
const VERTICAL_SPACING = 100;
const HORIZONTAL_SPACING = 100;
const DEFAULT_EDGE_STYLE = { stroke: '#7f97a6', strokeWidth: 1, opacity: 0.6 };
const BRANCH_EDGE_STYLE = { stroke: '#c79b6a', strokeWidth: 1.1, opacity: 0.7 };

// ============================================================================
// Hook
// ============================================================================

export function usePipelineConversion(): UsePipelineConversionReturn {
  /**
   * Convert DAGDefinition to React Flow nodes and edges
   * Uses horizontal layout (left to right)
   */
  const dagToFlow = useCallback((dag: DAGDefinition): PipelineFlowState => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    // Create start node (on the left)
    const startNode: Node<StartNodeData> = {
      id: START_NODE_ID,
      type: SPECIAL_NODE_TYPES.START,
      position: { x: 0, y: 150 },
      data: {
        title: dag.name || 'Start',
      },
    };
    nodes.push(startNode);

    // Create a map of step IDs to node IDs for edge creation
    const stepIdToNodeId = new Map<string, string>();

    // Calculate positions using horizontal topological layout (left to right)
    const stepsByLevel = calculateLevels(dag.steps);
    let xOffset = DEFAULT_NODE_WIDTH + HORIZONTAL_SPACING;

    stepsByLevel.forEach((levelSteps) => {
      // Calculate vertical centering for this level
      const levelHeight = levelSteps.length * (DEFAULT_NODE_HEIGHT + VERTICAL_SPACING);
      const startY = 150 - levelHeight / 2 + DEFAULT_NODE_HEIGHT / 2;

      levelSteps.forEach((step, index) => {
        const nodeId = `step_${step.id}`;
        stepIdToNodeId.set(step.id, nodeId);

        const stepNode: Node<StepNodeData> = {
          id: nodeId,
          type: step.action, // Use action type as node type
          position: {
            x: xOffset,
            y: startY + index * (DEFAULT_NODE_HEIGHT + VERTICAL_SPACING),
          },
          data: {
            stepId: step.id,
            name: step.name,
            action: step.action,
            condition: step.condition,
            params: step.params,
            depends_on: step.depends_on,
          },
        };
        nodes.push(stepNode);
      });

      xOffset += DEFAULT_NODE_WIDTH + HORIZONTAL_SPACING;
    });

    // Track which edges we've created to avoid duplicates
    const createdEdges = new Set<string>();

    // First, create edges for conditional nodes based on their branch targets
    // This takes precedence over depends_on for branch routing
    dag.steps.forEach((step) => {
      if (step.action === 'conditional' && step.params?.branches) {
        const sourceNodeId = stepIdToNodeId.get(step.id);
        if (!sourceNodeId) return;

        const branches = step.params.branches as Array<{
          id: string;
          label: string;
          condition: string;
          target_step: string | null;
        }>;

        branches.forEach((branch) => {
          if (branch.target_step) {
            const targetNodeId = stepIdToNodeId.get(branch.target_step);
            if (targetNodeId) {
              const edgeKey = `${step.id}->${branch.target_step}`;
              if (!createdEdges.has(edgeKey)) {
                edges.push({
                  id: `edge_${step.id}_${branch.id}`,
                  source: sourceNodeId,
                  target: targetNodeId,
                  sourceHandle: 'output',
                  targetHandle: 'input',
                  type: 'smoothstep',
                  animated: true,
                  label: branch.label,
                  labelStyle: { fill: '#c8b39a', fontSize: 10 },
                  labelBgStyle: { fill: '#0E0E0E', fillOpacity: 0.85 },
                  style: BRANCH_EDGE_STYLE,
                });
                createdEdges.add(edgeKey);
              }
            }
          }
        });
      }
    });

    // Create edges based on depends_on relationships (skip if branch edge already exists)
    dag.steps.forEach((step) => {
      const targetNodeId = stepIdToNodeId.get(step.id);
      if (!targetNodeId) return;

      if (!step.depends_on || step.depends_on.length === 0) {
        // No dependencies - connect to start node
        const edgeKey = `start->${step.id}`;
        if (!createdEdges.has(edgeKey)) {
          edges.push({
            id: `edge_start_${step.id}`,
            source: START_NODE_ID,
            target: targetNodeId,
            sourceHandle: 'output',
            targetHandle: 'input',
            type: 'smoothstep',
            style: DEFAULT_EDGE_STYLE,
          });
          createdEdges.add(edgeKey);
        }
      } else {
        // Connect to each dependency (but skip if a branch edge already connects them)
        (step.depends_on || []).forEach((depId) => {
          const edgeKey = `${depId}->${step.id}`;
          // Skip if this edge was already created by branch routing
          if (createdEdges.has(edgeKey)) return;

          const sourceNodeId = stepIdToNodeId.get(depId);
          if (sourceNodeId) {
            edges.push({
              id: `edge_${depId}_${step.id}`,
              source: sourceNodeId,
              target: targetNodeId,
              sourceHandle: 'output',
              targetHandle: 'input',
              type: 'smoothstep',
              label: step.condition ? 'conditional' : undefined,
              style: DEFAULT_EDGE_STYLE,
            });
            createdEdges.add(edgeKey);
          }
        });
      }
    });

    return { nodes, edges };
  }, []);

  /**
   * Convert React Flow state back to DAGDefinition
   */
  const flowToDag = useCallback(
    (nodes: Node[], edges: Edge[], baseDag: DAGDefinition): DAGDefinition => {
      // Filter out start node and convert remaining nodes to steps
      const stepNodes = nodes.filter((n) => n.type !== SPECIAL_NODE_TYPES.START);

      // Build edge map for quick lookup (target -> sources)
      const incomingEdges = new Map<string, string[]>();
      edges.forEach((edge) => {
        const sources = incomingEdges.get(edge.target) || [];
        sources.push(edge.source);
        incomingEdges.set(edge.target, sources);
      });

      // Convert nodes to steps
      const steps: PipelineStep[] = stepNodes.map((node) => {
        const data = node.data as StepNodeData;

        // Get depends_on from incoming edges (excluding start node)
        const sources = incomingEdges.get(node.id) || [];
        const depends_on = sources
          .filter((s) => s !== START_NODE_ID)
          .map((s) => {
            // Convert node ID back to step ID
            const sourceNode = nodes.find((n) => n.id === s);
            return (sourceNode?.data as StepNodeData)?.stepId || s.replace('step_', '');
          })
          .filter(Boolean);

        return {
          id: data.stepId || node.id.replace('step_', ''),
          name: data.name || 'Unnamed Step',
          action: data.action || 'unknown',
          params: data.params || {},
          depends_on,
          condition: data.condition,
        };
      });

      return {
        ...baseDag,
        steps,
      };
    },
    []
  );

  /**
   * Create initial flow state from DAG or empty workflow
   */
  const createInitialState = useCallback(
    (dag?: DAGDefinition): PipelineFlowState => {
      if (dag && dag.steps.length > 0) {
        return dagToFlow(dag);
      }

      // Empty workflow with just start node (positioned for horizontal flow)
      return {
        nodes: [
          {
            id: START_NODE_ID,
            type: SPECIAL_NODE_TYPES.START,
            position: { x: 0, y: 150 },
            data: {
              title: dag?.name || 'New Workflow',
            },
          },
        ],
        edges: [],
      };
    },
    [dagToFlow]
  );

  /**
   * Create a new step node for a given action
   */
  const createStepNode = useCallback(
    (action: string, position?: { x: number; y: number }): Node<StepNodeData> => {
      const stepId = `step_${nanoid(5)}`;
      const actionMeta = getActionMeta(action);
      const defaultParams = getDefaultParams(action);

      return {
        id: `step_${stepId}`,
        type: action,
        position: position || { x: 500, y: 150 }, // Default position for horizontal flow
        data: {
          stepId,
          name: actionMeta.label || action,
          action,
          params: defaultParams,
          depends_on: [],
        },
      };
    },
    []
  );

  return useMemo(
    () => ({
      dagToFlow,
      flowToDag,
      createInitialState,
      createStepNode,
    }),
    [dagToFlow, flowToDag, createInitialState, createStepNode]
  );
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Calculate execution levels for steps based on dependencies
 * Returns steps grouped by their execution level (for layout)
 */
function calculateLevels(steps: PipelineStep[]): PipelineStep[][] {
  const levels: PipelineStep[][] = [];
  const stepMap = new Map(steps.map((s) => [s.id, s]));
  const assignedLevel = new Map<string, number>();

  // Find steps with no dependencies first
  const noDeps = steps.filter((s) => !s.depends_on || s.depends_on.length === 0);
  if (noDeps.length > 0) {
    levels.push(noDeps);
    noDeps.forEach((s) => assignedLevel.set(s.id, 0));
  }

  // Assign levels based on max dependency level + 1
  let changed = true;
  while (changed) {
    changed = false;
    steps.forEach((step) => {
      if (assignedLevel.has(step.id)) return;

      // Check if all dependencies have been assigned
      const depLevels = (step.depends_on || []).map((d) => assignedLevel.get(d));
      if (depLevels.every((l) => l !== undefined)) {
        const level = Math.max(...(depLevels as number[])) + 1;
        assignedLevel.set(step.id, level);

        // Ensure level array exists
        while (levels.length <= level) {
          levels.push([]);
        }
        levels[level].push(step);
        changed = true;
      }
    });
  }

  // Handle any orphaned steps (circular dependencies or missing deps)
  steps.forEach((step) => {
    if (!assignedLevel.has(step.id)) {
      if (levels.length === 0) levels.push([]);
      levels[levels.length - 1].push(step);
    }
  });

  return levels;
}

export default usePipelineConversion;
