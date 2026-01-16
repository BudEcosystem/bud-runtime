'use client';

/**
 * Start Node Component
 *
 * The trigger node that marks where workflow execution begins.
 * Green-themed styling to indicate the start point.
 */

import React, { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';

// ============================================================================
// Types
// ============================================================================

export interface StartNodeData extends Record<string, unknown> {
  title?: string;
}

export type StartNodeProps = NodeProps<Node<StartNodeData>>;

// ============================================================================
// Styles (matching existing FlowGram theme)
// ============================================================================

const nodeStyles: React.CSSProperties = {
  background: '#0E0E0E',
  borderRadius: '8px',
  padding: '12px',
  border: '1px solid rgba(6, 7, 9, 0.15)',
  boxShadow: '0 2px 6px 0 rgba(0, 0, 0, 0.04), 0 4px 12px 0 rgba(0, 0, 0, 0.02)',
  minWidth: '180px',
  maxWidth: '220px',
  position: 'relative',
};

const selectedNodeStyles: React.CSSProperties = {
  boxShadow: '0 0 0 2px #52c41a',
};

const headerStyles: React.CSSProperties = {
  background: 'transparent',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
};

const iconContainerStyles: React.CSSProperties = {
  fontSize: '14px',
  width: '28px',
  height: '28px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: '#FFFFFF08',
  border: '1px solid #1F1F1F',
  borderRadius: '6px',
  color: '#52c41a',
};

const titleStyles: React.CSSProperties = {
  fontSize: '13px',
  fontWeight: '600',
  color: '#EEEEEE',
  margin: 0,
  background: 'transparent',
};

const subtitleStyles: React.CSSProperties = {
  color: '#52c41a',
  fontSize: '10px',
  textTransform: 'uppercase',
  letterSpacing: '0.3px',
};

const handleStyles: React.CSSProperties = {
  width: '12px',
  height: '12px',
  background: '#93bfe2',
  border: '2px solid #0E0E0E',
};

// ============================================================================
// Component
// ============================================================================

function StartNodeComponent({ data, selected }: StartNodeProps) {
  const nodeData = data as StartNodeData;
  const title = nodeData?.title || 'Start';

  return (
    <div
      className="start-node"
      style={{
        ...nodeStyles,
        ...(selected ? selectedNodeStyles : {}),
      }}
    >
      {/* Card Header */}
      <div style={headerStyles}>
        <span style={iconContainerStyles}>{'\u25B6\uFE0F'}</span>
        <div style={{ flex: 1 }}>
          <h3 style={titleStyles}>{title}</h3>
          <div style={subtitleStyles}>Trigger</div>
        </div>
      </div>

      {/* Output Handle (Right side for horizontal flow) */}
      <Handle type="source" position={Position.Right} id="output" style={handleStyles} />
    </div>
  );
}

export const StartNode = memo(StartNodeComponent);
export default StartNode;
