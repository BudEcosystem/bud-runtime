'use client';

/**
 * Auto Layout Hook
 *
 * Uses dagre to automatically layout nodes in a flow graph.
 * Supports both top-to-bottom (TB) and left-to-right (LR) layouts.
 */

import { useCallback, useMemo } from 'react';
import dagre from 'dagre';
import type { Node, Edge } from '@xyflow/react';
import type { LayoutDirection, LayoutConfig, DEFAULT_LAYOUT_CONFIG } from '../core/types';

// Default node dimensions for layout calculation
const DEFAULT_NODE_WIDTH = 200;
const DEFAULT_NODE_HEIGHT = 80;

export interface UseAutoLayoutOptions {
  /** Node width for layout calculation */
  nodeWidth?: number;
  /** Node height for layout calculation */
  nodeHeight?: number;
  /** Rank separation (vertical spacing in TB, horizontal in LR) */
  rankSep?: number;
  /** Node separation (horizontal spacing in TB, vertical in LR) */
  nodeSep?: number;
  /** Edge separation */
  edgeSep?: number;
}

export interface UseAutoLayoutReturn {
  /** Apply layout to nodes */
  applyLayout: (nodes: Node[], edges: Edge[]) => Node[];
  /** Get layout direction */
  direction: LayoutDirection;
}

/**
 * Hook for auto-layout functionality using dagre
 */
export function useAutoLayout(
  direction: LayoutDirection = 'TB',
  config?: LayoutConfig
): UseAutoLayoutReturn {
  const options = useMemo<UseAutoLayoutOptions>(
    () => ({
      nodeWidth: DEFAULT_NODE_WIDTH,
      nodeHeight: DEFAULT_NODE_HEIGHT,
      rankSep: config?.rankSep ?? 80,
      nodeSep: config?.nodeSep ?? 50,
      edgeSep: config?.edgeSep ?? 10,
    }),
    [config]
  );

  const applyLayout = useCallback(
    (nodes: Node[], edges: Edge[]): Node[] => {
      if (nodes.length === 0) return nodes;

      // Create a new dagre graph
      const dagreGraph = new dagre.graphlib.Graph();
      dagreGraph.setDefaultEdgeLabel(() => ({}));

      // Configure the graph layout
      dagreGraph.setGraph({
        rankdir: direction,
        ranksep: options.rankSep,
        nodesep: options.nodeSep,
        edgesep: options.edgeSep,
        marginx: 20,
        marginy: 20,
      });

      // Add nodes to the graph
      nodes.forEach((node) => {
        // Get node dimensions from data or use defaults
        const width = (node.data as any)?.width || options.nodeWidth || DEFAULT_NODE_WIDTH;
        const height = (node.data as any)?.height || options.nodeHeight || DEFAULT_NODE_HEIGHT;

        dagreGraph.setNode(node.id, {
          width,
          height,
        });
      });

      // Add edges to the graph
      edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
      });

      // Run the layout algorithm
      dagre.layout(dagreGraph);

      // Apply the calculated positions to nodes
      const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        const width = (node.data as any)?.width || options.nodeWidth || DEFAULT_NODE_WIDTH;
        const height = (node.data as any)?.height || options.nodeHeight || DEFAULT_NODE_HEIGHT;

        // Center the node on the calculated position
        return {
          ...node,
          position: {
            x: nodeWithPosition.x - width / 2,
            y: nodeWithPosition.y - height / 2,
          },
        };
      });

      return layoutedNodes;
    },
    [direction, options]
  );

  return {
    applyLayout,
    direction,
  };
}

/**
 * Utility function to apply layout once (not a hook)
 */
export function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
  direction: LayoutDirection = 'TB',
  options: UseAutoLayoutOptions = {}
): Node[] {
  if (nodes.length === 0) return nodes;

  const nodeWidth = options.nodeWidth || DEFAULT_NODE_WIDTH;
  const nodeHeight = options.nodeHeight || DEFAULT_NODE_HEIGHT;
  const rankSep = options.rankSep || 80;
  const nodeSep = options.nodeSep || 50;
  const edgeSep = options.edgeSep || 10;

  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  dagreGraph.setGraph({
    rankdir: direction,
    ranksep: rankSep,
    nodesep: nodeSep,
    edgesep: edgeSep,
    marginx: 20,
    marginy: 20,
  });

  nodes.forEach((node) => {
    const width = (node.data as any)?.width || nodeWidth;
    const height = (node.data as any)?.height || nodeHeight;
    dagreGraph.setNode(node.id, { width, height });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  return nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const width = (node.data as any)?.width || nodeWidth;
    const height = (node.data as any)?.height || nodeHeight;

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - width / 2,
        y: nodeWithPosition.y - height / 2,
      },
    };
  });
}

export default useAutoLayout;
