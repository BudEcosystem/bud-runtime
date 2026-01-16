'use client';

/**
 * Flow Editor Toolbar
 *
 * Provides common actions like layout toggle, undo/redo, fit view, etc.
 */

import React, { memo, type ReactNode } from 'react';
import {
  useFlowEditorContext,
  useLayoutDirection,
  useUndoRedoState,
} from '../core/FlowEditorContext';
import type { ToolbarAction, ToolbarConfig } from '../core/types';

// ============================================================================
// Icons (inline SVG for independence)
// ============================================================================

const UndoIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 7v6h6" />
    <path d="M21 17a9 9 0 00-9-9 9 9 0 00-6 2.3L3 13" />
  </svg>
);

const RedoIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 7v6h-6" />
    <path d="M3 17a9 9 0 019-9 9 9 0 016 2.3l3 2.7" />
  </svg>
);

const LayoutVerticalIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="6" y="3" width="12" height="6" rx="1" />
    <rect x="6" y="15" width="12" height="6" rx="1" />
    <path d="M12 9v6" />
    <path d="M9 12l3 3 3-3" />
  </svg>
);

const LayoutHorizontalIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="6" width="6" height="12" rx="1" />
    <rect x="15" y="6" width="6" height="12" rx="1" />
    <path d="M9 12h6" />
    <path d="M12 9l3 3-3 3" />
  </svg>
);

const FitViewIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
  </svg>
);

const AutoLayoutIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="3" width="7" height="7" rx="1" />
    <rect x="8.5" y="14" width="7" height="7" rx="1" />
    <path d="M6.5 10v1.5a2 2 0 002 2h7a2 2 0 002-2V10" />
    <path d="M12 13.5V14" />
  </svg>
);

// ============================================================================
// Types
// ============================================================================

export interface FlowToolbarProps {
  /** Toolbar configuration */
  config?: ToolbarConfig;
  /** Additional class name */
  className?: string;
  /** Position */
  position?: 'top-left' | 'top-right' | 'top-center';
  /** Custom children to render in the toolbar */
  children?: ReactNode;
}

// ============================================================================
// Styles
// ============================================================================

const toolbarStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
  padding: '6px',
  backgroundColor: '#ffffff',
  borderRadius: '8px',
  boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  border: '1px solid #e2e8f0',
};

const buttonStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '32px',
  height: '32px',
  borderRadius: '6px',
  border: 'none',
  backgroundColor: 'transparent',
  color: '#64748b',
  cursor: 'pointer',
  transition: 'background-color 0.2s, color 0.2s',
};

const buttonHoverStyles: React.CSSProperties = {
  backgroundColor: '#f1f5f9',
  color: '#1e293b',
};

const buttonActiveStyles: React.CSSProperties = {
  backgroundColor: '#dbeafe',
  color: '#3b82f6',
};

const buttonDisabledStyles: React.CSSProperties = {
  opacity: 0.4,
  cursor: 'not-allowed',
};

const dividerStyles: React.CSSProperties = {
  width: '1px',
  height: '20px',
  backgroundColor: '#e2e8f0',
  margin: '0 4px',
};

// ============================================================================
// Button Component
// ============================================================================

interface ToolbarButtonProps {
  icon: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
  tooltip?: string;
}

function ToolbarButton({ icon, onClick, disabled, active, tooltip }: ToolbarButtonProps) {
  const [isHovered, setIsHovered] = React.useState(false);

  const computedStyles: React.CSSProperties = {
    ...buttonStyles,
    ...(disabled ? buttonDisabledStyles : {}),
    ...(active ? buttonActiveStyles : isHovered ? buttonHoverStyles : {}),
  };

  return (
    <button
      style={computedStyles}
      onClick={onClick}
      disabled={disabled}
      title={tooltip}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {icon}
    </button>
  );
}

// ============================================================================
// Component
// ============================================================================

function FlowToolbarComponent({
  config,
  className = '',
  position = 'top-left',
  children,
}: FlowToolbarProps) {
  const {
    autoLayout,
    fitView,
  } = useFlowEditorContext();
  const [layoutDirection, setLayoutDirection] = useLayoutDirection();
  const { canUndo, canRedo, undo, redo } = useUndoRedoState();

  const showLayoutToggle = config?.showLayoutToggle ?? true;
  const showUndoRedo = config?.showUndoRedo ?? true;
  const showFitView = config?.showFitView ?? true;
  const customActions = config?.customActions ?? [];

  // Position styles
  const positionStyles: React.CSSProperties = {
    position: 'absolute',
    zIndex: 10,
    ...(position === 'top-left' ? { top: '10px', left: '10px' } : {}),
    ...(position === 'top-right' ? { top: '10px', right: '10px' } : {}),
    ...(position === 'top-center' ? { top: '10px', left: '50%', transform: 'translateX(-50%)' } : {}),
  };

  return (
    <div
      className={`flow-toolbar ${className}`}
      style={{ ...toolbarStyles, ...positionStyles }}
    >
      {/* Undo/Redo */}
      {showUndoRedo && (
        <>
          <ToolbarButton
            icon={<UndoIcon />}
            onClick={undo}
            disabled={!canUndo}
            tooltip="Undo (Ctrl+Z)"
          />
          <ToolbarButton
            icon={<RedoIcon />}
            onClick={redo}
            disabled={!canRedo}
            tooltip="Redo (Ctrl+Y)"
          />
          <div style={dividerStyles} />
        </>
      )}

      {/* Layout Toggle */}
      {showLayoutToggle && (
        <>
          <ToolbarButton
            icon={<LayoutVerticalIcon />}
            onClick={() => {
              setLayoutDirection('TB');
              autoLayout();
            }}
            active={layoutDirection === 'TB'}
            tooltip="Vertical Layout"
          />
          <ToolbarButton
            icon={<LayoutHorizontalIcon />}
            onClick={() => {
              setLayoutDirection('LR');
              autoLayout();
            }}
            active={layoutDirection === 'LR'}
            tooltip="Horizontal Layout"
          />
          <div style={dividerStyles} />
        </>
      )}

      {/* Auto Layout & Fit View */}
      <ToolbarButton
        icon={<AutoLayoutIcon />}
        onClick={autoLayout}
        tooltip="Auto Layout"
      />
      {showFitView && (
        <ToolbarButton
          icon={<FitViewIcon />}
          onClick={fitView}
          tooltip="Fit View"
        />
      )}

      {/* Custom Actions */}
      {customActions.length > 0 && (
        <>
          <div style={dividerStyles} />
          {customActions.map((action) => (
            <ToolbarButton
              key={action.id}
              icon={
                typeof action.icon === 'string' ? (
                  <span>{action.icon}</span>
                ) : action.icon ? (
                  React.createElement(action.icon)
                ) : (
                  <span>{action.label.charAt(0)}</span>
                )
              }
              onClick={action.onClick}
              disabled={action.disabled}
              tooltip={action.tooltip || action.label}
            />
          ))}
        </>
      )}

      {/* Custom children */}
      {children && (
        <>
          <div style={dividerStyles} />
          {children}
        </>
      )}
    </div>
  );
}

export const FlowToolbar = memo(FlowToolbarComponent);
export default FlowToolbar;
