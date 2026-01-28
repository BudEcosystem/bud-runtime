import React from "react";
import { Tag, Tooltip, Spin } from "antd";

// Types for Drawer Log Tree
export interface DrawerLogEntry {
  id: string;
  time: string;
  namespace: string;
  title: string;
  serviceName: string;
  duration: number;
  childCount?: number;
  children?: DrawerLogEntry[];
  canExpand?: boolean;
  isLoadingChildren?: boolean;
  rawData?: Record<string, any>;
}

// Format duration for display
const formatDuration = (seconds: number): string => {
  if (seconds < 0.001) {
    return `${(seconds * 1000000).toFixed(0)}µs`;
  }
  if (seconds < 1) {
    return `${(seconds * 1000).toFixed(0)}ms`;
  }
  if (seconds >= 60) {
    return `${(seconds / 60).toFixed(1)}m`;
  }
  return `${seconds.toFixed(2)}s`;
};

// Single row component for drawer log tree (matches LogRow style from index.tsx)
const DrawerLogRow = ({
  node,
  depth = 0,
  isLastChild,
  isSelected,
  isExpanded,
  hasExpandedParent,
  ancestorHasMoreSiblings,
  onToggleExpand,
  onSelect,
}: {
  node: DrawerLogEntry;
  depth?: number;
  isLastChild?: boolean;
  isSelected: boolean;
  isExpanded?: boolean;
  hasExpandedParent?: boolean;
  ancestorHasMoreSiblings: boolean[];
  onToggleExpand: () => void;
  onSelect: () => void;
}) => {
  const hasChildren = node.children && node.children.length > 0;
  const canExpand = node.canExpand || hasChildren;
  const isChild = depth > 0;
  const indentPx = depth * 14; // 14px indent per level (scaled down from 18px)

  // Base position for tree lines (scaled down for drawer)
  // 8px padding + 40px time + 45px namespace = 93px
  const baseTreePosition = 93;
  const expandButtonCenter = 12; // center offset for tag

  return (
    <div
      className={`w-full flex-auto relative transition-colors border-b border-[rgba(255,255,255,0.08)] ${
        isSelected
          ? "bg-[#1a1a1a] border-l-2 border-l-[#965CDE]"
          : "hover:bg-[rgba(255,255,255,0.03)] border-l-2 border-l-transparent"
      }`}
    >
      {/* Continuation vertical lines for ancestor levels */}
      {ancestorHasMoreSiblings.map((hasMore, level) =>
        hasMore && level > 0 ? (
          <div
            key={`ancestor-line-${level}`}
            className="absolute w-[1px] bg-[#D4A853]"
            style={{
              left: `${baseTreePosition + expandButtonCenter + (level - 1) * 14}px`,
              top: 0,
              bottom: 0,
            }}
          />
        ) : null
      )}

      {/* Tree connector line for current child */}
      {isChild && (
        <>
          {/* Vertical line */}
          <div
            className="absolute w-[1px] bg-[#D4A853]"
            style={{
              left: `${baseTreePosition + expandButtonCenter + (depth - 1) * 14}px`,
              top: 0,
              height: isLastChild ? "calc(50% - 4px)" : "100%",
            }}
          />
          {/* Curved corner */}
          {isLastChild && (
            <div
              className="absolute"
              style={{
                left: `${baseTreePosition + expandButtonCenter + (depth - 1) * 14}px`,
                top: "calc(50% - 5px)",
                width: "8px",
                height: "6px",
                borderLeft: "1px solid #D4A853",
                borderBottom: "1px solid #D4A853",
                borderBottomLeftRadius: "5px",
              }}
            />
          )}
          {/* Horizontal connector */}
          <div
            className="absolute h-[1px] bg-[#D4A853]"
            style={{
              left: `${baseTreePosition + expandButtonCenter + (depth - 1) * 14 + (isLastChild ? 7 : 0)}px`,
              top: "50%",
              width: `${isLastChild ? 7 : 14}px`,
            }}
          />
          {/* Diamond marker for leaf nodes */}
          {!canExpand && (
            <div
              className="absolute w-[6px] h-[6px] bg-[#D4A853]"
              style={{
                left: `${baseTreePosition + expandButtonCenter + (depth - 1) * 14 + 11}px`,
                top: "50%",
                transform: "translateY(-50%) rotate(45deg)",
              }}
            />
          )}
        </>
      )}

      {/* Vertical line extending down from parent with expanded children */}
      {hasExpandedParent && (
        <div
          className="absolute w-[1px] bg-[#D4A853]"
          style={{
            left: `${baseTreePosition + expandButtonCenter + indentPx}px`,
            top: "50%",
            bottom: 0,
          }}
        />
      )}

      <div
        className="flex items-center justify-between py-[2px] cursor-pointer relative"
        onClick={onSelect}
      >
        <div
          className="flex items-center flex-auto"
          style={{ paddingLeft: "8px", paddingRight: "8px" }}
        >
          {/* Time */}
          <div style={{ width: "40px", flexShrink: 0 }}>
            <span className="text-[#B3B3B3] text-[0.5rem]">{node.time}</span>
          </div>

          {/* Namespace */}
          <div style={{ width: "45px", flexShrink: 0 }} className="flex justify-start items-center">
            <Tooltip title={node.namespace || node.serviceName || "-"} placement="top">
              <Tag className="bg-[#2a2a2a] border-[#D4A853] text-[#D4A853] text-[0.4375rem] max-w-[42px] truncate px-[.15rem] !leading-[180%]">
                {node.namespace || node.serviceName || "-"}
              </Tag>
            </Tooltip>
          </div>

          {/* Expand indicator */}
          <div
            className="flex items-center justify-center relative z-10"
            style={{ width: "32px", flexShrink: 0, marginLeft: `${indentPx}px` }}
          >
            {canExpand && (
              <div
                className="cursor-pointer flex items-center justify-center"
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  onToggleExpand();
                }}
              >
                {node.isLoadingChildren ? (
                  <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[#B3B3B3] text-[0.4375rem] w-fit pointer-events-none px-[.15rem] text-center !leading-[180%] min-w-[1.25rem]">
                    <Spin size="small" />
                  </Tag>
                ) : (
                  <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[#B3B3B3] text-[0.4375rem] w-fit pointer-events-none px-[.15rem] text-center !leading-[180%] min-w-[1.25rem]">
                    {isExpanded ? "−" : "+"}{node.childCount || node.children?.length || ""}
                  </Tag>
                )}
              </div>
            )}
          </div>

          {/* Title */}
          <div className="flex items-center overflow-hidden flex-1 min-w-0">
            <Tooltip title={node.title} placement="top">
              <span className="text-[#EEEEEE] text-[0.5rem] font-semibold whitespace-nowrap overflow-hidden text-ellipsis max-w-[100px] block">
                {node.title}
              </span>
            </Tooltip>
          </div>
        </div>

        <div className="flex justify-end items-center pr-[8px] pl-[8px] flex-shrink-0">
          {/* Metrics tag */}
          {node.serviceName && (
            <Tooltip title={node.serviceName} placement="top">
              <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[#B3B3B3] text-[0.4375rem] max-w-[60px] truncate w-fit pointer-events-none px-[.15rem] text-center !leading-[180%] mr-2">
                {node.serviceName}
              </Tag>
            </Tooltip>
          )}

          {/* Duration */}
          <span className="text-[#B3B3B3] text-[0.5rem] text-right w-[40px]">
            {formatDuration(node.duration)}
          </span>
        </div>
      </div>
    </div>
  );
};

// Recursive tree component for drawer
export const DrawerLogTree = ({
  nodes,
  depth = 0,
  selectedId,
  expandedIds,
  ancestorHasMoreSiblings = [],
  onToggleExpand,
  onSelect,
}: {
  nodes: DrawerLogEntry[];
  depth?: number;
  selectedId: string;
  expandedIds: Set<string>;
  ancestorHasMoreSiblings?: boolean[];
  onToggleExpand: (id: string) => void;
  onSelect: (node: DrawerLogEntry) => void;
}) => {
  const ancestors = ancestorHasMoreSiblings ?? [];
  if (!nodes || !Array.isArray(nodes)) {
    return null;
  }
  return (
    <>
      {nodes.map((node, index) => {
        const isExpanded = expandedIds.has(node.id);
        const hasChildren = node.children && node.children.length > 0;
        const isLastChild = index === nodes.length - 1;
        const isNotLastChild = !isLastChild;

        const childAncestorSiblings = [...ancestors, isNotLastChild];

        return (
          <React.Fragment key={node.id}>
            <DrawerLogRow
              node={node}
              depth={depth}
              isLastChild={isLastChild}
              isSelected={selectedId === node.id}
              isExpanded={isExpanded}
              hasExpandedParent={hasChildren && isExpanded}
              ancestorHasMoreSiblings={ancestors}
              onToggleExpand={() => onToggleExpand(node.id)}
              onSelect={() => onSelect(node)}
            />
            {hasChildren && isExpanded && (
              <DrawerLogTree
                nodes={node.children!}
                depth={depth + 1}
                selectedId={selectedId}
                expandedIds={expandedIds}
                ancestorHasMoreSiblings={childAncestorSiblings}
                onToggleExpand={onToggleExpand}
                onSelect={onSelect}
              />
            )}
          </React.Fragment>
        );
      })}
    </>
  );
};

export default DrawerLogTree;
