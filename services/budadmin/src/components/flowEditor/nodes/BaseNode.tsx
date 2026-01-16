'use client';

/**
 * Base Node Component
 *
 * A foundational node component that provides common styling and functionality.
 * Other node types can extend this component.
 */

import React, { memo, type ReactNode } from 'react';
import { Handle, Position } from '@xyflow/react';
import { useFlowValidation } from '../core/FlowEditorContext';

// ============================================================================
// Types
// ============================================================================

export interface BaseNodeData extends Record<string, unknown> {
  label?: string;
  description?: string;
  width?: number;
  height?: number;
}

export interface BaseNodeProps {
  /** Node ID */
  id: string;
  /** Node data */
  data: BaseNodeData;
  /** Whether the node is selected */
  selected?: boolean;
  /** Custom content to render inside the node */
  children?: ReactNode;
  /** Number of input handles */
  inputHandles?: number;
  /** Number of output handles */
  outputHandles?: number;
  /** Whether to show handles */
  showHandles?: boolean;
  /** Custom class name */
  className?: string;
  /** Node border color */
  borderColor?: string;
  /** Node background color */
  backgroundColor?: string;
  /** Whether the node is deletable */
  deletable?: boolean;
}

// ============================================================================
// Styles
// ============================================================================

const baseStyles: React.CSSProperties = {
  padding: '10px 15px',
  borderRadius: '8px',
  border: '2px solid #e2e8f0',
  backgroundColor: '#ffffff',
  minWidth: '150px',
  boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  transition: 'border-color 0.2s, box-shadow 0.2s',
};

const selectedStyles: React.CSSProperties = {
  borderColor: '#3b82f6',
  boxShadow: '0 0 0 2px rgba(59, 130, 246, 0.3)',
};

const errorStyles: React.CSSProperties = {
  borderColor: '#ef4444',
  boxShadow: '0 0 0 2px rgba(239, 68, 68, 0.3)',
};

const handleStyles: React.CSSProperties = {
  width: '10px',
  height: '10px',
  backgroundColor: '#64748b',
  border: '2px solid #ffffff',
};

// ============================================================================
// Component
// ============================================================================

function BaseNodeComponent({
  id,
  data,
  selected,
  children,
  inputHandles = 1,
  outputHandles = 1,
  showHandles = true,
  className = '',
  borderColor,
  backgroundColor,
  deletable = true,
}: BaseNodeProps) {
  const validationResult = useFlowValidation();

  // Check if this node has validation errors
  const hasErrors = validationResult.errors.some(
    (error) => error.type === 'node' && error.id === id && error.severity === 'error'
  );

  const hasWarnings = validationResult.errors.some(
    (error) => error.type === 'node' && error.id === id && error.severity === 'warning'
  );

  // Compute styles
  const computedStyles: React.CSSProperties = {
    ...baseStyles,
    ...(selected ? selectedStyles : {}),
    ...(hasErrors ? errorStyles : {}),
    ...(borderColor ? { borderColor } : {}),
    ...(backgroundColor ? { backgroundColor } : {}),
  };

  // Get error message for tooltip
  const errorMessage = validationResult.errors
    .filter((error) => error.type === 'node' && error.id === id)
    .map((error) => error.message)
    .join('\n');

  return (
    <div
      className={`base-node ${className} ${selected ? 'selected' : ''} ${hasErrors ? 'has-errors' : ''}`}
      style={computedStyles}
      title={errorMessage || undefined}
    >
      {/* Input handles */}
      {showHandles &&
        Array.from({ length: inputHandles }).map((_, index) => (
          <Handle
            key={`input-${index}`}
            type="target"
            position={Position.Top}
            id={inputHandles > 1 ? `input-${index}` : undefined}
            style={{
              ...handleStyles,
              left: inputHandles > 1
                ? `${((index + 1) / (inputHandles + 1)) * 100}%`
                : '50%',
            }}
          />
        ))}

      {/* Node content */}
      {children || (
        <div className="base-node-content">
          {data.label && (
            <div
              className="base-node-label"
              style={{
                fontWeight: 500,
                fontSize: '14px',
                color: '#1e293b',
              }}
            >
              {data.label}
            </div>
          )}
          {data.description && (
            <div
              className="base-node-description"
              style={{
                fontSize: '12px',
                color: '#64748b',
                marginTop: '4px',
              }}
            >
              {data.description}
            </div>
          )}
        </div>
      )}

      {/* Output handles */}
      {showHandles &&
        Array.from({ length: outputHandles }).map((_, index) => (
          <Handle
            key={`output-${index}`}
            type="source"
            position={Position.Bottom}
            id={outputHandles > 1 ? `output-${index}` : undefined}
            style={{
              ...handleStyles,
              left: outputHandles > 1
                ? `${((index + 1) / (outputHandles + 1)) * 100}%`
                : '50%',
            }}
          />
        ))}

      {/* Error indicator */}
      {hasErrors && (
        <div
          className="error-indicator"
          style={{
            position: 'absolute',
            top: '-8px',
            right: '-8px',
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            backgroundColor: '#ef4444',
            color: '#ffffff',
            fontSize: '12px',
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          !
        </div>
      )}

      {/* Warning indicator */}
      {!hasErrors && hasWarnings && (
        <div
          className="warning-indicator"
          style={{
            position: 'absolute',
            top: '-8px',
            right: '-8px',
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            backgroundColor: '#f59e0b',
            color: '#ffffff',
            fontSize: '12px',
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          !
        </div>
      )}
    </div>
  );
}

export const BaseNode = memo(BaseNodeComponent);
export default BaseNode;
