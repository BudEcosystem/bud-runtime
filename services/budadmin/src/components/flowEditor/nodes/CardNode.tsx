'use client';

/**
 * Card Node Component
 *
 * A card-style node with header, body, and footer sections.
 * Provides slots for icon, title, badges, and content.
 */

import React, { memo, type ReactNode, type ComponentType } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { useFlowValidation } from '../core/FlowEditorContext';

// ============================================================================
// Types
// ============================================================================

export interface CardNodeData {
  /** Node title */
  title?: string;
  /** Node subtitle or type */
  subtitle?: string;
  /** Description or additional info */
  description?: string;
  /** Icon component or emoji */
  icon?: ComponentType<{ className?: string }> | string;
  /** Icon color */
  iconColor?: string;
  /** Icon background color */
  iconBgColor?: string;
  /** Header badge text */
  badge?: string;
  /** Badge color */
  badgeColor?: string;
  /** Badge background color */
  badgeBgColor?: string;
  /** Status indicator */
  status?: 'default' | 'success' | 'warning' | 'error' | 'info';
  /** Custom width */
  width?: number;
  /** Any additional data */
  [key: string]: unknown;
}

export interface CardNodeProps extends NodeProps<Node<CardNodeData>> {
  /** Header slot content */
  headerSlot?: ReactNode;
  /** Body slot content */
  bodySlot?: ReactNode;
  /** Footer slot content */
  footerSlot?: ReactNode;
  /** Number of input handles */
  inputHandles?: number;
  /** Number of output handles */
  outputHandles?: number;
  /** Custom class name */
  className?: string;
  /** Border color (overrides status) */
  borderColor?: string;
  /** Header background color */
  headerBgColor?: string;
}

// ============================================================================
// Styles
// ============================================================================

const cardStyles: React.CSSProperties = {
  borderRadius: '8px',
  border: '2px solid #e2e8f0',
  backgroundColor: '#ffffff',
  minWidth: '200px',
  maxWidth: '280px',
  boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  transition: 'border-color 0.2s, box-shadow 0.2s',
  overflow: 'hidden',
};

const selectedStyles: React.CSSProperties = {
  borderColor: '#3b82f6',
  boxShadow: '0 0 0 2px rgba(59, 130, 246, 0.3)',
};

const statusColors: Record<string, string> = {
  default: '#e2e8f0',
  success: '#22c55e',
  warning: '#f59e0b',
  error: '#ef4444',
  info: '#3b82f6',
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

function CardNodeComponent({
  id,
  data,
  selected,
  headerSlot,
  bodySlot,
  footerSlot,
  inputHandles = 1,
  outputHandles = 1,
  className = '',
  borderColor,
  headerBgColor,
}: CardNodeProps) {
  const validationResult = useFlowValidation();

  // Check for validation errors
  const hasErrors = validationResult.errors.some(
    (error) => error.type === 'node' && error.id === id && error.severity === 'error'
  );

  // Compute border color
  const computedBorderColor = hasErrors
    ? '#ef4444'
    : borderColor ||
      (data.status ? statusColors[data.status] : statusColors.default);

  // Compute styles
  const computedCardStyles: React.CSSProperties = {
    ...cardStyles,
    borderColor: computedBorderColor,
    ...(selected ? selectedStyles : {}),
    ...(data.width ? { width: data.width, minWidth: data.width, maxWidth: data.width } : {}),
  };

  // Render icon
  const renderIcon = () => {
    if (!data.icon) return null;

    const iconWrapperStyle: React.CSSProperties = {
      width: '32px',
      height: '32px',
      borderRadius: '6px',
      backgroundColor: data.iconBgColor || '#f1f5f9',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
    };

    if (typeof data.icon === 'string') {
      return (
        <div style={iconWrapperStyle}>
          <span style={{ fontSize: '18px' }}>{data.icon}</span>
        </div>
      );
    }

    const IconComponent = data.icon;
    return (
      <div style={iconWrapperStyle}>
        <IconComponent className="w-4 h-4" />
      </div>
    );
  };

  // Render badge
  const renderBadge = () => {
    if (!data.badge) return null;

    return (
      <span
        style={{
          fontSize: '10px',
          fontWeight: 500,
          padding: '2px 6px',
          borderRadius: '4px',
          backgroundColor: data.badgeBgColor || '#f1f5f9',
          color: data.badgeColor || '#64748b',
        }}
      >
        {data.badge}
      </span>
    );
  };

  // Get error tooltip
  const errorMessage = validationResult.errors
    .filter((error) => error.type === 'node' && error.id === id)
    .map((error) => error.message)
    .join('\n');

  return (
    <div
      className={`card-node ${className} ${selected ? 'selected' : ''} ${hasErrors ? 'has-errors' : ''}`}
      style={computedCardStyles}
      title={errorMessage || undefined}
    >
      {/* Input handles */}
      {Array.from({ length: inputHandles }).map((_, index) => (
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

      {/* Header */}
      {(headerSlot || data.title || data.icon) && (
        <div
          className="card-node-header"
          style={{
            padding: '10px 12px',
            borderBottom: '1px solid #f1f5f9',
            backgroundColor: headerBgColor || '#fafafa',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          {headerSlot || (
            <>
              {renderIcon()}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: '13px',
                    color: '#1e293b',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {data.title || 'Untitled'}
                </div>
                {data.subtitle && (
                  <div
                    style={{
                      fontSize: '11px',
                      color: '#64748b',
                      marginTop: '2px',
                    }}
                  >
                    {data.subtitle}
                  </div>
                )}
              </div>
              {renderBadge()}
            </>
          )}
        </div>
      )}

      {/* Body */}
      {(bodySlot || data.description) && (
        <div
          className="card-node-body"
          style={{
            padding: '10px 12px',
          }}
        >
          {bodySlot || (
            <div
              style={{
                fontSize: '12px',
                color: '#64748b',
                lineHeight: 1.4,
              }}
            >
              {data.description}
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      {footerSlot && (
        <div
          className="card-node-footer"
          style={{
            padding: '8px 12px',
            borderTop: '1px solid #f1f5f9',
            backgroundColor: '#fafafa',
          }}
        >
          {footerSlot}
        </div>
      )}

      {/* Output handles */}
      {Array.from({ length: outputHandles }).map((_, index) => (
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
    </div>
  );
}

export const CardNode = memo(CardNodeComponent);
export default CardNode;
