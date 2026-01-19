'use client';

/**
 * Validation Hook
 *
 * Provides validation functionality for flow graphs including:
 * - Cycle detection using DFS
 * - Custom validation rules
 * - Connection validation
 */

import { useCallback, useMemo } from 'react';
import type { Node, Edge, Connection } from '@xyflow/react';
import type {
  ValidationConfig,
  ValidationResult,
  ValidationError,
  ValidationRule,
} from '../core/types';

export interface UseValidationReturn {
  /** Validate the entire flow */
  validate: (nodes: Node[], edges: Edge[]) => ValidationResult;
  /** Check if adding an edge would create a cycle */
  detectCycle: (nodes: Node[], edges: Edge[], source: string, target: string) => boolean;
  /** Validate a potential connection */
  validateConnection: (connection: Connection, nodes: Node[], edges: Edge[]) => boolean;
  /** Get validation errors for a specific node */
  getNodeErrors: (nodeId: string, result: ValidationResult) => ValidationError[];
  /** Get validation errors for a specific edge */
  getEdgeErrors: (edgeId: string, result: ValidationResult) => ValidationError[];
}

/**
 * Hook for flow validation
 */
export function useValidation(config?: ValidationConfig): UseValidationReturn {
  const preventCycles = config?.preventCycles ?? true;
  const customRules = config?.rules ?? [];

  /**
   * Detect if adding an edge from source to target would create a cycle
   * Uses DFS to check if there's a path from target to source
   */
  const detectCycle = useCallback(
    (nodes: Node[], edges: Edge[], source: string, target: string): boolean => {
      // Build adjacency list
      const adjacency = new Map<string, string[]>();
      nodes.forEach((node) => adjacency.set(node.id, []));
      edges.forEach((edge) => {
        const neighbors = adjacency.get(edge.source) || [];
        neighbors.push(edge.target);
        adjacency.set(edge.source, neighbors);
      });

      // Add the potential new edge
      const sourceNeighbors = adjacency.get(source) || [];
      sourceNeighbors.push(target);
      adjacency.set(source, sourceNeighbors);

      // DFS to detect cycle starting from target
      const visited = new Set<string>();
      const recursionStack = new Set<string>();

      function dfs(nodeId: string): boolean {
        visited.add(nodeId);
        recursionStack.add(nodeId);

        const neighbors = adjacency.get(nodeId) || [];
        for (const neighbor of neighbors) {
          if (!visited.has(neighbor)) {
            if (dfs(neighbor)) return true;
          } else if (recursionStack.has(neighbor)) {
            return true;
          }
        }

        recursionStack.delete(nodeId);
        return false;
      }

      // Check if there's a cycle starting from source
      return dfs(source);
    },
    []
  );

  /**
   * Built-in validation rules
   */
  const builtInRules = useMemo<ValidationRule[]>(() => {
    const rules: ValidationRule[] = [];

    // Cycle detection rule
    if (preventCycles) {
      rules.push((nodes, edges) => {
        const errors: ValidationError[] = [];

        // Build adjacency list
        const adjacency = new Map<string, string[]>();
        nodes.forEach((node) => adjacency.set(node.id, []));
        edges.forEach((edge) => {
          const neighbors = adjacency.get(edge.source) || [];
          neighbors.push(edge.target);
          adjacency.set(edge.source, neighbors);
        });

        // DFS to detect cycles
        const visited = new Set<string>();
        const recursionStack = new Set<string>();
        const cycleNodes = new Set<string>();

        function dfs(nodeId: string, path: string[]): boolean {
          visited.add(nodeId);
          recursionStack.add(nodeId);
          path.push(nodeId);

          const neighbors = adjacency.get(nodeId) || [];
          for (const neighbor of neighbors) {
            if (!visited.has(neighbor)) {
              if (dfs(neighbor, path)) return true;
            } else if (recursionStack.has(neighbor)) {
              // Found a cycle - mark all nodes in the cycle
              const cycleStart = path.indexOf(neighbor);
              for (let i = cycleStart; i < path.length; i++) {
                cycleNodes.add(path[i]);
              }
              return true;
            }
          }

          path.pop();
          recursionStack.delete(nodeId);
          return false;
        }

        for (const node of nodes) {
          if (!visited.has(node.id)) {
            dfs(node.id, []);
          }
        }

        // Add errors for nodes in cycles
        cycleNodes.forEach((nodeId) => {
          errors.push({
            type: 'node',
            id: nodeId,
            message: 'Node is part of a cycle',
            severity: 'error',
          });
        });

        return errors;
      });
    }

    // Orphan node detection (nodes with no connections except start node)
    rules.push((nodes, edges) => {
      const errors: ValidationError[] = [];
      const connectedNodes = new Set<string>();

      edges.forEach((edge) => {
        connectedNodes.add(edge.source);
        connectedNodes.add(edge.target);
      });

      nodes.forEach((node) => {
        // Skip start nodes (they might not have incoming edges)
        if (node.type === 'start') return;

        if (!connectedNodes.has(node.id) && nodes.length > 1) {
          errors.push({
            type: 'node',
            id: node.id,
            message: 'Node is not connected to any other node',
            severity: 'warning',
          });
        }
      });

      return errors;
    });

    // Dangling edge detection
    rules.push((nodes, edges) => {
      const errors: ValidationError[] = [];
      const nodeIds = new Set(nodes.map((n) => n.id));

      edges.forEach((edge) => {
        if (!nodeIds.has(edge.source)) {
          errors.push({
            type: 'edge',
            id: edge.id,
            message: `Edge source node "${edge.source}" does not exist`,
            severity: 'error',
          });
        }
        if (!nodeIds.has(edge.target)) {
          errors.push({
            type: 'edge',
            id: edge.id,
            message: `Edge target node "${edge.target}" does not exist`,
            severity: 'error',
          });
        }
      });

      return errors;
    });

    return rules;
  }, [preventCycles]);

  /**
   * Validate the entire flow
   */
  const validate = useCallback(
    (nodes: Node[], edges: Edge[]): ValidationResult => {
      const allErrors: ValidationError[] = [];

      // Run built-in rules
      builtInRules.forEach((rule) => {
        const errors = rule(nodes, edges);
        allErrors.push(...errors);
      });

      // Run custom rules
      customRules.forEach((rule) => {
        const errors = rule(nodes, edges);
        allErrors.push(...errors);
      });

      return {
        valid: allErrors.filter((e) => e.severity === 'error').length === 0,
        errors: allErrors,
      };
    },
    [builtInRules, customRules]
  );

  /**
   * Validate a potential connection
   */
  const validateConnection = useCallback(
    (connection: Connection, nodes: Node[], edges: Edge[]): boolean => {
      if (!connection.source || !connection.target) return false;

      // Don't allow self-connections
      if (connection.source === connection.target) return false;

      // Don't allow duplicate edges
      const exists = edges.some(
        (e) =>
          e.source === connection.source && e.target === connection.target
      );
      if (exists) return false;

      // Check for cycles
      if (preventCycles) {
        if (detectCycle(nodes, edges, connection.source, connection.target)) {
          return false;
        }
      }

      return true;
    },
    [preventCycles, detectCycle]
  );

  /**
   * Get validation errors for a specific node
   */
  const getNodeErrors = useCallback(
    (nodeId: string, result: ValidationResult): ValidationError[] => {
      return result.errors.filter((e) => e.type === 'node' && e.id === nodeId);
    },
    []
  );

  /**
   * Get validation errors for a specific edge
   */
  const getEdgeErrors = useCallback(
    (edgeId: string, result: ValidationResult): ValidationError[] => {
      return result.errors.filter((e) => e.type === 'edge' && e.id === edgeId);
    },
    []
  );

  return {
    validate,
    detectCycle,
    validateConnection,
    getNodeErrors,
    getEdgeErrors,
  };
}

export default useValidation;
