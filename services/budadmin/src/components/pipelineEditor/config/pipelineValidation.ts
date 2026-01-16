/**
 * Workflow Validation Rules
 *
 * Workflow-specific validation rules for the DAG editor.
 * Ensures workflows are valid before execution.
 */

import type { Node, Edge } from '@xyflow/react';
import type { ValidationRule, ValidationError, ValidationResult } from '@/components/flowEditor';
import { SPECIAL_NODE_TYPES } from './pipelineNodeTypes';

// ============================================================================
// Validation Rules
// ============================================================================

/**
 * Validates that the workflow has exactly one start node
 */
export const startNodeRule: ValidationRule = (nodes: Node[]): ValidationError[] => {
  const startNodes = nodes.filter((n) => n.type === SPECIAL_NODE_TYPES.START);

  if (startNodes.length === 0) {
    return [
      {
        type: 'node',
        id: 'workflow',
        message: 'Workflow must have a start node',
        severity: 'error',
      },
    ];
  }

  if (startNodes.length > 1) {
    return startNodes.slice(1).map((node) => ({
      type: 'node' as const,
      id: node.id,
      message: 'Only one start node is allowed',
      severity: 'error' as const,
    }));
  }

  return [];
};

/**
 * Validates that all steps have unique IDs
 */
export const uniqueStepIdsRule: ValidationRule = (nodes: Node[]): ValidationError[] => {
  const errors: ValidationError[] = [];
  const stepIdMap = new Map<string, string[]>();

  nodes.forEach((node) => {
    const stepId = (node.data as Record<string, unknown>)?.stepId as string | undefined;
    if (stepId) {
      const existing = stepIdMap.get(stepId) || [];
      existing.push(node.id);
      stepIdMap.set(stepId, existing);
    }
  });

  stepIdMap.forEach((nodeIds, stepId) => {
    if (nodeIds.length > 1) {
      nodeIds.forEach((nodeId) => {
        errors.push({
          type: 'node',
          id: nodeId,
          message: `Duplicate step ID: "${stepId}"`,
          severity: 'error',
        });
      });
    }
  });

  return errors;
};

/**
 * Validates that depends_on references exist
 */
export const validDependenciesRule: ValidationRule = (nodes: Node[]): ValidationError[] => {
  const errors: ValidationError[] = [];
  const stepIds = new Set(
    nodes
      .map((n) => (n.data as Record<string, unknown>)?.stepId as string | undefined)
      .filter(Boolean)
  );

  nodes.forEach((node) => {
    const dependsOn = (node.data as Record<string, unknown>)?.depends_on as string[] | undefined;
    if (dependsOn && Array.isArray(dependsOn)) {
      dependsOn.forEach((dep) => {
        if (!stepIds.has(dep)) {
          errors.push({
            type: 'node',
            id: node.id,
            message: `Dependency "${dep}" does not exist`,
            severity: 'error',
          });
        }
      });
    }
  });

  return errors;
};

/**
 * Validates that all nodes (except start) have incoming connections
 */
export const connectedNodesRule: ValidationRule = (nodes: Node[], edges: Edge[]): ValidationError[] => {
  const errors: ValidationError[] = [];
  const nodesWithIncoming = new Set(edges.map((e) => e.target));

  nodes.forEach((node) => {
    if (node.type !== SPECIAL_NODE_TYPES.START && !nodesWithIncoming.has(node.id)) {
      errors.push({
        type: 'node',
        id: node.id,
        message: 'Node is not connected to any other node',
        severity: 'warning',
      });
    }
  });

  return errors;
};

/**
 * Validates that start node has at least one outgoing connection
 */
export const startNodeConnectedRule: ValidationRule = (nodes: Node[], edges: Edge[]): ValidationError[] => {
  const startNode = nodes.find((n) => n.type === SPECIAL_NODE_TYPES.START);
  if (!startNode) return [];

  const hasOutgoing = edges.some((e) => e.source === startNode.id);
  if (!hasOutgoing) {
    return [
      {
        type: 'node',
        id: startNode.id,
        message: 'Start node must have at least one outgoing connection',
        severity: 'warning',
      },
    ];
  }

  return [];
};

/**
 * Validates that conditional nodes have proper condition expressions
 */
export const conditionalNodeRule: ValidationRule = (nodes: Node[]): ValidationError[] => {
  const errors: ValidationError[] = [];

  nodes.forEach((node) => {
    if (node.type === SPECIAL_NODE_TYPES.CONDITIONAL || (node.data as Record<string, unknown>)?.action === 'conditional') {
      const params = (node.data as Record<string, unknown>)?.params as Record<string, unknown> | undefined;
      const condition = params?.condition || params?.expression;

      if (!condition) {
        errors.push({
          type: 'node',
          id: node.id,
          message: 'Conditional node must have a condition expression',
          severity: 'warning',
        });
      }
    }
  });

  return errors;
};

// ============================================================================
// Exported Configuration
// ============================================================================

/**
 * All workflow validation rules
 */
export const pipelineValidationRules: ValidationRule[] = [
  startNodeRule,
  uniqueStepIdsRule,
  validDependenciesRule,
  connectedNodesRule,
  startNodeConnectedRule,
  conditionalNodeRule,
];

/**
 * Run all workflow validations
 */
export function validatePipeline(nodes: Node[], edges: Edge[]): ValidationResult {
  const errors: ValidationError[] = [];

  pipelineValidationRules.forEach((rule) => {
    const ruleErrors = rule(nodes, edges);
    errors.push(...ruleErrors);
  });

  return {
    valid: errors.filter((e) => e.severity === 'error').length === 0,
    errors,
  };
}
