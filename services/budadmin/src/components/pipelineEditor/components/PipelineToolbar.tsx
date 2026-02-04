'use client';

/**
 * Workflow Toolbar Component
 *
 * A standalone toolbar for the workflow editor that provides
 * undo/redo, layout toggle, fit view, and custom actions.
 * Does not depend on FlowEditorContext.
 */

import React, { memo, type ReactNode } from 'react';
import { useReactFlow } from '@xyflow/react';

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

const MagnifyingGlassIcon = ({ children }: { children?: React.ReactNode }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="11" cy="11" r="8" />
    <path d="M21 21l-4.35-4.35" />
    {children}
  </svg>
);

const ZoomInIcon = () => (
  <MagnifyingGlassIcon>
    <path d="M11 8v6" />
    <path d="M8 11h6" />
  </MagnifyingGlassIcon>
);

const ZoomOutIcon = () => (
  <MagnifyingGlassIcon>
    <path d="M8 11h6" />
  </MagnifyingGlassIcon>
);

// ============================================================================
// Types
// ============================================================================

export interface ToolbarAction {
  id: string;
  label: string;
  icon?: string | React.ComponentType;
  onClick: () => void;
  disabled?: boolean;
  tooltip?: string;
}

export interface PipelineToolbarProps {
  /** Show fit view button */
  showFitView?: boolean;
  /** Show zoom controls (zoom in/out buttons) */
  showZoomControls?: boolean;
  /** Show auto layout button */
  showAutoLayout?: boolean;
  /** Callback for auto layout */
  onAutoLayout?: () => void;
  /** Custom actions */
  customActions?: ToolbarAction[];
  /** Additional class name */
  className?: string;
  /** Position */
  position?: 'top-left' | 'top-right' | 'top-center' | 'bottom-left';
}

// ============================================================================
// Styles
// ============================================================================

const toolbarStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '3px',
  padding: '4px',
  backgroundColor: '#0E0E0E',
  borderRadius: '8px',
  boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.3)',
  border: '1px solid #333333',
};

const buttonStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '28px',
  height: '28px',
  borderRadius: '5px',
  border: 'none',
  backgroundColor: 'transparent',
  color: '#808080',
  cursor: 'pointer',
  transition: 'background-color 0.2s, color 0.2s',
};

const buttonHoverStyles: React.CSSProperties = {
  backgroundColor: '#1a1a1a',
  color: '#fff',
};

const buttonDisabledStyles: React.CSSProperties = {
  opacity: 0.4,
  cursor: 'not-allowed',
};

const dividerStyles: React.CSSProperties = {
  width: '1px',
  height: '20px',
  backgroundColor: '#333333',
  margin: '0 4px',
};

// ============================================================================
// Button Component
// ============================================================================

interface ToolbarButtonProps {
  icon: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  tooltip?: string;
}

function ToolbarButton({ icon, onClick, disabled, tooltip }: ToolbarButtonProps) {
  const [isHovered, setIsHovered] = React.useState(false);

  const computedStyles: React.CSSProperties = {
    ...buttonStyles,
    ...(disabled ? buttonDisabledStyles : {}),
    ...(isHovered && !disabled ? buttonHoverStyles : {}),
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

function PipelineToolbarComponent({
  showFitView = true,
  showZoomControls = true,
  showAutoLayout = true,
  onAutoLayout,
  customActions = [],
  className = '',
  position = 'top-left',
}: PipelineToolbarProps) {
  const reactFlow = useReactFlow();

  const handleFitView = () => {
    reactFlow.fitView({ padding: 0.2 });
  };

  const handleZoomIn = () => {
    reactFlow.zoomIn({ duration: 200 });
  };

  const handleZoomOut = () => {
    reactFlow.zoomOut({ duration: 200 });
  };

  // Position styles
  const positionStyles: React.CSSProperties = {
    position: 'absolute',
    zIndex: 10,
    ...(position === 'top-left' ? { top: '10px', left: '10px' } : {}),
    ...(position === 'top-right' ? { top: '10px', right: '10px' } : {}),
    ...(position === 'top-center' ? { top: '10px', left: '50%', transform: 'translateX(-50%)' } : {}),
    ...(position === 'bottom-left' ? { bottom: '26px', left: '16px' } : {}),
  };

  return (
    <div
      className={`workflow-toolbar ${className}`}
      style={{ ...toolbarStyles, ...positionStyles }}
    >
      {/* Auto Layout */}
      {showAutoLayout && onAutoLayout && (
        <ToolbarButton
          icon={<AutoLayoutIcon />}
          onClick={onAutoLayout}
          tooltip="Auto Layout"
        />
      )}

      {/* Zoom Controls */}
      {showZoomControls && (
        <>
          <ToolbarButton
            icon={<ZoomInIcon />}
            onClick={handleZoomIn}
            tooltip="Zoom In"
          />
          <ToolbarButton
            icon={<ZoomOutIcon />}
            onClick={handleZoomOut}
            tooltip="Zoom Out"
          />
        </>
      )}

      {/* Fit View */}
      {showFitView && (
        <ToolbarButton
          icon={<FitViewIcon />}
          onClick={handleFitView}
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
    </div>
  );
}

export const PipelineToolbar = memo(PipelineToolbarComponent);
export default PipelineToolbar;
