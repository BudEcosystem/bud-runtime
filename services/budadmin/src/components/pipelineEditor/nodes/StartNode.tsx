'use client';

/**
 * Start Node Component
 *
 * The trigger node that marks where workflow execution begins.
 * Green-themed styling to indicate the start point.
 */

import React, { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Icon } from '@iconify/react';

// ============================================================================
// Types
// ============================================================================

export interface StartNodeData extends Record<string, unknown> {
  title?: string;
}

export type StartNodeProps = NodeProps<Node<StartNodeData>>;

// ============================================================================
// Styles (matching StepNode theme)
// ============================================================================

const nodeStyles: React.CSSProperties = {
  background: '#0E0E0E',
  borderRadius: '12px',
  padding: '20px',
  border: '1px solid #333333',
  boxShadow: '0 2px 6px 0 rgba(0, 0, 0, 0.04), 0 4px 12px 0 rgba(0, 0, 0, 0.02)',
  minWidth: '280px',
  maxWidth: '360px',
  position: 'relative',
  borderLeft: '3px solid #52c41a',
};

const selectedNodeStyles: React.CSSProperties = {
  boxShadow: '0 0 0 2px #52c41a',
};

const headerStyles: React.CSSProperties = {
  background: 'transparent',
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
};

const iconContainerStyles: React.CSSProperties = {
  fontSize: '18px',
  width: '36px',
  height: '36px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: '#52c41a15',
  border: 'none',
  borderRadius: '8px',
  color: '#52c41a',
  flexShrink: 0,
};

const titleStyles: React.CSSProperties = {
  fontSize: '14px',
  fontWeight: '600',
  color: '#FFFFFF',
  margin: 0,
  background: 'transparent',
};

const subtitleStyles: React.CSSProperties = {
  color: '#808080',
  fontSize: '12px',
  marginTop: '2px',
};

const handleStyles: React.CSSProperties = {
  width: '10px',
  height: '10px',
  background: '#555555',
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
        <span style={iconContainerStyles}>
          <Icon icon="ph:play-bold" style={{ width: 20, height: 20 }} />
        </span>
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
