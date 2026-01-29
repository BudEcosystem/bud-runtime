import React, { useEffect, useRef, useState, useCallback } from "react";
import { Tag, Spin, Tooltip } from "antd";
import * as echarts from "echarts";
import {
  Text_10_400_B3B3B3,
  Text_10_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_600_EEEEEE,
  Text_26_600_FFFFFF,
} from "@/components/ui/text";
import CustomSelect from "src/flows/components/CustomSelect";
import { AppRequest } from "src/pages/api/requests";
import { useDrawer } from "src/hooks/useDrawer";
import { useObservabilitySocket } from "@/hooks/useObservabilitySocket";

// API Response Types
interface TraceSpan {
  timestamp: string;
  trace_id: string;
  span_id: string;
  parent_span_id: string;
  trace_state: string;
  span_name: string;
  span_kind: string;
  service_name: string;
  resource_attributes: Record<string, string>;
  scope_name: string;
  scope_version: string;
  span_attributes: Record<string, any>;
  duration_ms?: number;
  duration?: number; // Duration in nanoseconds (from OpenTelemetry)
  status_code?: string;
  child_span_count?: number;
}

interface TracesResponse {
  object: string;
  message: string;
  page: number;
  limit: number;
  total_record: number;
  items: TraceSpan[];
  total_pages: number;
}

// Trace Detail API Response
interface TraceDetailResponse {
  object: string;
  message: string;
  trace_id: string;
  spans: TraceSpan[];
}

// UI Log Entry Type
interface LogEntry {
  id: string;
  time: string;
  namespace: string;
  title: string;
  childCount?: number;
  metrics: {
    sum?: number;
    rate?: number;
    tag?: string;
  };
  duration: number;
  startOffsetSec: number;
  children?: LogEntry[];
  traceId?: string;
  spanId?: string;
  parentSpanId?: string;
  canExpand?: boolean; // true if this is a root span that can be expanded
  isLoadingChildren?: boolean;
  rawData?: Record<string, any>; // Raw span data for details drawer
}

interface LogsTabProps {
  promptName?: string;
  promptId?: string;
  projectId?: string;
}

// Duration bar component
const DurationBar = ({
  duration,
  referenceDuration,
}: {
  duration: number;
  referenceDuration: number;
}) => {
  // Calculate width as percentage of reference duration (root span = 100%)
  const widthPercent = referenceDuration > 0 ? (duration / referenceDuration) * 100 : 0;

  return (
    <div className="relative h-5" style={{ width: "120px", flexShrink: 0 }}>
      <div
        className="absolute h-[6px] top-[7px] rounded"
        style={{
          left: 0,
          width: `${Math.max(Math.min(widthPercent, 100), 1)}%`,
          background: "#a855f7",
        }}
      />
    </div>
  );
};

// Single log row component
const LogRow = ({
  row,
  referenceDuration,
  isSelected,
  depth,
  isLastChild,
  isExpanded,
  hasExpandedParent,
  ancestorHasMoreSiblings,
  onSelect,
  onToggleExpand,
  onViewDetails,
}: {
  row: LogEntry;
  referenceDuration: number;
  isSelected: boolean;
  depth: number;
  isLastChild?: boolean;
  isExpanded?: boolean;
  hasExpandedParent?: boolean;
  ancestorHasMoreSiblings: boolean[]; // tracks which ancestor levels have more siblings
  onSelect: () => void;
  onToggleExpand?: () => void;
  onViewDetails?: (log: LogEntry) => void;
}) => {
  const hasChildren = row.children && row.children.length > 0;
  const canExpand = row.canExpand || hasChildren;
  const isChild = depth > 0;
  const indentPx = depth * 18; // 18px indent per level

  // Base position for tree lines - center of expand button/tag
  // 12px padding + 50px time + 60px namespace = 122px (start of expand button column)
  // Tag has min-w-[1.5rem] (24px), centered in 40px container, so center is at ~12px from tag left
  // With tag centered: (40 - 24) / 2 + 12 = 8 + 12 = 20px, but visually adjust to 12px for tag center
  const baseTreePosition = 122;
  const expandButtonCenter = 15; // center offset to align with middle of min-w-[1.5rem] tag

  return (
    <div
      className={`w-full flex-auto relative transition-colors border-b border-[rgba(255,255,255,0.08)] ${isSelected
        ? "bg-[#1a1a1a] border-l-2 border-l-[#965CDE]"
        : "hover:bg-[rgba(255,255,255,0.03)] border-l-2 border-l-transparent"
        }`}
    >
      {/* Continuation vertical lines for ancestor levels (skip level 0 - root items are separate) */}
      {/* level in array = depth of ancestor with siblings, line position = parent of that ancestor */}
      {ancestorHasMoreSiblings.map((hasMore, level) =>
        hasMore && level > 0 ? (
          <div
            key={`ancestor-line-${level}`}
            className="absolute w-[1px] bg-[#D4A853]"
            style={{
              left: `${baseTreePosition + expandButtonCenter + (level - 1) * 18}px`,
              top: 0,
              bottom: 0,
            }}
          />
        ) : null
      )}

      {/* Tree connector line for current child - L-shaped with curved corner */}
      {isChild && (
        <>
          {/* Vertical line from top to curve point - starts from center of parent's expand button */}
          <div
            className="absolute w-[1px] bg-[#D4A853]"
            style={{
              left: `${baseTreePosition + expandButtonCenter + (depth - 1) * 18}px`,
              top: 0,
              height: isLastChild ? "calc(50% - 5px)" : "100%",
            }}
          />
          {/* Curved corner connector (L-shape with border-radius) */}
          {isLastChild && (
            <div
              className="absolute"
              style={{
                left: `${baseTreePosition + expandButtonCenter + (depth - 1) * 18}px`,
                top: "calc(50% - 6px)",
                width: "10px",
                height: "7px",
                borderLeft: "1px solid #D4A853",
                borderBottom: "1px solid #D4A853",
                borderBottomLeftRadius: "6px",
              }}
            />
          )}
          {/* Horizontal connector line (after the curve) - connects to current row's expand button */}
          <div
            className="absolute h-[1px] bg-[#D4A853]"
            style={{
              left: `${baseTreePosition + expandButtonCenter + (depth - 1) * 18 + (isLastChild ? 9 : 0)}px`,
              top: "50%",
              width: `${isLastChild ? 9 : 18}px`,
            }}
          />
          {/* Diamond marker - only show when there's nothing more to expand (leaf node) */}
          {!canExpand && (
            <div
              className="absolute w-[8px] h-[8px] bg-[#D4A853]"
              style={{
                left: `${baseTreePosition + expandButtonCenter + (depth - 1) * 18 + 14}px`,
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
        className="flex items-center justify-between py-1 cursor-pointer relative"
        onClick={() => {
          onSelect();
          onViewDetails?.(row);
        }}
      >
        <div
          className="flex items-center flex-auto"
          style={{
            paddingLeft: "12px",
            paddingRight: "12px",
          }}
        >
          {/* Time - fixed width, no indent */}
          <div style={{ width: "50px", flexShrink: 0 }}>
            <Text_10_400_B3B3B3>{row.time}</Text_10_400_B3B3B3>
          </div>

          {/* Namespace - fixed width, no indent */}
          <div style={{ width: "60px", flexShrink: 0 }} className="flex justify-start items-center">
            <Tooltip title={row.namespace || "-"} placement="top">
              <Tag className="bg-[#2a2a2a] border-[#D4A853] text-[#D4A853] text-[.5rem] max-w-[55px] truncate px-[.2rem] !leading-[200%]">
                {row.namespace || "-"}
              </Tag>
            </Tooltip>
          </div>

          {/* Count / Expand indicator - indented based on depth */}
          <div
            className="flex items-center justify-center relative z-10"
            style={{ width: "40px", flexShrink: 0, marginLeft: `${indentPx}px` }}
          >
            {canExpand && (
              <div
                className="cursor-pointer flex items-center justify-center"
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  onToggleExpand?.();
                }}
              >
                {row.isLoadingChildren ? (
                  <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[#B3B3B3] text-[.5rem] w-fit pointer-events-none px-[.2rem] w-full text-center !leading-[200%] min-w-[1.5rem]">
                    <Spin size="small" />
                  </Tag>
                ) : (
                  <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[#B3B3B3] text-[.5rem] w-fit pointer-events-none px-[.2rem] w-full text-center !leading-[200%]  min-w-[1.5rem]">
                    {isExpanded ? "−" : "+"}{row.childCount || row.children?.length || ""}
                  </Tag>
                )}
              </div>
            )}
          </div>

          {/* Title */}
          <div className="flex items-center overflow-hidden flex-1 min-w-0">
            <Tooltip title={row.title} placement="top">
              <Text_10_600_EEEEEE className="ibm whitespace-nowrap overflow-hidden text-ellipsis max-w-[130px] block">
                {row.title}
              </Text_10_600_EEEEEE>
            </Tooltip>
          </div>
        </div>
        <div className="flex justify-end items-center min-w-[30%] pr-[12px] pl-[12px] flex-shrink-0">
          {/* Metrics tags */}
          <div className="flex gap-2 items-center flex-shrink-0 mr-3">
            {row.metrics.sum !== undefined && (
              <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[.5rem] text-[#B3B3B3] w-fit pointer-events-none px-[.2rem] w-full text-center !leading-[200%]">
                ∅ ∑ ↗{row.metrics.sum} ↙{row.metrics.rate}
              </Tag>
            )}
            {row.metrics.tag && (
              <Tooltip title={row.metrics.tag} placement="top">
                <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[.5rem] text-[#B3B3B3] max-w-[80px] truncate w-fit pointer-events-none px-[.2rem] w-full text-center !leading-[200%]">
                  {row.metrics.tag}
                </Tag>
              </Tooltip>
            )}
          </div>

          {/* Timeline */}
          <DurationBar
            duration={row.duration}
            referenceDuration={referenceDuration}
          />

          {/* Duration */}
          <Text_10_400_B3B3B3 className="text-right ml-[1rem]">
            {formatDuration(row.duration)}
          </Text_10_400_B3B3B3>
        </div>

      </div>
    </div>
  );
};

// Flat row component for flatten view (no tree lines, no expand)
const FlatLogRow = ({
  row,
  referenceDuration,
  isSelected,
  onSelect,
  onViewDetails,
}: {
  row: LogEntry;
  referenceDuration: number;
  isSelected: boolean;
  onSelect: () => void;
  onViewDetails?: (log: LogEntry) => void;
}) => {
  return (
    <div
      className={`w-full flex-auto relative transition-colors border-b border-[rgba(255,255,255,0.08)] ${
        isSelected
          ? "bg-[#1a1a1a] border-l-2 border-l-[#965CDE]"
          : "hover:bg-[rgba(255,255,255,0.03)] border-l-2 border-l-transparent"
      }`}
    >
      <div
        className="flex items-center justify-between py-1 cursor-pointer"
        onClick={() => {
          onSelect();
          onViewDetails?.(row);
        }}
      >
        <div className="flex items-center flex-auto px-3">
          {/* Time */}
          <div style={{ width: "50px", flexShrink: 0 }}>
            <Text_10_400_B3B3B3>{row.time}</Text_10_400_B3B3B3>
          </div>

          {/* Status */}
          <div style={{ width: "60px", flexShrink: 0 }} className="flex justify-start items-center">
            <Tooltip title={row.namespace || "-"} placement="top">
              <Tag className="bg-[#2a2a2a] border-[#D4A853] text-[#D4A853] text-[.5rem] max-w-[55px] truncate px-[.2rem]">
                {row.namespace || "-"}
              </Tag>
            </Tooltip>
          </div>

          {/* Title */}
          <div className="flex items-center overflow-hidden flex-1 min-w-0">
            <Tooltip title={row.title} placement="top">
              <Text_10_600_EEEEEE className="ibm whitespace-nowrap overflow-hidden text-ellipsis max-w-[130px] block">
                {row.title}
              </Text_10_600_EEEEEE>
            </Tooltip>
          </div>
        </div>
        <div className="flex justify-end items-center min-w-[30%] pr-3 pl-3 flex-shrink-0 bg-[#101010]">
          {/* Metrics tag */}
          {row.metrics.tag && (
            <Tooltip title={row.metrics.tag} placement="top">
              <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[#B3B3B3] text-[11px] max-w-[80px] truncate mr-3">
                {row.metrics.tag}
              </Tag>
            </Tooltip>
          )}

          {/* Timeline */}
          <DurationBar duration={row.duration} referenceDuration={referenceDuration} />

          {/* Duration */}
          <Text_10_400_B3B3B3 className="text-right ml-4">
            {formatDuration(row.duration)}
          </Text_10_400_B3B3B3>
        </div>
      </div>
    </div>
  );
};

// Recursive component for rendering nested logs
const LogTree = ({
  logs,
  referenceDuration,
  selectedId,
  expandedIds,
  onSelect,
  onToggleExpand,
  onViewDetails,
  depth = 0,
  ancestorHasMoreSiblings = [],
}: {
  logs: LogEntry[];
  referenceDuration?: number; // Root span duration as 100% reference (only needed for children)
  selectedId: string | null;
  expandedIds: Set<string>;
  onSelect: (id: string) => void;
  onToggleExpand: (id: string) => void;
  onViewDetails?: (log: LogEntry) => void;
  depth?: number;
  ancestorHasMoreSiblings?: boolean[];
}) => {
  return (
    <>
      {logs.map((log, index) => {
        const isExpanded = expandedIds.has(log.id);
        const hasChildren = log.children && log.children.length > 0;
        const isLastChild = index === logs.length - 1;
        const isNotLastChild = !isLastChild;

        // For children of this item, update the ancestor tracking
        // Current level has more siblings if this is NOT the last child
        const childAncestorSiblings = [...ancestorHasMoreSiblings, isNotLastChild];

        // For root spans (depth 0), their own duration is the reference (100%)
        // For children, use the passed referenceDuration from the root
        const currentReferenceDuration = depth === 0 ? log.duration : (referenceDuration ?? log.duration);

        return (
          <React.Fragment key={log.id}>
            <LogRow
              row={log}
              referenceDuration={currentReferenceDuration}
              isSelected={selectedId === log.id}
              depth={depth}
              isLastChild={isLastChild}
              isExpanded={isExpanded}
              hasExpandedParent={hasChildren && isExpanded}
              ancestorHasMoreSiblings={ancestorHasMoreSiblings}
              onSelect={() => onSelect(log.id)}
              onToggleExpand={() => onToggleExpand(log.id)}
              onViewDetails={onViewDetails}
            />
            {/* Render children if expanded */}
            {hasChildren && isExpanded && (
              <LogTree
                logs={log.children!}
                referenceDuration={depth === 0 ? log.duration : referenceDuration}
                selectedId={selectedId}
                expandedIds={expandedIds}
                onSelect={onSelect}
                onToggleExpand={onToggleExpand}
                onViewDetails={onViewDetails}
                depth={depth + 1}
                ancestorHasMoreSiblings={childAncestorSiblings}
              />
            )}
          </React.Fragment>
        );
      })}
    </>
  );
};

// Helper function to format date as YYYY-MM-DDTHH:mm:ssZ
const formatDateForApi = (date: Date): string => {
  return date.toISOString().replace(/\.\d{3}Z$/, "Z");
};

// Helper function to get time range dates
const getTimeRangeDates = (range: string): { from_date: string; to_date: string } => {
  const now = new Date();
  let from_date: Date;

  switch (range) {
    case "5m":
      from_date = new Date(now.getTime() - 5 * 60 * 1000);
      break;
    case "15m":
      from_date = new Date(now.getTime() - 15 * 60 * 1000);
      break;
    case "30m":
      from_date = new Date(now.getTime() - 30 * 60 * 1000);
      break;
    case "1h":
      from_date = new Date(now.getTime() - 60 * 60 * 1000);
      break;
    case "24h":
      from_date = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      break;
    case "7d":
      from_date = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      break;
    case "30d":
      from_date = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      break;
    default:
      from_date = new Date(now.getTime() - 5 * 60 * 1000);
  }

  return {
    from_date: formatDateForApi(from_date),
    to_date: formatDateForApi(now),
  };
};

// Helper function to format timestamp to time string
const formatTime = (timestamp: string): string => {
  if (!timestamp) return 'N/A';
  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return 'Invalid';
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
};

// Helper function to format duration (seconds to minutes if > 99s)
const formatDuration = (seconds: number): string => {
  if (seconds > 99) {
    return `${(seconds / 60).toFixed(2)}m`;
  }
  return `${seconds.toFixed(2)}s`;
};

// Helper function to extract only root spans (those with empty parent_span_id)
const buildRootSpansList = (spans: TraceSpan[], earliestTimestamp: number): LogEntry[] => {
  const result: LogEntry[] = [];

  spans.forEach((span) => {
    // Only include spans with empty parent_span_id (root spans)
    if (!span.parent_span_id || span.parent_span_id === "") {
      const timestamp = new Date(span.timestamp).getTime();

      const entry: LogEntry = {
        id: span.span_id,
        time: formatTime(span.timestamp),
        namespace: span.resource_attributes?.["service.name"] || "",
        title: span.span_name,
        childCount: span.child_span_count,
        metrics: {
          tag: span.service_name,
        },
        duration: (span.duration ?? 0) / 1_000_000_000, // Convert nanoseconds to seconds
        startOffsetSec: (timestamp - earliestTimestamp) / 1000,
        traceId: span.trace_id,
        spanId: span.span_id,
        parentSpanId: span.parent_span_id,
        canExpand: (span.child_span_count ?? 0) > 0, // Only expandable if has children
        rawData: span as unknown as Record<string, any>, // Include raw span data for details drawer
      };

      result.push(entry);
    }
  });

  // Sort by timestamp
  result.sort((a, b) => a.startOffsetSec - b.startOffsetSec);

  return result;
};

// Helper function to build flat list of all spans (for flatten view)
const buildFlatSpansList = (spans: TraceSpan[], earliestTimestamp: number): LogEntry[] => {
  return spans.map((span) => {
    const timestamp = new Date(span.timestamp).getTime();
    return {
      id: span.span_id,
      time: formatTime(span.timestamp),
      namespace: span.resource_attributes?.["service.name"] || "",
      title: span.span_name,
      metrics: {
        tag: span.service_name,
      },
      duration: (span.duration ?? 0) / 1_000_000_000, // Convert nanoseconds to seconds
      startOffsetSec: (timestamp - earliestTimestamp) / 1000,
      traceId: span.trace_id,
      spanId: span.span_id,
      parentSpanId: span.parent_span_id,
      canExpand: false, // No expansion in flatten mode
      rawData: span as unknown as Record<string, any>, // Include raw span data for details drawer
    };
  }).sort((a, b) => a.startOffsetSec - b.startOffsetSec);
};

// Helper function to build hierarchical tree from trace detail spans
const buildChildrenFromTraceDetail = (
  spans: TraceSpan[],
  rootSpanId: string,
  earliestTimestamp: number
): LogEntry[] => {
  // Build a map of span_id to LogEntry
  const spanMap = new Map<string, LogEntry>();

  // First pass: create all LogEntry nodes (excluding the root span itself)
  spans.forEach((span) => {
    const timestamp = new Date(span.timestamp).getTime();

    const entry: LogEntry = {
      id: span.span_id,
      time: formatTime(span.timestamp),
      namespace: span.resource_attributes?.["service.name"] || "",
      title: span.span_name,
      childCount: span.child_span_count, // Use child_span_count from API
      metrics: {
        tag: span.service_name,
      },
      duration: (span.duration ?? 0) / 1_000_000_000, // Convert nanoseconds to seconds
      startOffsetSec: (timestamp - earliestTimestamp) / 1000,
      children: [],
      traceId: span.trace_id,
      spanId: span.span_id,
      parentSpanId: span.parent_span_id,
      canExpand: (span.child_span_count ?? 0) > 0, // Set canExpand based on child_span_count
      rawData: span as unknown as Record<string, any>, // Include raw span data for details drawer
    };

    spanMap.set(span.span_id, entry);
  });

  // Second pass: build parent-child relationships
  const directChildren: LogEntry[] = [];
  spans.forEach((span) => {
    const entry = spanMap.get(span.span_id);
    if (!entry) return;

    // Skip the root span itself
    if (span.span_id === rootSpanId) return;

    if (span.parent_span_id === rootSpanId) {
      // Direct child of root span
      directChildren.push(entry);
    } else if (span.parent_span_id && spanMap.has(span.parent_span_id)) {
      // Child of another span
      const parent = spanMap.get(span.parent_span_id)!;
      parent.children = parent.children || [];
      parent.children.push(entry);
    }
  });

  // Sort children by timestamp and clean up empty children arrays
  const processChildren = (entry: LogEntry) => {
    if (entry.children && entry.children.length > 0) {
      entry.children.sort((a, b) => a.startOffsetSec - b.startOffsetSec);
      entry.children.forEach(processChildren);
    } else {
      delete entry.children;
    }
  };

  directChildren.forEach(processChildren);

  // Sort by timestamp
  directChildren.sort((a, b) => a.startOffsetSec - b.startOffsetSec);

  return directChildren;
};

// Helper function to build tree structure from live socket spans
// This is used for live data where child_span_count is not available
const buildTreeFromLiveSpans = (spans: TraceSpan[]): LogEntry[] => {
  if (!spans || spans.length === 0) return [];

  // Step 1: Group spans by trace_id
  const spansByTraceId = new Map<string, TraceSpan[]>();
  spans.forEach(span => {
    const traceId = span.trace_id;
    if (!traceId) return;
    if (!spansByTraceId.has(traceId)) {
      spansByTraceId.set(traceId, []);
    }
    spansByTraceId.get(traceId)!.push(span);
  });

  const result: LogEntry[] = [];

  // Step 2: For each trace, build tree structure
  spansByTraceId.forEach((traceSpans) => {
    // Find root span (no parent_span_id or empty)
    const rootSpan = traceSpans.find(s => !s.parent_span_id || s.parent_span_id === '');
    if (!rootSpan) return; // Skip if no root found

    // Find earliest timestamp for offset calculation
    const timestamps = traceSpans.map(s => new Date(s.timestamp).getTime());
    const earliestTimestamp = Math.min(...timestamps);

    // Recursive function to build children
    const buildNode = (span: TraceSpan): LogEntry => {
      const children = traceSpans.filter(s => s.parent_span_id === span.span_id);
      const childNodes = children.map(c => buildNode(c));

      // Sort children by timestamp
      childNodes.sort((a, b) => a.startOffsetSec - b.startOffsetSec);

      const timestamp = new Date(span.timestamp).getTime();

      return {
        id: span.span_id,
        time: formatTime(span.timestamp),
        namespace: span.resource_attributes?.["service.name"] || "",
        title: span.span_name || 'Unknown Span',
        childCount: childNodes.length,
        metrics: { tag: span.service_name || '' },
        duration: (span.duration ?? 0) / 1_000_000_000,
        startOffsetSec: (timestamp - earliestTimestamp) / 1000,
        traceId: span.trace_id,
        spanId: span.span_id,
        parentSpanId: span.parent_span_id || '',
        canExpand: childNodes.length > 0,
        children: childNodes.length > 0 ? childNodes : undefined,
        rawData: span as unknown as Record<string, any>,
      };
    };

    result.push(buildNode(rootSpan));
  });

  // Sort result by timestamp (most recent first for live data)
  result.sort((a, b) => {
    const timeA = new Date(a.rawData?.timestamp || 0).getTime();
    const timeB = new Date(b.rawData?.timestamp || 0).getTime();
    return timeB - timeA; // Descending order (newest first)
  });

  return result;
};

const LogsTab: React.FC<LogsTabProps> = ({ promptName, promptId, projectId }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [timeRange, setTimeRange] = useState("5m");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [logsData, setLogsData] = useState<LogEntry[]>([]);
  const [chartData, setChartData] = useState<{ times: string[]; values: number[] }>({
    times: [],
    values: [],
  });
  const [isAllExpanded, setIsAllExpanded] = useState(false);
  const [isLive, setIsLive] = useState(false);

  // Live streaming state
  const liveSpanIdsRef = useRef<Set<string>>(new Set());
  const MAX_LIVE_ITEMS = 200;

  // View mode and pagination state
  const [viewMode, setViewMode] = useState<'traces' | 'flatten'>('traces');
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  // Drawer hook
  const { openDrawer } = useDrawer();

  // Handle incoming live trace data
  const handleLiveTrace = useCallback((trace: TraceSpan) => {
    console.log('[LiveTrace] Received trace:', trace);

    // Validate required fields
    if (!trace || !trace.span_id) {
      console.warn('[LiveTrace] Invalid trace data - missing span_id:', trace);
      return;
    }

    // In traces view, only show root spans (those with empty parent_span_id)
    if (viewMode === 'traces' && trace.parent_span_id && trace.parent_span_id !== '') {
      console.log('[LiveTrace] Skipping non-root span:', trace.span_id);
      return;
    }

    // Deduplicate by span_id
    if (liveSpanIdsRef.current.has(trace.span_id)) {
      console.log('[LiveTrace] Duplicate span, skipping:', trace.span_id);
      return;
    }
    liveSpanIdsRef.current.add(trace.span_id);

    // Transform to LogEntry and prepend to list
    // Handle both snake_case (from socket) and potential variations
    const newEntry: LogEntry = {
      id: trace.span_id,
      time: trace.timestamp ? formatTime(trace.timestamp) : 'N/A',
      namespace: trace.resource_attributes?.["service.name"] || "",
      title: trace.span_name || 'Unknown Span',
      childCount: trace.child_span_count ?? 0,
      metrics: { tag: trace.service_name || '' },
      duration: (trace.duration ?? 0) / 1_000_000_000, // nanoseconds to seconds
      startOffsetSec: 0,
      traceId: trace.trace_id,
      spanId: trace.span_id,
      parentSpanId: trace.parent_span_id || '',
      canExpand: (trace.child_span_count ?? 0) > 0,
      rawData: trace as unknown as Record<string, any>,
    };

    console.log('[LiveTrace] Created LogEntry:', newEntry);
    setLogsData(prev => [newEntry, ...prev].slice(0, MAX_LIVE_ITEMS));
  }, [viewMode]);

  // Handle batch of live traces (for tree building in traces view)
  const handleLiveTraceBatch = useCallback((traces: TraceSpan[]) => {
    console.log('[LiveTrace] Received batch:', traces.length, 'spans');

    if (!traces || traces.length === 0) return;

    if (viewMode === 'traces') {
      // In traces view, build proper tree structure from batch
      const newTrees = buildTreeFromLiveSpans(traces);
      console.log('[LiveTrace] Built', newTrees.length, 'trees from batch');

      if (newTrees.length === 0) return;

      // Track trace IDs for deduplication
      newTrees.forEach(tree => {
        if (tree.traceId) {
          liveSpanIdsRef.current.add(tree.traceId);
        }
      });

      // Merge with existing data (prepend new trees, replace existing with same trace_id)
      setLogsData(prev => {
        const newTraceIds = new Set(newTrees.map(t => t.traceId));
        // Filter out existing trees with same trace_id (update scenario)
        const filteredPrev = prev.filter(p => !newTraceIds.has(p.traceId));
        return [...newTrees, ...filteredPrev].slice(0, MAX_LIVE_ITEMS);
      });
    } else {
      // In flatten view, process each span individually (existing behavior)
      traces.forEach(trace => {
        if (!trace || !trace.span_id) return;
        if (liveSpanIdsRef.current.has(trace.span_id)) return;
        liveSpanIdsRef.current.add(trace.span_id);

        const newEntry: LogEntry = {
          id: trace.span_id,
          time: trace.timestamp ? formatTime(trace.timestamp) : 'N/A',
          namespace: trace.resource_attributes?.["service.name"] || "",
          title: trace.span_name || 'Unknown Span',
          childCount: 0,
          metrics: { tag: trace.service_name || '' },
          duration: (trace.duration ?? 0) / 1_000_000_000,
          startOffsetSec: 0,
          traceId: trace.trace_id,
          spanId: trace.span_id,
          parentSpanId: trace.parent_span_id || '',
          canExpand: false,
          rawData: trace as unknown as Record<string, any>,
        };

        setLogsData(prev => [newEntry, ...prev].slice(0, MAX_LIVE_ITEMS));
      });
    }
  }, [viewMode]);

  // Socket hook for live streaming
  // Note: promptId (UUID) is used for socket subscription, promptName is used for API calls
  console.log('[LogsTab] Socket params:', { projectId, promptId, promptName, isLive });
  const { isSubscribed, connectionStatus, error: socketError } = useObservabilitySocket({
    projectId: projectId || '',
    promptId: promptId || '',
    enabled: isLive && !!projectId && !!promptId,
    onTraceBatchReceived: handleLiveTraceBatch,
    onTraceReceived: handleLiveTrace,
    onError: (err) => console.error('[LiveTrace] Socket error:', err),
  });

  const ITEMS_PER_PAGE = 15;

  // Open drawer with selected log
  const openLogDetailsDrawer = (log: LogEntry) => {
    openDrawer("log-details", {
      spanData: log,
      viewMode,
      promptName,
      projectId,
    });
  };

  // Fetch traces from API
  const fetchTraces = useCallback(async (loadMore = false) => {
    if (!promptName || !projectId) return;

    if (loadMore) {
      setIsLoadingMore(true);
    } else {
      setIsLoading(true);
      setPage(1);
    }

    try {
      const currentPage = loadMore ? page + 1 : 1;
      const { from_date, to_date } = getTimeRangeDates(timeRange);

      // Build params based on view mode
      const params: Record<string, any> = {
        project_id: projectId,
        from_date,
        to_date,
        limit: viewMode === 'flatten' ? ITEMS_PER_PAGE : 1000,
        page: viewMode === 'flatten' ? currentPage : 1,
      };

      // Add flatten parameter when in flatten mode
      if (viewMode === 'flatten') {
        params.flatten = true;
      }

      const response: any = await AppRequest.Get(
        `/prompts/${promptName}/traces`,
        { params }
      );

      if (response.data?.items && response.data.items.length > 0) {
        const spans: TraceSpan[] = response.data.items;
        const total = response.data.total_record || 0;

        // Find earliest and latest timestamps for offset calculation and chart
        const timestamps = spans.map((s: TraceSpan) => new Date(s.timestamp).getTime());
        const earliestTimestamp = Math.min(...timestamps);
        const latestTimestamp = Math.max(...timestamps);

        // Build data based on view mode
        let newData: LogEntry[];
        if (viewMode === 'flatten') {
          newData = buildFlatSpansList(spans, earliestTimestamp);
        } else {
          // Build list of root spans only (those with empty parent_span_id)
          newData = buildRootSpansList(spans, earliestTimestamp);
        }

        // Handle append vs replace for infinite scroll
        if (loadMore && viewMode === 'flatten') {
          setLogsData(prev => [...prev, ...newData]);
          setPage(currentPage);
        } else {
          setLogsData(newData);
        }

        // Update pagination state
        setHasMore(currentPage * ITEMS_PER_PAGE < total);

        // Build chart data - group by time buckets (only on initial load)
        if (!loadMore) {
          const bucketCount = 6;
          const bucketSize = (latestTimestamp - earliestTimestamp) / bucketCount || 60000;
          const buckets: { time: string; count: number }[] = [];

          for (let i = 0; i < bucketCount; i++) {
            const bucketStart = earliestTimestamp + i * bucketSize;
            const bucketEnd = bucketStart + bucketSize;
            const count = spans.filter((s: TraceSpan) => {
              const ts = new Date(s.timestamp).getTime();
              return ts >= bucketStart && ts < bucketEnd;
            }).length;

            buckets.push({
              time: formatTime(new Date(bucketStart).toISOString()),
              count,
            });
          }

          setChartData({
            times: buckets.map((b) => b.time),
            values: buckets.map((b) => b.count),
          });
        }
      } else {
        if (!loadMore) {
          setLogsData([]);
          setChartData({ times: [], values: [] });
        }
        setHasMore(false);
      }
    } catch (error) {
      console.error("Error fetching traces:", error);
      if (!loadMore) {
        setLogsData([]);
        setChartData({ times: [], values: [] });
      }
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [promptName, projectId, timeRange, viewMode, page]);

  // Fetch traces when dependencies change (except page - that's handled by loadMore)
  useEffect(() => {
    fetchTraces();
  }, [promptName, projectId, timeRange, viewMode]);

  // Reset state when view mode changes
  useEffect(() => {
    setLogsData([]);
    setExpandedIds(new Set());
    setSelectedId(null);
    setPage(1);
    setHasMore(true);
  }, [viewMode]);

  // Infinite scroll observer for flatten view
  useEffect(() => {
    if (!loadMoreRef.current || viewMode !== 'flatten') return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoadingMore && !isLoading) {
          fetchTraces(true); // Load more
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, isLoading, viewMode, fetchTraces]);

  // Fetch trace details for a specific trace
  const fetchTraceDetails = useCallback(
    async (traceId: string, spanId: string) => {
      if (!promptName || !projectId) return;

      // Set loading state for this specific log entry
      setLogsData((prev) =>
        prev.map((log) =>
          log.id === spanId ? { ...log, isLoadingChildren: true } : log
        )
      );

      try {
        const response: any = await AppRequest.Get(
          `/prompts/${promptName}/traces/${traceId}`,
          {
            params: {
              project_id: projectId,
            },
          }
        );

        if (response.data?.spans && response.data.spans.length > 0) {
          const spans: TraceSpan[] = response.data.spans;

          // Find earliest timestamp for offset calculation
          const timestamps = spans.map((s: TraceSpan) =>
            new Date(s.timestamp).getTime()
          );
          const earliestTimestamp = Math.min(...timestamps);

          // Build children tree from trace detail
          const children = buildChildrenFromTraceDetail(
            spans,
            spanId,
            earliestTimestamp
          );

          // Update the log entry with children (preserve original childCount from API)
          setLogsData((prev) =>
            prev.map((log) =>
              log.id === spanId
                ? {
                  ...log,
                  children,
                  // Keep original childCount from API, don't overwrite with children.length
                  isLoadingChildren: false,
                  canExpand: children.length > 0,
                }
                : log
            )
          );

          // Auto-expand if children were fetched
          if (children.length > 0) {
            setExpandedIds((prev) => new Set(prev).add(spanId));
          }
        } else {
          // No children found
          setLogsData((prev) =>
            prev.map((log) =>
              log.id === spanId
                ? { ...log, isLoadingChildren: false, canExpand: false }
                : log
            )
          );
        }
      } catch (error) {
        console.error("Error fetching trace details:", error);
        setLogsData((prev) =>
          prev.map((log) =>
            log.id === spanId
              ? { ...log, isLoadingChildren: false, canExpand: false }
              : log
          )
        );
      }
    },
    [promptName, projectId]
  );

  const handleToggleExpand = (id: string) => {
    // Find the log entry
    const logEntry = logsData.find((log) => log.id === id);

    if (logEntry) {
      // If it's a root span that hasn't loaded children yet, fetch them
      if (logEntry.canExpand && !logEntry.children && logEntry.traceId) {
        fetchTraceDetails(logEntry.traceId, id);
        return;
      }
    }

    // Toggle expand state
    setExpandedIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  // Helper to collect all expandable IDs recursively from loaded data
  const collectAllExpandableIds = (logs: LogEntry[]): string[] => {
    const ids: string[] = [];
    const traverse = (entries: LogEntry[]) => {
      entries.forEach((entry) => {
        if (entry.canExpand || (entry.children && entry.children.length > 0)) {
          ids.push(entry.id);
        }
        if (entry.children) {
          traverse(entry.children);
        }
      });
    };
    traverse(logs);
    return ids;
  };

  // Fetch trace details for expand all (returns updated log entry)
  const fetchTraceDetailsForExpandAll = async (
    log: LogEntry
  ): Promise<LogEntry> => {
    if (!promptName || !projectId || !log.traceId) return log;

    try {
      const response: any = await AppRequest.Get(
        `/prompts/${promptName}/traces/${log.traceId}`,
        {
          params: {
            project_id: projectId,
          },
        }
      );

      if (response.data?.spans && response.data.spans.length > 0) {
        const spans: TraceSpan[] = response.data.spans;
        const timestamps = spans.map((s: TraceSpan) =>
          new Date(s.timestamp).getTime()
        );
        const earliestTimestamp = Math.min(...timestamps);

        const children = buildChildrenFromTraceDetail(
          spans,
          log.spanId || log.id,
          earliestTimestamp
        );

        return {
          ...log,
          children,
          // Keep original childCount from API, don't overwrite with children.length
          isLoadingChildren: false,
          canExpand: children.length > 0,
        };
      }
    } catch (error) {
      console.error("Error fetching trace details for expand all:", error);
    }

    return { ...log, isLoadingChildren: false, canExpand: false };
  };

  // Expand/Collapse all handler
  const handleExpandCollapseAll = async () => {
    if (isAllExpanded) {
      // Collapse all - clear all expanded IDs
      setExpandedIds(new Set());
      setIsAllExpanded(false);
    } else {
      // Expand all - first fetch children for root spans that need loading
      const rootSpansNeedingFetch = logsData.filter(
        (log) => log.canExpand && !log.children && log.traceId
      );

      if (rootSpansNeedingFetch.length > 0) {
        // Set loading state for all spans being fetched
        setLogsData((prev) =>
          prev.map((log) =>
            rootSpansNeedingFetch.some((r) => r.id === log.id)
              ? { ...log, isLoadingChildren: true }
              : log
          )
        );

        // Fetch all trace details in parallel
        const fetchPromises = rootSpansNeedingFetch.map((log) =>
          fetchTraceDetailsForExpandAll(log)
        );
        const updatedLogs = await Promise.all(fetchPromises);

        // Update logsData with fetched children and collect all IDs
        const updatedLogsMap = new Map(updatedLogs.map((log) => [log.id, log]));
        const newLogsData = logsData.map((log) => updatedLogsMap.get(log.id) || log);

        // Collect all expandable IDs from the updated data
        const allIds = collectAllExpandableIds(newLogsData);

        setLogsData(newLogsData);
        setExpandedIds(new Set(allIds));
      } else {
        // All children already loaded, just expand
        const allIds = collectAllExpandableIds(logsData);
        setExpandedIds(new Set(allIds));
      }

      setIsAllExpanded(true);
    }
  };

  // Close/Clear handler
  const handleClose = () => {
    setSelectedId(null);

    if (isLive) {
      // If showing socket data, clear current data and allow new data to appear
      setLogsData([]);
      liveSpanIdsRef.current.clear();
    } else {
      // If showing regular traces, reset time filter to default and refetch
      const defaultTimeRange = "5m";
      if (timeRange === defaultTimeRange) {
        // If already at default, manually trigger refetch since setState won't cause a change
        fetchTraces();
      } else {
        // Setting timeRange will trigger useEffect which calls fetchTraces
        setTimeRange(defaultTimeRange);
      }
    }
  };

  // Toggle live mode
  const handleToggleLive = () => {
    setIsLive((prev) => {
      if (!prev) {
        // Enabling live mode: clear existing traces data and deduplication set
        setLogsData([]);
        liveSpanIdsRef.current.clear();
      }
      return !prev;
    });
  };

  // Handle time range change - disables live mode if active
  const handleTimeRangeChange = (newRange: string) => {
    if (isLive) {
      // Disable live mode and clear live data when changing time filter
      setIsLive(false);
      setLogsData([]);
      liveSpanIdsRef.current.clear();
    }
    setTimeRange(newRange);
  };

  // Initialize and update echarts
  useEffect(() => {
    if (!chartRef.current) return;

    const myChart = echarts.init(chartRef.current, null, {
      renderer: "canvas",
    });

    const option = {
      backgroundColor: "transparent",
      grid: {
        left: "3%",
        right: "3%",
        bottom: "15%",
        top: "20%",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: chartData.times,
        axisLine: {
          lineStyle: { color: "#333" },
        },
        axisTick: { show: false },
        axisLabel: {
          color: "#6A6E76",
          fontSize: 11,
        },
      },
      yAxis: {
        type: "value",
        min: 0,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: {
          lineStyle: { color: "#1F1F1F" },
        },
        axisLabel: {
          color: "#6A6E76",
          fontSize: 11,
          formatter: (value: number) => value.toFixed(1),
        },
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(0,0,0,0.85)",
        borderColor: "#1F1F1F",
        textStyle: { color: "#EEEEEE", fontSize: 12 },
      },
      series: [
        {
          type: "bar",
          data: chartData.values,
          barWidth: "60%",
          itemStyle: {
            color: "#965CDE",
            borderRadius: [4, 4, 0, 0],
          },
        },
      ],
    };

    myChart.setOption(option);

    const handleResize = () => myChart.resize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      myChart.dispose();
    };
  }, [chartData]);

  const timeRangeOptions = [
    { label: "Last 5 minutes", value: "5m" },
    { label: "Last 15 minutes", value: "15m" },
    { label: "Last 30 minutes", value: "30m" },
    { label: "Last 1 hour", value: "1h" },
    { label: "Last 24 hours", value: "24h" },
    { label: "Last 1 week", value: "7d" },
    { label: "Last 1 month", value: "30d" },
  ];

  // Get time range label for display
  const getTimeRangeLabel = () => {
    const option = timeRangeOptions.find((o) => o.value === timeRange);
    return option?.label?.replace("Last ", "") || "5 minutes";
  };

  return (
    <div className="px-[3.5rem] pb-8">
      {/* Header */}
      <div className="mb-6">
        <Text_26_600_FFFFFF className="block mb-2">Logs</Text_26_600_FFFFFF>
        <Text_12_400_B3B3B3 className="max-w-[850px]">
          View OpenTelemetry traces and spans for this prompt. Monitor request
          flow, performance metrics, and debug issues across your AI pipeline.
        </Text_12_400_B3B3B3>
      </div>

      {/* Chart Section */}
      <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-4 mb-4">
        {/* Chart Controls */}
        <div className="flex justify-end items-center gap-2 mb-2">
          <CustomSelect
            name="timeRange"
            value={timeRange}
            onChange={handleTimeRangeChange}
            selectOptions={timeRangeOptions}
            ClassNames="w-[160px] !py-[.1rem]"
            InputClasses="!text-[.625rem] !py-[.1rem] !min-h-[1.6rem] !h-[1.6rem]"
            placeholder="Select time range"
          />
          <div className="flex items-center border border-[#3a3a3a] rounded-md overflow-hidden max-h-[1.6rem]">
            <button
              className={`p-[.4rem] border-r border-[#3a3a3a] transition-colors ${
                viewMode === 'traces'
                  ? "bg-[#2a2a2a] text-white"
                  : "bg-[#1a1a1a] text-[#B3B3B3] hover:text-white hover:bg-[#2a2a2a]"
              }`}
              title="Traces view"
              onClick={() => setViewMode('traces')}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="4" y1="6" x2="20" y2="6" />
                <line x1="4" y1="12" x2="20" y2="12" />
                <line x1="4" y1="18" x2="20" y2="18" />
                <circle cx="8" cy="6" r="2" fill="currentColor" />
                <circle cx="16" cy="12" r="2" fill="currentColor" />
                <circle cx="10" cy="18" r="2" fill="currentColor" />
              </svg>
            </button>
            <button
              className={`p-[.4rem] transition-colors ${
                viewMode === 'flatten'
                  ? "bg-[#2a2a2a] text-white"
                  : "bg-[#1a1a1a] text-[#B3B3B3] hover:text-white hover:bg-[#2a2a2a]"
              }`}
              title="Flatten view"
              onClick={() => setViewMode('flatten')}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {/* Chart */}
        <div ref={chartRef} className="w-full h-[180px]" />
      </div>

      {/* Logs List Section */}
      <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg overflow-hidden">
        {/* List Header */}
        <div className="px-4 py-3 border-b border-[#1F1F1F] flex justify-between items-center">
          <Text_12_400_B3B3B3>
            {isLoading
              ? "Loading traces..."
              : `Showing ${logsData.length} records from the last ${getTimeRangeLabel()}`}
          </Text_12_400_B3B3B3>
          <div className="flex items-center gap-4">
            {/* Expand/Collapse button */}
            <button
              className="flex items-center gap-1.5 text-[#B3B3B3] hover:text-white transition-colors text-xs"
              onClick={handleExpandCollapseAll}
              title={isAllExpanded ? "Collapse all" : "Expand all"}
            >
              <span>{isAllExpanded ? "Collapse" : "Expand"}</span>
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className={isAllExpanded ? "" : "rotate-180"}
              >
                <path d="M4 14l8-8 8 8" />
                <path d="M4 10l8 8 8-8" />
              </svg>
            </button>

            {/* Close button */}
            <button
              className="flex items-center gap-1.5 text-[#B3B3B3] hover:text-white transition-colors text-xs"
              onClick={handleClose}
              title="Close selection"
            >
              <span>Clear</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>

            {/* Live button */}
            <button
              className={`flex items-center gap-1.5 transition-colors text-xs ${isLive ? "text-white" : "text-[#B3B3B3] hover:text-white"}`}
              onClick={handleToggleLive}
              title={isLive ? `Live: ${connectionStatus}${socketError ? ` - ${socketError.message}` : ''}` : "Enable live mode"}
            >
              {/* Pulsing green dot when subscribed */}
              {isLive && isSubscribed && (
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
              )}
              {/* Loading spinner when connecting */}
              {isLive && !isSubscribed && connectionStatus !== 'error' && connectionStatus !== 'disconnected' && (
                <Spin size="small" className="scale-50" />
              )}
              {/* Red dot on error */}
              {isLive && connectionStatus === 'error' && (
                <span className="h-2 w-2 rounded-full bg-red-500"></span>
              )}
              <span>Live</span>
            </button>
          </div>
        </div>

        {/* Log rows container */}
        <div className="relative">

          {/* Log Rows */}
          <div className="max-h-[500px] overflow-auto">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Spin size="large" />
              </div>
            ) : logsData.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Text_12_400_B3B3B3 className="mb-2">
                  No traces found for the selected time range
                </Text_12_400_B3B3B3>
                <Text_12_400_B3B3B3>
                  Try selecting a longer time range or check if traces are being collected
                </Text_12_400_B3B3B3>
              </div>
            ) : viewMode === 'traces' ? (
              <div className="min-w-max">
                <LogTree
                  logs={logsData}
                  selectedId={selectedId}
                  expandedIds={expandedIds}
                  onSelect={setSelectedId}
                  onToggleExpand={handleToggleExpand}
                  onViewDetails={openLogDetailsDrawer}
                />
              </div>
            ) : (
              <div className="min-w-max">
                {/* Flatten view - flat list of all spans */}
                {logsData.map((log) => (
                  <FlatLogRow
                    key={log.id}
                    row={log}
                    referenceDuration={Math.max(...logsData.map(l => l.duration), 1)}
                    isSelected={selectedId === log.id}
                    onSelect={() => setSelectedId(log.id)}
                    onViewDetails={openLogDetailsDrawer}
                  />
                ))}
                {/* Infinite scroll trigger */}
                <div ref={loadMoreRef} className="h-4">
                  {isLoadingMore && (
                    <div className="flex justify-center py-2">
                      <Spin size="small" />
                    </div>
                  )}
                  {!hasMore && logsData.length > 0 && (
                    <div className="flex justify-center py-2">
                      <Text_12_400_B3B3B3>No more records</Text_12_400_B3B3B3>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

    </div>
  );
};

export default LogsTab;
