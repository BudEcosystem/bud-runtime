'use client';

/**
 * Node Palette Component
 *
 * A draggable palette of node types that can be dropped onto the canvas.
 * Supports categories, search, and drag-and-drop.
 */

import React, { memo, useState, useMemo, type DragEvent, type ComponentType } from 'react';
import type { NodePaletteConfig, NodePaletteCategory, NodePaletteItem } from '../core/types';
import { DEFAULT_DRAG_MIME_TYPE } from '../hooks/useDragAndDrop';

// ============================================================================
// Icons
// ============================================================================

const SearchIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </svg>
);

const ChevronDownIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="m6 9 6 6 6-6" />
  </svg>
);

const ChevronRightIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="m9 18 6-6-6-6" />
  </svg>
);

// ============================================================================
// Types
// ============================================================================

export interface NodePaletteProps {
  /** Palette configuration */
  config: NodePaletteConfig;
  /** MIME type for drag data */
  mimeType?: string;
  /** Callback when an item is clicked */
  onItemClick?: (item: NodePaletteItem) => void;
  /** Additional class name */
  className?: string;
  /** Custom item renderer */
  renderItem?: (item: NodePaletteItem, dragHandleProps: DragHandleProps) => React.ReactNode;
  /** Theme variant */
  theme?: 'light' | 'dark';
}

export interface DragHandleProps {
  draggable: boolean;
  onDragStart: (e: DragEvent) => void;
}

// ============================================================================
// Theme Styles
// ============================================================================

const themes = {
  light: {
    palette: {
      display: 'flex' as const,
      flexDirection: 'column' as const,
      backgroundColor: '#ffffff',
      borderRadius: '8px',
      border: '1px solid #e2e8f0',
      boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)',
      overflow: 'hidden' as const,
      maxHeight: '100%',
      height: '100%',
    },
    search: {
      display: 'flex' as const,
      alignItems: 'center' as const,
      gap: '8px',
      padding: '10px 12px',
      borderBottom: '1px solid #e2e8f0',
      color: '#64748b',
    },
    searchInput: {
      flex: 1,
      border: 'none',
      outline: 'none',
      fontSize: '13px',
      color: '#1e293b',
      backgroundColor: 'transparent',
    },
    categories: {
      flex: 1,
      overflowY: 'auto' as const,
    },
    categoryHeader: {
      display: 'flex' as const,
      alignItems: 'center' as const,
      gap: '8px',
      padding: '10px 12px',
      cursor: 'pointer',
      userSelect: 'none' as const,
      backgroundColor: '#f8fafc',
      borderBottom: '1px solid #e2e8f0',
      color: '#64748b',
    },
    categoryLabel: {
      flex: 1,
      fontWeight: 600,
      fontSize: '12px',
      color: '#475569',
      textTransform: 'uppercase' as const,
      letterSpacing: '0.05em',
    },
    categoryCount: {
      fontSize: '11px',
      color: '#94a3b8',
    },
    categoryItems: {
      padding: '8px',
    },
    item: {
      display: 'flex' as const,
      alignItems: 'center' as const,
      gap: '10px',
      padding: '8px 10px',
      borderRadius: '6px',
      cursor: 'grab',
      transition: 'background-color 0.2s',
    },
    itemHover: {
      backgroundColor: '#f1f5f9',
    },
    itemIcon: {
      width: '28px',
      height: '28px',
      borderRadius: '6px',
      display: 'flex' as const,
      alignItems: 'center' as const,
      justifyContent: 'center' as const,
      fontSize: '14px',
      flexShrink: 0,
    },
    itemContent: {
      flex: 1,
      minWidth: 0,
    },
    itemLabel: {
      fontWeight: 500,
      fontSize: '13px',
      color: '#1e293b',
      whiteSpace: 'nowrap' as const,
      overflow: 'hidden' as const,
      textOverflow: 'ellipsis' as const,
    },
    itemDescription: {
      fontSize: '11px',
      color: '#64748b',
      marginTop: '2px',
      whiteSpace: 'nowrap' as const,
      overflow: 'hidden' as const,
      textOverflow: 'ellipsis' as const,
    },
    iconBgDefault: '#f1f5f9',
    iconColorDefault: '#64748b',
  },
  dark: {
    palette: {
      display: 'flex' as const,
      flexDirection: 'column' as const,
      backgroundColor: '#141414',
      borderRadius: '0',
      border: 'none',
      boxShadow: 'none',
      overflow: 'hidden' as const,
      maxHeight: '100%',
      height: '100%',
    },
    search: {
      display: 'flex' as const,
      alignItems: 'center' as const,
      gap: '8px',
      padding: '12px 16px',
      borderBottom: '1px solid #333',
      color: '#808080',
    },
    searchInput: {
      flex: 1,
      border: 'none',
      outline: 'none',
      fontSize: '13px',
      color: '#fff',
      backgroundColor: 'transparent',
    },
    categories: {
      flex: 1,
      overflowY: 'auto' as const,
    },
    categoryHeader: {
      display: 'flex' as const,
      alignItems: 'center' as const,
      gap: '8px',
      padding: '10px 16px',
      cursor: 'pointer',
      userSelect: 'none' as const,
      backgroundColor: '#1a1a1a',
      borderBottom: '1px solid #333',
      color: '#808080',
    },
    categoryLabel: {
      flex: 1,
      fontWeight: 600,
      fontSize: '12px',
      color: '#808080',
      textTransform: 'uppercase' as const,
      letterSpacing: '0.05em',
    },
    categoryCount: {
      fontSize: '11px',
      color: '#666',
    },
    categoryItems: {
      padding: '8px 12px',
    },
    item: {
      display: 'flex' as const,
      alignItems: 'center' as const,
      gap: '10px',
      padding: '8px 10px',
      borderRadius: '6px',
      cursor: 'grab',
      transition: 'background-color 0.2s',
    },
    itemHover: {
      backgroundColor: '#1f1f1f',
    },
    itemIcon: {
      width: '28px',
      height: '28px',
      borderRadius: '6px',
      display: 'flex' as const,
      alignItems: 'center' as const,
      justifyContent: 'center' as const,
      fontSize: '14px',
      flexShrink: 0,
    },
    itemContent: {
      flex: 1,
      minWidth: 0,
    },
    itemLabel: {
      fontWeight: 500,
      fontSize: '13px',
      color: '#e0e0e0',
      whiteSpace: 'nowrap' as const,
      overflow: 'hidden' as const,
      textOverflow: 'ellipsis' as const,
    },
    itemDescription: {
      fontSize: '11px',
      color: '#808080',
      marginTop: '2px',
      whiteSpace: 'nowrap' as const,
      overflow: 'hidden' as const,
      textOverflow: 'ellipsis' as const,
    },
    iconBgDefault: '#1f1f1f',
    iconColorDefault: '#808080',
  },
};

// ============================================================================
// Component
// ============================================================================

function NodePaletteComponent({
  config,
  mimeType = DEFAULT_DRAG_MIME_TYPE,
  onItemClick,
  className = '',
  renderItem,
  theme = 'light',
}: NodePaletteProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(
    new Set(config.categories.filter((c) => c.collapsed).map((c) => c.id))
  );

  // Get theme styles
  const themeStyles = themes[theme];

  // Filter items based on search
  const filteredItems = useMemo(() => {
    if (!searchTerm) return config.items;
    const term = searchTerm.toLowerCase();
    return config.items.filter(
      (item) =>
        item.label.toLowerCase().includes(term) ||
        item.description?.toLowerCase().includes(term) ||
        item.type.toLowerCase().includes(term)
    );
  }, [config.items, searchTerm]);

  // Group items by category
  const itemsByCategory = useMemo(() => {
    const grouped = new Map<string, NodePaletteItem[]>();
    config.categories.forEach((cat) => grouped.set(cat.id, []));

    filteredItems.forEach((item) => {
      const items = grouped.get(item.categoryId) || [];
      items.push(item);
      grouped.set(item.categoryId, items);
    });

    return grouped;
  }, [config.categories, filteredItems]);

  // Toggle category collapse
  const toggleCategory = (categoryId: string) => {
    if (!config.collapsible) return;

    setCollapsedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(categoryId)) {
        next.delete(categoryId);
      } else {
        next.add(categoryId);
      }
      return next;
    });
  };

  // Handle drag start
  const handleDragStart = (e: DragEvent, item: NodePaletteItem) => {
    const dragData = { type: item.type, data: {} };
    e.dataTransfer.setData(mimeType, JSON.stringify(dragData));
    e.dataTransfer.effectAllowed = 'move';
  };

  // Render icon
  const renderIcon = (item: NodePaletteItem) => {
    const bgColor = item.color ? `${item.color}20` : themeStyles.iconBgDefault;
    const iconColor = item.color || themeStyles.iconColorDefault;

    if (typeof item.icon === 'string') {
      return (
        <div style={{ ...themeStyles.itemIcon, backgroundColor: bgColor }}>
          <span style={{ color: iconColor }}>{item.icon}</span>
        </div>
      );
    }

    if (item.icon) {
      const IconComponent = item.icon as ComponentType<{ className?: string; style?: React.CSSProperties }>;
      return (
        <div style={{ ...themeStyles.itemIcon, backgroundColor: bgColor }}>
          <IconComponent style={{ color: iconColor, width: 16, height: 16 }} />
        </div>
      );
    }

    return (
      <div style={{ ...themeStyles.itemIcon, backgroundColor: bgColor }}>
        <span style={{ color: iconColor }}>{item.label.charAt(0)}</span>
      </div>
    );
  };

  // Render palette item
  const renderPaletteItem = (item: NodePaletteItem) => {
    const dragHandleProps: DragHandleProps = {
      draggable: true,
      onDragStart: (e) => handleDragStart(e, item),
    };

    if (renderItem) {
      return renderItem(item, dragHandleProps);
    }

    return (
      <PaletteItem
        key={item.type}
        item={item}
        dragHandleProps={dragHandleProps}
        onClick={() => onItemClick?.(item)}
        renderIcon={renderIcon}
        themeStyles={themeStyles}
      />
    );
  };

  return (
    <div className={`node-palette ${className}`} style={themeStyles.palette}>
      {/* Search */}
      {config.searchable !== false && (
        <div style={themeStyles.search}>
          <SearchIcon />
          <input
            type="text"
            placeholder="Search actions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={themeStyles.searchInput}
          />
        </div>
      )}

      {/* Categories */}
      <div style={themeStyles.categories}>
        {config.categories.map((category) => {
          const items = itemsByCategory.get(category.id) || [];
          const isCollapsed = collapsedCategories.has(category.id);

          // Skip empty categories when searching
          if (searchTerm && items.length === 0) return null;

          return (
            <div key={category.id} className="palette-category">
              {/* Category header */}
              <div
                style={themeStyles.categoryHeader}
                onClick={() => toggleCategory(category.id)}
              >
                {config.collapsible !== false && (
                  isCollapsed ? <ChevronRightIcon /> : <ChevronDownIcon />
                )}
                <span style={themeStyles.categoryLabel}>{category.label}</span>
                <span style={themeStyles.categoryCount}>
                  {items.length}
                </span>
              </div>

              {/* Category items */}
              {!isCollapsed && items.length > 0 && (
                <div style={themeStyles.categoryItems}>
                  {items.map(renderPaletteItem)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// Palette Item Component
// ============================================================================

interface PaletteItemProps {
  item: NodePaletteItem;
  dragHandleProps: DragHandleProps;
  onClick?: () => void;
  renderIcon: (item: NodePaletteItem) => React.ReactNode;
  themeStyles: typeof themes.light;
}

function PaletteItem({ item, dragHandleProps, onClick, renderIcon, themeStyles }: PaletteItemProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      style={{
        ...themeStyles.item,
        ...(isHovered ? themeStyles.itemHover : {}),
      }}
      {...dragHandleProps}
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {renderIcon(item)}
      <div style={themeStyles.itemContent}>
        <div style={themeStyles.itemLabel}>{item.label}</div>
        {item.description && (
          <div style={themeStyles.itemDescription}>{item.description}</div>
        )}
      </div>
    </div>
  );
}

export const NodePalette = memo(NodePaletteComponent);
export default NodePalette;
