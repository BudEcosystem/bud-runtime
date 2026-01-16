/**
 * Workflow Node Types Configuration
 *
 * Registers all node types for the workflow editor.
 * This is used by the FlowEditor to render different node types.
 */

import type { NodeTypes } from '@xyflow/react';
import { StartNode } from '../nodes/StartNode';
import { StepNode } from '../nodes/StepNode';
import { allActions } from './actionRegistry';

/**
 * Node types for the workflow editor
 */
export const pipelineNodeTypes: NodeTypes = {
  // Start trigger node
  start: StartNode,

  // Step nodes - all actions use the same StepNode component
  // which reads the action type from node data
  step: StepNode,

  // Register all action types to use StepNode
  // This allows both 'step' type and specific action types
  ...Object.fromEntries(allActions.map((action) => [action.value, StepNode])),
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
