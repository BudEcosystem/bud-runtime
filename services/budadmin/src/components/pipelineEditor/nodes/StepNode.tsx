'use client';

/**
 * Step Node Component
 *
 * Represents a workflow action step. Displays action type, name,
 * step ID, condition (if any), and parameter preview.
 */

import React, { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { Icon } from '@iconify/react';
import { getActionMeta } from '../config/actionRegistry';

// Icon mapping for action icon names to iconify identifiers
const ICON_MAP: Record<string, string> = {
  // Model Operations
  'database-plus': 'ph:database-bold',
  'cloud-upload': 'ph:cloud-arrow-up-bold',
  'chart-bar': 'ph:chart-bar-bold',
  'trash': 'ph:trash-bold',

  // Cluster Operations
  'heart-pulse': 'ph:heartbeat-bold',
  'server-x': 'ph:x-circle-bold',
  'server-plus': 'ph:plus-circle-bold',

  // Deployment Operations
  'rocket': 'ph:rocket-launch-bold',
  'shield': 'ph:shield-bold',
  'trending-up': 'ph:trend-up-bold',
  'arrows-alt': 'ph:arrows-out-bold',

  // Integration Operations
  'globe': 'ph:globe-bold',
  'bell': 'ph:bell-bold',
  'link': 'ph:link-bold',

  // Simulation
  'beaker': 'ph:flask-bold',

  // Control Flow
  'note': 'ph:note-bold',
  'timer': 'ph:timer-bold',
  'clock': 'ph:clock-bold',
  'git-branch': 'ph:git-branch-bold',
  'swap': 'ph:swap-bold',
  'stack': 'ph:stack-bold',
  'arrow-square-out': 'ph:arrow-square-out-bold',
  'x-circle': 'ph:x-circle-bold',
};

// Check if a string is an emoji
const isEmoji = (str: string): boolean => {
  if (!str || str.length === 0) return false;
  // Simple check: emoji strings typically have length > 1 due to surrogate pairs
  // and consist of high surrogate characters (0xD800-0xDBFF)
  const codePoint = str.codePointAt(0);
  if (!codePoint) return false;
  // Common emoji ranges: emoticons, symbols, pictographs
  return codePoint >= 0x1F300 || (codePoint >= 0x2600 && codePoint <= 0x27BF);
};

// ============================================================================
// Types
// ============================================================================

export interface StepNodeData extends Record<string, unknown> {
  stepId?: string;
  name?: string;
  action?: string;
  condition?: string;
  params?: Record<string, unknown>;
  depends_on?: string[];
}

export type StepNodeProps = NodeProps<Node<StepNodeData>>;

// ============================================================================
// Styles (matching existing FlowGram theme)
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
};

const selectedNodeStyles: React.CSSProperties = {
  boxShadow: '0 0 0 2px #1890ff',
};

const headerStyles: React.CSSProperties = {
  background: 'transparent',
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
};

const titleStyles: React.CSSProperties = {
  fontSize: '14px',
  fontWeight: '600',
  color: '#FFFFFF',
  margin: 0,
  background: 'transparent',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  maxWidth: '260px',
};

const conditionBadgeStyles: React.CSSProperties = {
  fontSize: '9px',
  color: '#faad14',
  background: '#faad1420',
  padding: '2px 6px',
  borderRadius: '4px',
  marginTop: '4px',
  display: 'inline-block',
};

const branchContainerStyles: React.CSSProperties = {
  marginTop: '8px',
  borderTop: '1px solid #333',
  paddingTop: '8px',
};

const branchLabelStyles: React.CSSProperties = {
  fontSize: '9px',
  color: '#888',
  marginBottom: '4px',
  textTransform: 'uppercase',
  letterSpacing: '0.3px',
};

const branchItemStyles: React.CSSProperties = {
  fontSize: '10px',
  color: '#aaa',
  padding: '3px 6px',
  background: '#FFFFFF05',
  borderRadius: '4px',
  marginBottom: '4px',
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
};

const branchTargetStyles: React.CSSProperties = {
  color: '#fa8c16',
  fontSize: '10px',
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

// Render icon from icon name string
const renderActionIcon = (iconName: string, color: string): React.ReactNode => {
  // Check if it's an emoji - render directly
  if (isEmoji(iconName)) {
    return <span style={{ color }}>{iconName}</span>;
  }

  // Check if we have a mapping for this icon name
  const iconifyName = ICON_MAP[iconName.toLowerCase()];
  if (iconifyName) {
    return <Icon icon={iconifyName} style={{ color, width: 20, height: 20 }} />;
  }

  // Fallback: try to use it as a Phosphor icon directly
  if (!iconName.includes(':')) {
    return <Icon icon={`ph:${iconName}-bold`} style={{ color, width: 20, height: 20 }} />;
  }

  // If it contains a colon, assume it's already a valid iconify identifier
  return <Icon icon={iconName} style={{ color, width: 20, height: 20 }} />;
};

function StepNodeComponent({ data, selected }: StepNodeProps) {
  const nodeData = data as StepNodeData;
  const action = nodeData?.action || 'unknown';
  const actionMeta = getActionMeta(action);
  const name = nodeData?.name || actionMeta.label;
  const condition = nodeData?.condition;
  const params = nodeData?.params || {};

  // Get branches for conditional nodes
  const branches = action === 'conditional' && params.branches && Array.isArray(params.branches)
    ? (params.branches as Array<{ id: string; label: string; target_step: string | null }>)
    : null;

  // Icon container with action color
  const iconContainerStyles: React.CSSProperties = {
    fontSize: '18px',
    width: '36px',
    height: '36px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: `${actionMeta.color}15`,
    border: 'none',
    color: actionMeta.color,
    borderRadius: '8px',
    flexShrink: 0,
  };

  // Subtitle with action color
  const subtitleStyles: React.CSSProperties = {
    color: '#808080',
    fontSize: '12px',
    marginTop: '2px',
  };

  return (
    <div
      className="step-node"
      style={{
        ...nodeStyles,
        ...(selected ? selectedNodeStyles : {}),
        borderLeft: `3px solid ${actionMeta.color}`,
      }}
    >
      {/* Input Handle (Left side for horizontal flow) */}
      <Handle type="target" position={Position.Left} id="input" style={handleStyles} />

      {/* Card Header */}
      <div style={{
        ...headerStyles,
        // Add bottom margin only when there's content below (condition or branches)
        marginBottom: (condition || branches) ? '12px' : undefined,
      }}>
        <span style={iconContainerStyles}>
          {renderActionIcon(actionMeta.icon, actionMeta.color)}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={titleStyles} title={name}>{name}</h3>
          <div style={subtitleStyles}>{actionMeta.label}</div>
        </div>
      </div>

      {/* Condition badge (if any) */}
      {condition && (
        <div style={conditionBadgeStyles} title={condition}>
          ⚡ Conditional
        </div>
      )}

      {/* Branches display for conditional nodes */}
      {branches && branches.length > 0 && (
        <div style={branchContainerStyles}>
          <div style={branchLabelStyles}>Branches ({branches.length})</div>
          {branches.slice(0, 3).map((branch) => (
            <div key={branch.id} style={branchItemStyles}>
              <span>{branch.label}</span>
              {branch.target_step && (
                <span style={branchTargetStyles}>→ {branch.target_step}</span>
              )}
            </div>
          ))}
          {branches.length > 3 && (
            <div style={{ fontSize: '9px', color: '#666' }}>
              +{branches.length - 3} more
            </div>
          )}
        </div>
      )}

      {/* Output Handle (Right side for horizontal flow) */}
      <Handle type="source" position={Position.Right} id="output" style={handleStyles} />
    </div>
  );
}

// Custom comparison to ensure re-renders when params change
function arePropsEqual(prevProps: StepNodeProps, nextProps: StepNodeProps) {
  const prevData = prevProps.data as StepNodeData;
  const nextData = nextProps.data as StepNodeData;

  // Always re-render if params changed (deep compare for branches)
  if (JSON.stringify(prevData?.params) !== JSON.stringify(nextData?.params)) {
    return false;
  }

  // Check other important props
  return (
    prevProps.selected === nextProps.selected &&
    prevData?.stepId === nextData?.stepId &&
    prevData?.name === nextData?.name &&
    prevData?.action === nextData?.action &&
    prevData?.condition === nextData?.condition
  );
}

export const StepNode = memo(StepNodeComponent, arePropsEqual);
export default StepNode;
