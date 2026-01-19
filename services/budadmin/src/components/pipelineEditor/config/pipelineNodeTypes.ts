/**
 * Workflow Node Types Configuration
 *
 * Registers all node types for the workflow editor.
 * This is used by the FlowEditor to render different node types.
 *
 * Note: All action types use the StepNode component, which reads
 * the action type from node data and renders dynamically based on
 * action metadata from the API.
 */

import type { NodeTypes } from '@xyflow/react';
import { StartNode } from '../nodes/StartNode';
import { StepNode } from '../nodes/StepNode';

/**
 * Node types for the workflow editor.
 *
 * - 'start': The trigger/start node
 * - 'step': Generic step node used for all action types
 *
 * The StepNode component handles all action types dynamically by reading
 * the action type from node.data and fetching metadata from the API cache.
 */
export const pipelineNodeTypes: NodeTypes = {
  start: StartNode,
  step: StepNode,
};

/**
 * Default node type for new nodes
 */
export const DEFAULT_NODE_TYPE = 'step';

/**
 * Special node types that have unique behavior
 */
export const SPECIAL_NODE_TYPES = {
  START: 'start',
  END: 'end',
  CONDITIONAL: 'conditional',
} as const;

/**
 * Node types that cannot be deleted
 */
export const UNDELETABLE_NODE_TYPES = new Set<string>([SPECIAL_NODE_TYPES.START]);

/**
 * Node types that cannot be copied
 */
export const UNCOPYABLE_NODE_TYPES = new Set<string>([SPECIAL_NODE_TYPES.START]);
