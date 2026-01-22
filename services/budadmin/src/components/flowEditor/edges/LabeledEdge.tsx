'use client';

/**
 * Labeled Edge Component
 *
 * An edge with optional label, condition badge, and styling options.
 */

import React, { memo } from 'react';
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
  type Edge,
} from '@xyflow/react';

// ============================================================================
// Types
// ============================================================================

export interface LabeledEdgeData extends Record<string, unknown> {
  /** Label text */
  label?: string;
  /** Condition expression (displayed as badge) */
  condition?: string;
  /** Whether the edge is animated */
  animated?: boolean;
  /** Edge color */
  color?: string;
  /** Whether the edge is dashed */
  dashed?: boolean;
  /** Edge stroke width */
  strokeWidth?: number;
}

export type LabeledEdgeProps = EdgeProps<Edge<LabeledEdgeData>>;

// ============================================================================
// Component
// ============================================================================

function LabeledEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
  selected,
}: LabeledEdgeProps) {
  // Get bezier path
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  // Compute edge style
  const edgeStyle: React.CSSProperties = {
    ...style,
    stroke: selected ? '#3b82f6' : (data?.color || '#64748b'),
    strokeWidth: data?.strokeWidth || 2,
    strokeDasharray: data?.dashed ? '5,5' : undefined,
  };

  // Determine if we should show a label
  const showLabel = data?.label || data?.condition;

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={edgeStyle}
        className={data?.animated ? 'animated' : ''}
      />

      {showLabel && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
            }}
            className="nodrag nopan"
          >
            {/* Condition badge */}
            {data?.condition && (
              <div
                style={{
                  fontSize: '10px',
                  fontFamily: 'monospace',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  backgroundColor: selected ? '#dbeafe' : '#f1f5f9',
                  border: `1px solid ${selected ? '#3b82f6' : '#e2e8f0'}`,
                  color: selected ? '#1e40af' : '#475569',
                  whiteSpace: 'nowrap',
                  maxWidth: '150px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
                title={data.condition}
              >
                {data.condition}
              </div>
            )}

            {/* Regular label */}
            {data?.label && !data?.condition && (
              <div
                style={{
                  fontSize: '11px',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  backgroundColor: selected ? '#dbeafe' : '#ffffff',
                  border: `1px solid ${selected ? '#3b82f6' : '#e2e8f0'}`,
                  color: selected ? '#1e40af' : '#64748b',
                  whiteSpace: 'nowrap',
                }}
              >
                {data.label}
              </div>
            )}
          </div>
        </EdgeLabelRenderer>
      )}

      {/* Animated path (if animated) */}
      {data?.animated && (
        <style>
          {`
            .react-flow__edge-path.animated {
              stroke-dasharray: 5;
              animation: dashdraw 0.5s linear infinite;
            }
            @keyframes dashdraw {
              from {
                stroke-dashoffset: 10;
              }
            }
          `}
        </style>
      )}
    </>
  );
}

export const LabeledEdge = memo(LabeledEdgeComponent);
export default LabeledEdge;
