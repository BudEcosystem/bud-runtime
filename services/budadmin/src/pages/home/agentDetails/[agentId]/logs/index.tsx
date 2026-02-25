import React, { useEffect, useLayoutEffect, useRef, useState, useCallback } from "react";
import { Tag, Spin, Tooltip, Popover } from "antd";
import * as echarts from "echarts";
import dayjs from "dayjs";
import type { Dayjs } from "dayjs";
import {
  Text_10_400_B3B3B3,
  Text_10_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_600_EEEEEE,
  Text_26_600_FFFFFF,
} from "@/components/ui/text";
import LogfireDateRangePicker, { DateRangeValue, PRESET_OPTIONS } from "@/components/ui/LogfireDateRangePicker";
import { AppRequest } from "src/pages/api/requests";
import { useDrawer } from "src/hooks/useDrawer";
import { useObservabilitySocket } from "@/hooks/useObservabilitySocket";
import ProjectTags from "src/flows/components/ProjectTags";
import { usePromptMetrics } from "src/hooks/usePromptMetrics";

// API Response Types
interface SpanEvent {
  timestamp: string;
  name: string;
  attributes: Record<string, any>;
}

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
  status_message?: string;
  child_span_count?: number;
  events?: SpanEvent[];
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
  // Logfire-style fields
  level?: string; // INFO, WARN, ERROR, DEBUG
  scopeName?: string; // otel scope name
  inputTokens?: string; // gen_ai.usage.input_tokens
  outputTokens?: string; // gen_ai.usage.output_tokens
  serviceName?: string; // service_name for badge
  // Exception fields
  hasException?: boolean; // true if this span has an exception/error
  errorType?: string; // e.g., "Internal Server Error", "Not Found", "Bad Request"
}

interface LogsTabProps {
  promptName?: string;
  promptId?: string;
  projectId?: string;
}

// Chart configuration for real-time scrolling
const ONE_HOUR_MS = 60 * 60 * 1000;

const CHART_CONFIG = {
  bucketCount: 30, // Number of bars in the chart
  updateInterval: 500, // Chart update interval in ms (faster for smoother scrolling)
};

// Get time window in ms from time range string
const getTimeWindowMs = (range: string): number => {
  switch (range) {
    case "5m": return 5 * 60 * 1000;
    case "15m": return 15 * 60 * 1000;
    case "30m": return 30 * 60 * 1000;
    case "1h": return 60 * 60 * 1000;
    case "24h": return 24 * 60 * 60 * 1000;
    case "7d": return 7 * 24 * 60 * 60 * 1000;
    case "30d": return 30 * 24 * 60 * 60 * 1000;
    default: return 5 * 60 * 1000;
  }
};

// Generate time buckets based on current time (for scrolling effect)
interface TimeBucket {
  start: number;
  end: number;
  label: string;
}

const generateTimeBuckets = (timeWindowMs: number, bucketCount: number): TimeBucket[] => {
  const now = Date.now();
  const bucketSize = timeWindowMs / bucketCount;
  const buckets: TimeBucket[] = [];

  for (let i = 0; i < bucketCount; i++) {
    const start = now - timeWindowMs + (i * bucketSize);
    const end = start + bucketSize;
    const date = new Date(end);

    // Format label based on time window
    let label: string;
    if (timeWindowMs <= 60000) {
      // <= 1 minute: show seconds
      label = date.toLocaleTimeString('en-US', {
        hour12: false,
        minute: '2-digit',
        second: '2-digit',
      });
    } else if (timeWindowMs <= ONE_HOUR_MS) {
      // <= 1 hour: show minutes:seconds
      label = date.toLocaleTimeString('en-US', {
        hour12: false,
        minute: '2-digit',
        second: '2-digit',
      });
    } else if (timeWindowMs <= 86400000) {
      // <= 24 hours: show hours:minutes
      label = date.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
      });
    } else {
      // > 24 hours: show date + time
      label = date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      }) + ' ' + date.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
      });
    }

    buckets.push({ start, end, label });
  }

  return buckets;
};

// Aggregate traces into time buckets for chart
interface ChartBucketData {
  label: string;
  successCount: number;
  errorCount: number;
  total: number;
}

// Extended bucket data for tooltip display
interface ExtendedBucketData {
  value: number;
  bucketStart: number;
  bucketEnd: number;
  totalDuration: number; // Total duration in seconds for traces in this bucket
}

const aggregateTracesIntoBuckets = (
  traces: { timestamp: number; status?: string }[],
  buckets: TimeBucket[]
): ChartBucketData[] => {
  return buckets.map(bucket => {
    const filtered = traces.filter(
      t => t.timestamp >= bucket.start && t.timestamp < bucket.end
    );

    const errorCount = filtered.filter(t => t.status === 'error' || t.status === 'ERROR').length;
    const successCount = filtered.length - errorCount;

    return {
      label: bucket.label,
      successCount,
      errorCount,
      total: filtered.length,
    };
  });
};

// Token metrics popover component - reusable for LogRow and FlatLogRow
const TokenMetricsPopover = ({
  inputTokens,
  outputTokens,
  scopeName,
}: {
  inputTokens?: string;
  outputTokens?: string;
  scopeName?: string;
}) => {
  if (!inputTokens && !outputTokens) return null;

  return (
    <Popover
      placement="top"
      arrow={false}
      styles={{ body: { padding: 0, background: '#1F1F1F', border: '1px solid #3a3a3a', borderRadius: '6px' } }}
      content={
        <div className="min-w-[180px]">
          <div className="px-3 py-2 border-b border-[#3a3a3a]">
            <Text_10_600_EEEEEE className="block">LLM Tokens (aggregated)</Text_10_600_EEEEEE>
            {scopeName && (
              <Text_10_400_B3B3B3 className="block mt-1">{scopeName}</Text_10_400_B3B3B3>
            )}
          </div>
          <div className="px-3 py-2">
            <div className="flex justify-between items-center text-[.625rem] border-b border-[#2a2a2a] pb-1 mb-1">
              <span className="text-[#757575]">Type</span>
              <span className="text-[#757575]">Amount</span>
            </div>
            <div className="flex justify-between items-center text-[.625rem] py-1">
              <span className="text-[#B3B3B3]">Input</span>
              <span className="text-[#EEEEEE]">↗ {inputTokens || 0}</span>
            </div>
            <div className="flex justify-between items-center text-[.625rem] py-1">
              <span className="text-[#B3B3B3]">Output</span>
              <span className="text-[#EEEEEE]">↙ {outputTokens || 0}</span>
            </div>
          </div>
        </div>
      }
    >
      <div className="cursor-pointer">
        <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[.5rem] text-[#B3B3B3] w-fit pointer-events-none px-[.2rem] w-full text-center flex justify-center items-center gap-x-[.3rem] leading-[200%]">
          <div className="text-[.75rem]">∅</div>
          <div className="flex justify-center items-center gap-x-[.1rem]">
            {/* <div className="text-[.4rem]">∑</div> */}
            <div className="text-[.4rem]">↗</div>{inputTokens || 0}
            <div className="text-[.4rem]">↙</div>{outputTokens || 0}
          </div>
        </Tag>
      </div>
    </Popover>
  );
};

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
// Hook to detect screen width for responsive tree positioning
const useScreenWidth = () => {
  const [width, setWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1366);

  useEffect(() => {
    const handleResize = () => setWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return width;
};

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
  const screenWidth = useScreenWidth();
  const hasChildren = row.children && row.children.length > 0;
  const canExpand = row.canExpand || hasChildren;
  const isChild = depth > 0;
  const indentPx = depth * 18; // 18px indent per level

  // Base position for tree lines - center of expand button/tag
  // Responsive calculation based on column widths:
  // < 1680px: 12px padding + 50px time + 60px namespace = 122px
  // >= 1680px: 12px padding + 65px time + 90px namespace = 167px
  // >= 1920px: 12px padding + 80px time + 115px namespace = 207px
  const baseTreePosition = screenWidth >= 1920 ? 207 : screenWidth >= 1680 ? 167 : 122;
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
          <div style={{ flexShrink: 0 }} className="w-[50px] 1680px:w-[65px] 1920px:w-[80px]">
            <Text_10_400_B3B3B3>{row.time}</Text_10_400_B3B3B3>
          </div>

          {/* Namespace - fixed width, no indent */}
          <div style={{ flexShrink: 0 }} className="flex justify-start items-center w-[60px] 1680px:w-[90px] 1920px:w-[115px]">
            <Tooltip title={row.namespace || "-"} placement="top">
              <Tag className="bg-[#423A1A40] border-[#D1B854] text-[#D1B854] text-[.5rem] max-w-[80px] truncate px-[.2rem] !leading-[200%]">
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
                  <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[#B3B3B3] text-[.5rem] w-fit pointer-events-none px-[.2rem] w-full text-center !leading-[200%] min-w-[1.5rem] 1920px:min-w-[1.3rem]">
                    <Spin size="small" />
                  </Tag>
                ) : (
                  <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[#B3B3B3] text-[.5rem] w-fit pointer-events-none px-[.2rem] w-full text-center !leading-[200%]  min-w-[1.5rem] 1920px:min-w-[1.3rem]">
                    {isExpanded ? "−" : "+"}{row.childCount || row.children?.length || ""}
                  </Tag>
                )}
              </div>
            )}
          </div>

          {/* Title */}
          <div className="flex items-center overflow-hidden flex-1 min-w-0">
            <Tooltip title={row.title} placement="top">
              <Text_10_600_EEEEEE className="ibm whitespace-nowrap overflow-hidden text-ellipsis max-w-[130px] 1680px:max-w-[150px] block">
                {row.title}
              </Text_10_600_EEEEEE>
            </Tooltip>
          </div>
        </div>
        <div className="flex justify-end items-center min-w-[30%] pr-[12px] pl-[12px] flex-shrink-0">
          {/* Metrics tags */}
          <div className="flex gap-2 items-center flex-shrink-0 mr-3">
            {/* Token metrics with original icon style */}
            <TokenMetricsPopover
              inputTokens={row.inputTokens}
              outputTokens={row.outputTokens}
              scopeName={row.scopeName}
            />
            {/* Exception tag */}
            {row.hasException && (
              <Tooltip title={row.errorType || "Exception"} placement="top">
                <div>
                  <ProjectTags
                    name="exception"
                    color="#EC7575"
                    textClass="text-[.5rem] leading-[90%]"
                  />
                </div>
              </Tooltip>
            )}
            {row.metrics.tag && (
              <Tooltip title={row.metrics.tag} placement="top">
                <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[.5rem] text-[#B3B3B3] max-w-[80px] truncate w-fit pointer-events-none px-[.2rem] w-full text-center !leading-[200%]">
                  {row.metrics.tag}
                </Tag>
              </Tooltip>
            )}
            {/* Scope tag (like Logfire's auto_tracing, logfire, etc.) */}
            {/* {row.scopeName && (
              <Tooltip title={row.scopeName} placement="top">
                <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[.5rem] text-[#B3B3B3] max-w-[80px] truncate w-fit pointer-events-none px-[.2rem] w-full text-center !leading-[200%]">
                  {row.scopeName}
                </Tag>
              </Tooltip>
            )} */}
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
      className={`w-full flex-auto relative transition-colors border-b border-[rgba(255,255,255,0.08)] ${isSelected
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
          <div style={{ width: "50px", flexShrink: 0 }} className="1680px:w-[65px] 1920px:w-[80px]">
            <Text_10_400_B3B3B3>{row.time}</Text_10_400_B3B3B3>
          </div>

          {/* Status */}
          <div style={{ width: "60px", flexShrink: 0 }} className="flex justify-start items-center  1680px:w-[90px] 1920px:w-[115px]">
            <Tooltip title={row.namespace || "-"} placement="top">
              <Tag className="bg-[#2a2a2a] border-[#D4A853] text-[#D4A853] text-[.5rem] max-w-[80px] truncate px-[.2rem]">
                {row.namespace || "-"}
              </Tag>
            </Tooltip>
          </div>

          {/* Title */}
          <div className="flex items-center overflow-hidden flex-1 min-w-0">
            <Tooltip title={row.title} placement="top">
              <Text_10_600_EEEEEE className="ibm whitespace-nowrap overflow-hidden text-ellipsis max-w-[130px] 1680px:max-w-[150px]  block">
                {row.title}
              </Text_10_600_EEEEEE>
            </Tooltip>
          </div>
        </div>
        <div className="flex justify-end items-center min-w-[30%] pr-3 pl-3 flex-shrink-0 ">
          {/* Metrics tags */}
          <div className="flex gap-2 items-center flex-shrink-0 mr-3">
            {/* Token metrics with original icon style */}
            <TokenMetricsPopover
              inputTokens={row.inputTokens}
              outputTokens={row.outputTokens}
              scopeName={row.scopeName}
            />
            {/* Exception tag */}
            {row.hasException && (
              <Tooltip title={row.errorType || "Exception"} placement="top">
                <div>
                  <ProjectTags
                    name="exception"
                    color="#EC7575"
                    textClass="text-[.5rem]"
                  />
                </div>
              </Tooltip>
            )}
            {row.metrics.tag && (
              <Tooltip title={row.metrics.tag} placement="top">
                <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[.5rem] text-[#B3B3B3] max-w-[80px] truncate w-fit pointer-events-none px-[.2rem] w-full text-center !leading-[200%]">
                  {row.metrics.tag}
                </Tag>
              </Tooltip>
            )}
            {/* Scope tag (like Logfire's auto_tracing, logfire, etc.) */}
            {row.scopeName && (
              <Tooltip title={row.scopeName} placement="top">
                <Tag className="bg-[#2a2a2a] border-[#3a3a3a] text-[.5rem] text-[#B3B3B3] max-w-[80px] truncate w-fit pointer-events-none px-[.2rem] w-full text-center !leading-[200%]">
                  {row.scopeName}
                </Tag>
              </Tooltip>
            )}
          </div>

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

// Helper function to get time range dates - supports both presets and custom ranges
const getTimeRangeDates = (
  range: string,
  customRange?: [Dayjs, Dayjs] | null
): { from_date: string; to_date: string } => {
  // If custom range is provided, use it
  if (customRange) {
    return {
      from_date: formatDateForApi(customRange[0].toDate()),
      to_date: formatDateForApi(customRange[1].toDate()),
    };
  }

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
    case "6h":
      from_date = new Date(now.getTime() - 6 * 60 * 60 * 1000);
      break;
    case "12h":
      from_date = new Date(now.getTime() - 12 * 60 * 60 * 1000);
      break;
    case "24h":
      from_date = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      break;
    case "2d":
      from_date = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);
      break;
    case "7d":
      from_date = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      break;
    case "14d":
      from_date = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);
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

const formatChartLabel = (timestamp: string | number): string => {
  const date = new Date(timestamp);
  const hoursDiff = (Date.now() - date.getTime()) / (1000 * 60 * 60);
  if (hoursDiff <= 24) {
    return date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
  } else if (hoursDiff <= 24 * 7) {
    return (
      date.toLocaleDateString("en-US", { weekday: "short" }) +
      " " +
      date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" })
    );
  }
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};

// Helper function to detect exception/error status from a span
const detectSpanException = (span: TraceSpan): { hasException: boolean; errorType?: string } => {
  const attrs = span.span_attributes || {};

  // Check 1: status_code is STATUS_CODE_ERROR
  if (span.status_code === "STATUS_CODE_ERROR") {
    // Try to extract error type from various sources
    const errorType = attrs["gateway_analytics.error_type"]
      || (span.events?.[0]?.attributes?.error_type)
      || "Error";
    return { hasException: true, errorType };
  }

  // Check 2: events array contains exception events
  if (span.events && span.events.length > 0) {
    const exceptionEvent = span.events.find(event =>
      event.name?.toLowerCase().includes("exception") ||
      event.attributes?.level === "ERROR"
    );
    if (exceptionEvent) {
      const errorType = exceptionEvent.attributes?.error_type || "Exception";
      return { hasException: true, errorType };
    }
  }

  // Check 3: span_attributes has gateway_analytics.error_type
  if (attrs["gateway_analytics.error_type"]) {
    return { hasException: true, errorType: attrs["gateway_analytics.error_type"] };
  }

  // Check 4: HTTP error status code in span_attributes (400+)
  const httpStatusCode = attrs["gateway_analytics.status_code"];
  if (httpStatusCode) {
    const statusNum = parseInt(httpStatusCode, 10);
    if (statusNum >= 400) {
      const errorType = attrs["gateway_analytics.error_type"]
        || (statusNum >= 500 ? "Server Error" : "Client Error");
      return { hasException: true, errorType };
    }
  }

  // Check 5: status_message contains error information
  if (span.status_message && span.status_message.length > 0) {
    // If there's a non-empty status_message, it usually indicates an error
    const errorType = attrs["gateway_analytics.error_type"] || "Error";
    return { hasException: true, errorType };
  }

  return { hasException: false };
};

// Helper function to convert a TraceSpan to a LogEntry
// Centralizes the mapping logic to avoid duplication across build functions
const traceSpanToLogEntry = (
  span: TraceSpan,
  earliestTimestamp: number,
  overrides?: Partial<LogEntry>
): LogEntry => {
  const timestamp = new Date(span.timestamp).getTime();
  const attrs = span.span_attributes || {};

  // Detect exception status
  const { hasException, errorType } = detectSpanException(span);

  const baseEntry: LogEntry = {
    id: span.span_id,
    time: formatTime(span.timestamp),
    namespace: span.resource_attributes?.["service.name"] || "",
    title: span.span_name || "Unknown Span",
    childCount: span.child_span_count,
    metrics: {
      tag: span.service_name || "",
    },
    duration: (span.duration ?? 0) / 1_000_000_000, // Convert nanoseconds to seconds
    startOffsetSec: (timestamp - earliestTimestamp) / 1000,
    traceId: span.trace_id,
    spanId: span.span_id,
    parentSpanId: span.parent_span_id || "",
    canExpand: (span.child_span_count ?? 0) > 0,
    rawData: span as unknown as Record<string, any>,
    // Logfire-style fields
    level: attrs.level || "INFO",
    scopeName: span.scope_name || "",
    inputTokens: attrs["gen_ai.usage.input_tokens"],
    outputTokens: attrs["gen_ai.usage.output_tokens"],
    serviceName: span.service_name,
    // Exception fields
    hasException,
    errorType,
  };

  // Apply any overrides provided by the caller
  return overrides ? { ...baseEntry, ...overrides } : baseEntry;
};

// Helper function to extract only root spans (those with empty parent_span_id)
const buildRootSpansList = (spans: TraceSpan[], earliestTimestamp: number): LogEntry[] => {
  return spans
    .filter((span) => !span.parent_span_id || span.parent_span_id === "")
    .map((span) => traceSpanToLogEntry(span, earliestTimestamp))
    .sort((a, b) => a.startOffsetSec - b.startOffsetSec);
};

// Helper function to build flat list of all spans (for flatten view)
const buildFlatSpansList = (spans: TraceSpan[], earliestTimestamp: number): LogEntry[] => {
  return spans
    .map((span) => traceSpanToLogEntry(span, earliestTimestamp, { canExpand: false }))
    .sort((a, b) => a.startOffsetSec - b.startOffsetSec);
};

// Helper function to build hierarchical tree from trace detail spans
const buildChildrenFromTraceDetail = (
  spans: TraceSpan[],
  rootSpanId: string,
  earliestTimestamp: number
): LogEntry[] => {
  // Build a map of span_id to LogEntry
  const spanMap = new Map<string, LogEntry>();

  // First pass: create all LogEntry nodes with empty children array for tree building
  spans.forEach((span) => {
    const entry = traceSpanToLogEntry(span, earliestTimestamp, { children: [] });
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

    // Helper to count total descendants recursively
    const countDescendants = (node: LogEntry): number => {
      if (!node.children || node.children.length === 0) return 0;
      return node.children.reduce((sum, child) => sum + 1 + countDescendants(child), 0);
    };

    // Recursive function to build children
    const buildNode = (span: TraceSpan): LogEntry => {
      const children = traceSpans.filter(s => s.parent_span_id === span.span_id);
      const childNodes = children.map(c => buildNode(c));

      // Sort children by timestamp
      childNodes.sort((a, b) => a.startOffsetSec - b.startOffsetSec);

      // Calculate total descendant count (all children + grandchildren + etc.)
      const totalDescendants = childNodes.reduce(
        (sum, child) => sum + 1 + countDescendants(child),
        0
      );

      return traceSpanToLogEntry(span, earliestTimestamp, {
        childCount: totalDescendants,
        canExpand: childNodes.length > 0,
        children: childNodes.length > 0 ? childNodes : undefined,
      });
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
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const [timeRange, setTimeRange] = useState("5m");
  const [customDateRange, setCustomDateRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [logsData, setLogsData] = useState<LogEntry[]>([]);
  const [isAllExpanded, setIsAllExpanded] = useState(false);
  const [isLive, setIsLive] = useState(false);
  const [totalRecord, setTotalRecord] = useState(0);

  // Time-series API hook for chart data
  const { fetchPromptTimeSeries, PROMPT_METRICS: METRICS } = usePromptMetrics();

  // Live chart data - stores traces with timestamps for aggregation
  const liveChartTracesRef = useRef<{ timestamp: number; status?: string; duration?: number }[]>([]);
  const chartUpdateIntervalRef = useRef<NodeJS.Timeout | null>(null);
  // Time-series API data points for merging with live traces
  const timeSeriesDataRef = useRef<{ timestamp: number; value: number }[]>([]);


  // Live streaming state
  const liveSpanIdsRef = useRef<Set<string>>(new Set());
  const MAX_CHART_TRACES = 10000; // Max traces to keep for chart aggregation

  // View mode and pagination state
  const [viewMode, setViewMode] = useState<'traces' | 'flatten'>('traces');
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  // Reverse scroll refs (scroll to top to load more)
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const loadMoreTopRef = useRef<HTMLDivElement>(null);
  const prevScrollHeightRef = useRef<number>(0);
  const isPrependingRef = useRef<boolean>(false);

  // Drawer hook
  const { openDrawer } = useDrawer();

  // Handle incoming live trace data
  const handleLiveTrace = useCallback((trace: TraceSpan) => {
    // Validate required fields
    if (!trace || !trace.span_id) {
      console.warn('[LiveTrace] Invalid trace data - missing span_id:', trace);
      return;
    }

    // Add to chart traces using arrival time, not trace timestamp
    // This ensures live traces appear in the current time window
    // Subtract a small amount to ensure it falls within the bucket boundary
    const now = Date.now();
    const arrivalTime = now - 1; // 1ms before now to ensure it's within bucket
    const timeWindowMs = getTimeWindowMs(timeRange);
    const cutoffTime = now - timeWindowMs * 2;

    // Use arrival time for chart (when trace arrived), not original timestamp
    liveChartTracesRef.current.push({
      timestamp: arrivalTime,
      status: trace.status_code || 'ok',
      duration: (trace.duration ?? 0) / 1_000_000_000, // nanoseconds to seconds
    });
    liveChartTracesRef.current = liveChartTracesRef.current
      .filter(t => t.timestamp > cutoffTime)
      .slice(-MAX_CHART_TRACES);

    // In traces view, only show root spans (those with empty parent_span_id)
    if (viewMode === 'traces' && trace.parent_span_id && trace.parent_span_id !== '') {
      return;
    }

    // Deduplicate by span_id
    if (liveSpanIdsRef.current.has(trace.span_id)) {
      return;
    }
    liveSpanIdsRef.current.add(trace.span_id);

    // Transform to LogEntry and append to list (live data appears at the bottom)
    // Detect exception status
    const { hasException, errorType } = detectSpanException(trace);

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
      hasException,
      errorType,
    };

    setLogsData(prev => [...prev, newEntry].slice(-200));
  }, [viewMode, timeRange]);

  // Handle batch of live traces (for tree building in traces view)
  const handleLiveTraceBatch = useCallback((traces: TraceSpan[]) => {
    if (!traces || traces.length === 0) return;

    // Add all traces to chart data using arrival time
    const now = Date.now();
    const arrivalTime = now - 1; // 1ms before now to ensure it's within bucket
    const timeWindowMs = getTimeWindowMs(timeRange);
    const cutoffTime = now - timeWindowMs * 2;

    // Use arrival time for all traces in batch (when they arrived)
    traces.forEach(trace => {
      liveChartTracesRef.current.push({
        timestamp: arrivalTime,
        status: trace.status_code || 'ok',
        duration: (trace.duration ?? 0) / 1_000_000_000, // nanoseconds to seconds
      });
    });

    // Clean up old traces
    liveChartTracesRef.current = liveChartTracesRef.current
      .filter(t => t.timestamp > cutoffTime)
      .slice(-MAX_CHART_TRACES);

    if (viewMode === 'traces') {
      // In traces view, build proper tree structure from batch
      const newTrees = buildTreeFromLiveSpans(traces);
      if (newTrees.length === 0) return;

      // Track trace IDs for deduplication
      newTrees.forEach(tree => {
        if (tree.traceId) {
          liveSpanIdsRef.current.add(tree.traceId);
        }
      });

      // Merge with existing data (append new trees at the bottom, replace existing with same trace_id)
      setLogsData(prev => {
        const newTraceIds = new Set(newTrees.map(t => t.traceId));
        // Filter out existing trees with same trace_id (update scenario)
        const filteredPrev = prev.filter(p => !newTraceIds.has(p.traceId));
        return [...filteredPrev, ...newTrees];
      });
    } else {
      // In flatten view, process each span individually (existing behavior)
      traces.forEach(trace => {
        if (!trace || !trace.span_id) return;
        if (liveSpanIdsRef.current.has(trace.span_id)) return;
        liveSpanIdsRef.current.add(trace.span_id);

        // Detect exception status
        const { hasException, errorType } = detectSpanException(trace);

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
          hasException,
          errorType,
        };

        setLogsData(prev => [...prev, newEntry].slice(-200));
      });
    }
  }, [viewMode, timeRange]);

  // Socket hook for live streaming
  // Note: promptId (UUID) is used for socket subscription, promptName is used for API calls
  const { isSubscribed, connectionStatus, error: socketError } = useObservabilitySocket({
    projectId: projectId || '',
    promptId: promptId || '',
    enabled: isLive && !!projectId && !!promptId,
    onTraceBatchReceived: handleLiveTraceBatch,
    onTraceReceived: handleLiveTrace,
    onError: (err) => console.error('[LiveTrace] Socket error:', err),
  });

  const ITEMS_PER_PAGE = 20;
  const TRACES_PER_PAGE = 10;

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
      const { from_date, to_date } = getTimeRangeDates(timeRange, customDateRange);

      // Build params based on view mode
      const params: Record<string, any> = {
        project_id: projectId,
        from_date,
        to_date,
        limit: viewMode === 'flatten' ? ITEMS_PER_PAGE : TRACES_PER_PAGE,
        page: currentPage,
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
        setTotalRecord(total);

        // Find earliest timestamp for offset calculation
        const timestamps = spans.map((s: TraceSpan) => new Date(s.timestamp).getTime());
        const earliestTimestamp = Math.min(...timestamps);

        // Build data based on view mode
        let newData: LogEntry[];
        if (viewMode === 'flatten') {
          newData = buildFlatSpansList(spans, earliestTimestamp);
        } else {
          // Build list of root spans only (those with empty parent_span_id)
          newData = buildRootSpansList(spans, earliestTimestamp);
        }

        // Handle prepend vs replace for reverse infinite scroll (scroll to top to load more)
        if (loadMore) {
          if (scrollContainerRef.current) {
            prevScrollHeightRef.current = scrollContainerRef.current.scrollHeight;
            isPrependingRef.current = true;
          }
          setLogsData(prev => [...newData, ...prev]);
          setPage(currentPage);
        } else {
          setLogsData(newData);
        }

        // Update pagination state
        const perPage = viewMode === 'flatten' ? ITEMS_PER_PAGE : TRACES_PER_PAGE;
        setHasMore(currentPage * perPage < total);
      } else {
        if (!loadMore) {
          setLogsData([]);
        }
        setHasMore(false);
      }
    } catch (error) {
      console.error("Error fetching traces:", error);
      if (!loadMore) {
        setLogsData([]);
      }
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [promptName, projectId, timeRange, customDateRange, viewMode, page]);

  // Fetch traces when dependencies change (except page - that's handled by loadMore)
  useEffect(() => {
    fetchTraces();
  }, [promptName, projectId, timeRange, customDateRange, viewMode]);

  // Reset state when view mode changes
  useEffect(() => {
    setLogsData([]);
    setExpandedIds(new Set());
    setSelectedId(null);
    setPage(1);
    setHasMore(true);
    setIsAllExpanded(false);
  }, [viewMode]);

  // Reverse scroll observer - scroll to top to load more (both views)
  useEffect(() => {
    if (!loadMoreTopRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoadingMore && !isLoading) {
          fetchTraces(true);
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(loadMoreTopRef.current);
    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, isLoading, viewMode, fetchTraces]);

  // Preserve scroll position after prepending items
  useLayoutEffect(() => {
    if (isPrependingRef.current && scrollContainerRef.current) {
      const newScrollHeight = scrollContainerRef.current.scrollHeight;
      const addedHeight = newScrollHeight - prevScrollHeightRef.current;
      scrollContainerRef.current.scrollTop += addedHeight;
      isPrependingRef.current = false;
    }
  }, [logsData]);

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
      liveChartTracesRef.current = [];
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
        // Enabling live mode: keep existing data, seed dedup set with current span IDs
        liveSpanIdsRef.current.clear();
        logsData.forEach(log => {
          if (log.spanId) liveSpanIdsRef.current.add(log.spanId);
          if (log.traceId) liveSpanIdsRef.current.add(log.traceId);
        });
        liveChartTracesRef.current = [];
      } else {
        // Disabling live mode: clear live data and fetch regular traces
        setLogsData([]);
        liveSpanIdsRef.current.clear();
        liveChartTracesRef.current = [];
        setExpandedIds(new Set());
        setIsAllExpanded(false);
        setPage(1);
        setHasMore(true);
        // Fetch regular traces after state update
        setTimeout(() => fetchTraces(), 0);
      }
      return !prev;
    });
  };

  // Handle preset time range change - disables live mode if active
  const handlePresetChange = (newRange: string) => {
    if (isLive) {
      // Disable live mode and clear live data when changing time filter
      setIsLive(false);
      setLogsData([]);
      liveSpanIdsRef.current.clear();
      liveChartTracesRef.current = [];
    }
    setTimeRange(newRange);
    setCustomDateRange(null); // Clear custom range when preset is selected
  };

  // Handle custom date range change
  const handleCustomRangeChange = (startDate: Dayjs, endDate: Dayjs) => {
    if (isLive) {
      // Disable live mode and clear live data when changing time filter
      setIsLive(false);
      setLogsData([]);
      liveSpanIdsRef.current.clear();
      liveChartTracesRef.current = [];
    }
    setCustomDateRange([startDate, endDate]);
    setTimeRange(""); // Clear preset when custom range is selected
  };

  // Handle combined date range picker change
  const handleDateRangeChange = (value: DateRangeValue) => {
    if (value.preset) {
      handlePresetChange(value.preset);
    } else if (value.startDate && value.endDate) {
      handleCustomRangeChange(value.startDate, value.endDate);
    }
  };

  // Update chart - always regenerate buckets based on current time for scrolling effect
  const updateChartData = useCallback(() => {
    if (!chartInstanceRef.current) {
      console.log('[Chart] No chart instance');
      return;
    }

    const timeWindowMs = getTimeWindowMs(timeRange);
    const bucketSize = timeWindowMs / CHART_CONFIG.bucketCount;
    const now = Date.now();
    const windowStart = now - timeWindowMs;

    // Get traces to aggregate based on mode
    let tracesToAggregate: { timestamp: number; status?: string; duration?: number }[];
    if (isLive) {
      tracesToAggregate = liveChartTracesRef.current;
    } else {
      tracesToAggregate = logsData.map(log => ({
        timestamp: log.rawData?.timestamp ? new Date(log.rawData.timestamp).getTime() : Date.now(),
        status: log.rawData?.status_code || 'ok',
        duration: log.duration || 0,
      }));
    }

    // Debug logging
    console.log('[Chart Update] isLive:', isLive,
      '| traces:', tracesToAggregate.length,
      '| window:', new Date(windowStart).toLocaleTimeString(), '-', new Date(now).toLocaleTimeString());

    // If we have traces, check how many are in window
    if (tracesToAggregate.length > 0) {
      const inWindow = tracesToAggregate.filter(t => t.timestamp >= windowStart && t.timestamp <= now);
      console.log('[Chart Update] Traces in window:', inWindow.length, '/', tracesToAggregate.length);

      // Log first trace details if any
      if (tracesToAggregate.length > 0) {
        const firstTrace = tracesToAggregate[0];
        console.log('[Chart Update] First trace - timestamp:', firstTrace.timestamp,
          '| as date:', new Date(firstTrace.timestamp).toLocaleTimeString(),
          '| diff from now:', Math.round((now - firstTrace.timestamp) / 1000), 'seconds');
      }
    }

    // Generate buckets based on CURRENT time (this creates the scrolling effect)
    const labels: string[] = [];
    const successData: ExtendedBucketData[] = [];
    const errorData: ExtendedBucketData[] = [];
    let totalInBuckets = 0;

    for (let i = 0; i < CHART_CONFIG.bucketCount; i++) {
      const bucketStart = now - timeWindowMs + (i * bucketSize);
      const bucketEnd = bucketStart + bucketSize;

      // Format label based on time window
      const date = new Date(bucketEnd);
      let label: string;
      if (timeWindowMs <= ONE_HOUR_MS) {
        // <= 1 hour: show MM:SS
        label = date.toLocaleTimeString('en-US', { hour12: false, minute: '2-digit', second: '2-digit' });
      } else if (timeWindowMs <= 86400000) {
        // <= 24 hours: show HH:MM
        label = date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
      } else {
        // > 24 hours: show date
        label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      }
      labels.push(label);

      // Count traces in this bucket and calculate total duration
      const inBucket = tracesToAggregate.filter(t => t.timestamp >= bucketStart && t.timestamp < bucketEnd);
      const errorTraces = inBucket.filter(t => t.status === 'error' || t.status === 'ERROR');
      const successTraces = inBucket.filter(t => t.status !== 'error' && t.status !== 'ERROR');

      const successDuration = successTraces.reduce((sum, t) => sum + (t.duration || 0), 0);
      const errorDuration = errorTraces.reduce((sum, t) => sum + (t.duration || 0), 0);
      const totalDuration = successDuration + errorDuration;

      // In live mode, also add historical counts from time-series API
      let apiCount = 0;
      if (isLive && timeSeriesDataRef.current.length > 0) {
        apiCount = timeSeriesDataRef.current
          .filter(d => d.timestamp >= bucketStart && d.timestamp < bucketEnd)
          .reduce((sum, d) => sum + d.value, 0);
      }

      successData.push({
        value: successTraces.length + apiCount,
        bucketStart,
        bucketEnd,
        totalDuration,
      });
      errorData.push({
        value: errorTraces.length,
        bucketStart,
        bucketEnd,
        totalDuration,
      });
      totalInBuckets += inBucket.length;
    }

    // Log total traces that ended up in buckets
    if (tracesToAggregate.length > 0) {
      console.log('[Chart Update] Total in buckets:', totalInBuckets,
        '| successData:', successData.filter(x => x.value > 0).length, 'non-zero buckets');
    }

    // Calculate which labels to show (every Nth label for readability)
    const labelInterval = Math.ceil(CHART_CONFIG.bucketCount / 8);

    // Update chart with smooth animation
    chartInstanceRef.current.setOption({
      xAxis: {
        data: labels,
        axisLabel: {
          interval: (index: number) => index % labelInterval === 0,
        },
      },
      series: [
        { data: errorData },
        { data: successData },
      ],
    });
  }, [timeRange, isLive, logsData]);

  // Fetch chart data from time-series API
  // Stores data in ref for live mode merging; updates chart directly in non-live mode
  const fetchChartData = useCallback(async () => {
    if (!promptId) return;

    const { from_date, to_date } = getTimeRangeDates(timeRange, customDateRange);

    const response = await fetchPromptTimeSeries(
      from_date,
      to_date,
      [METRICS.requests],
      { prompt_id: [promptId] },
      { dataSource: "prompt", fillGaps: true }
    );

    if (response && response.groups && response.groups.length > 0) {
      const aggregatedData: Map<string, number> = new Map();

      response.groups.forEach((group) => {
        group.data_points.forEach((point) => {
          const timestamp = point.timestamp;
          const value = point.values[METRICS.requests] || 0;
          const existing = aggregatedData.get(timestamp) || 0;
          aggregatedData.set(timestamp, existing + value);
        });
      });

      const sortedEntries = Array.from(aggregatedData.entries()).sort(
        (a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime()
      );

      // Always store in ref for live mode merging
      timeSeriesDataRef.current = sortedEntries.map(([timestamp, value]) => ({
        timestamp: new Date(timestamp).getTime(),
        value,
      }));

      // Only update chart directly in non-live mode
      // In live mode, updateChartData handles chart rendering with merged data
      if (!isLive && chartInstanceRef.current) {
        const labels = sortedEntries.map(([timestamp]) => formatChartLabel(timestamp));

        const successData: ExtendedBucketData[] = sortedEntries.map(([timestamp, value], index) => {
          const currentTime = new Date(timestamp).getTime();
          const nextTime =
            index < sortedEntries.length - 1
              ? new Date(sortedEntries[index + 1][0]).getTime()
              : currentTime + ONE_HOUR_MS;
          return {
            value,
            bucketStart: currentTime,
            bucketEnd: nextTime,
            totalDuration: 0,
          };
        });

        const labelInterval = Math.max(1, Math.ceil(labels.length / 8));

        chartInstanceRef.current.setOption({
          xAxis: {
            data: labels,
            axisLabel: {
              interval: (index: number) => index % labelInterval === 0,
            },
          },
          series: [{ data: [] }, { data: successData }],
        });
      }
    } else {
      timeSeriesDataRef.current = [];
      if (!isLive && chartInstanceRef.current) {
        chartInstanceRef.current.setOption({
          xAxis: { data: [] },
          series: [{ data: [] }, { data: [] }],
        });
      }
    }
  }, [promptId, timeRange, customDateRange, isLive, fetchPromptTimeSeries, METRICS]);

  // Initialize echarts with stacked bar configuration
  useEffect(() => {
    if (!chartRef.current) return;

    const myChart = echarts.init(chartRef.current, null, {
      renderer: "canvas",
    });
    chartInstanceRef.current = myChart;

    const option = {
      backgroundColor: "transparent",
      grid: {
        left: "3%",
        right: "3%",
        bottom: "15%",
        top: "15%",
        containLabel: true,
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "rgba(24, 24, 27, 0.98)",
        borderColor: "#3f3f46",
        borderWidth: 1,
        padding: [12, 14],
        textStyle: { color: "#fafafa", fontSize: 12 },
        confine: true, // Keep tooltip within chart bounds
        extraCssText: 'box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);',
        formatter: function (params: any) {
          // Extract data from the series (Error is first, Success is second)
          const errorParam = params[0];
          const successParam = params[1];

          // Get extended bucket data (both series have the same bucket info)
          const bucketData = errorParam?.data as ExtendedBucketData;
          const bucketStart = bucketData?.bucketStart || Date.now();
          const bucketEnd = bucketData?.bucketEnd || Date.now();
          const totalDuration = bucketData?.totalDuration || 0;

          // Get counts (handle both number and object data formats)
          const error = typeof errorParam?.data === 'object' ? errorParam?.data?.value || 0 : errorParam?.value || 0;
          const success = typeof successParam?.data === 'object' ? successParam?.data?.value || 0 : successParam?.value || 0;
          const total = success + error;

          // Format timestamps
          const formatDateTime = (timestamp: number) => {
            const date = new Date(timestamp);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ', ' +
              date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
          };

          // Format duration
          const formatDurationTooltip = (seconds: number) => {
            if (seconds === 0) return '0s';
            if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
            if (seconds < 60) return `${seconds.toFixed(2)}s`;
            return `${(seconds / 60).toFixed(2)}m`;
          };

          // Calculate cursor point (middle of bucket)
          const cursorPoint = (bucketStart + bucketEnd) / 2;

          return `
            <div style="min-width: 200px;">
              <table style="border-collapse: collapse; width: 100%; font-size: 12px;">
                <tr>
                  <td style="color: #71717a; padding: 2px 12px 2px 0; white-space: nowrap;">Cursor point</td>
                  <td style="color: #fafafa; font-family: monospace; text-align: right;">${formatDateTime(cursorPoint)}</td>
                </tr>
                <tr>
                  <td style="color: #71717a; padding: 2px 12px 2px 0; white-space: nowrap;">Bar period</td>
                  <td style="color: #fafafa; font-family: monospace; text-align: right; font-size: 11px;">
                    ${formatDateTime(bucketStart)} -<br/>${formatDateTime(bucketEnd)}
                  </td>
                </tr>
                <tr>
                  <td style="color: #71717a; padding: 2px 12px 2px 0; white-space: nowrap;">Count</td>
                  <td style="color: #fafafa; text-align: right;">${total}</td>
                </tr>
                <tr>
                  <td style="color: #71717a; padding: 2px 12px 2px 0; white-space: nowrap;">Duration</td>
                  <td style="color: #fafafa; text-align: right;">${formatDurationTooltip(totalDuration)}</td>
                </tr>
              </table>
              ${total > 0 ? `
              <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #27272a;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                  <span style="display: flex; align-items: center; gap: 6px; color: #a1a1aa;">
                    <span style="display: inline-block; width: 8px; height: 8px; background: #965CDE; border-radius: 2px;"></span>
                    Success
                  </span>
                  <span style="font-weight: 500; color: #fafafa;">${success}</span>
                </div>
                ${error > 0 ? `
                <div style="display: flex; justify-content: space-between;">
                  <span style="display: flex; align-items: center; gap: 6px; color: #a1a1aa;">
                    <span style="display: inline-block; width: 8px; height: 8px; background: #ef4444; border-radius: 2px;"></span>
                    Errors
                  </span>
                  <span style="font-weight: 500; color: #fafafa;">${error}</span>
                </div>
                ` : ''}
              </div>
              ` : ''}

            </div>
          `;
        },
      },
      xAxis: {
        type: "category",
        data: [],
        axisLine: { lineStyle: { color: "#3f3f46" } },
        axisTick: { show: false },
        axisLabel: {
          color: "#71717a",
          fontSize: 10,
          interval: 0,
        },
        // Smooth animation for x-axis scrolling
        animation: true,
      },
      yAxis: {
        type: "value",
        min: 0,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: {
          lineStyle: { color: "#3D3D3D", type: "solid" },
        },
        axisLabel: {
          color: "#71717a",
          fontSize: 10,
        },
        minInterval: 1,
      },
      series: [
        {
          name: "Error",
          type: "bar",
          stack: "total",
          data: [],
          itemStyle: {
            color: "#ef4444",
            borderRadius: [0, 0, 0, 0],
          },
          emphasis: {
            itemStyle: { color: "#f87171" },
          },
          barWidth: "52%",
          animationDuration: 300,
          animationEasing: "linear" as const,
        },
        {
          name: "Success",
          type: "bar",
          stack: "total",
          data: [],
          itemStyle: {
            color: "#965CDE",
            borderRadius: [2, 2, 0, 0],
          },
          emphasis: {
            itemStyle: { color: "#a78bfa" },
          },
          barWidth: "52%",
          animationDuration: 300,
          animationEasing: "linear" as const,
        },
      ],
      // Global animation settings for smooth scrolling effect
      animation: true,
      animationDuration: 300,
      animationDurationUpdate: 300,
      animationEasing: "linear" as const,
      animationEasingUpdate: "linear" as const,
    };

    myChart.setOption(option);

    const handleResize = () => myChart.resize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      myChart.dispose();
      chartInstanceRef.current = null;
    };
  }, []);

  // <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #27272a; font-size: 11px;">
  //               <div style="display: flex; align-items: center; gap: 8px; color: #71717a; margin-bottom: 4px;">
  //                 <span style="color: #965CDE;">&#8857;</span>
  //                 <span><strong style="color: #a1a1aa;">Double click:</strong> Jump to time</span>
  //               </div>
  //               <div style="display: flex; align-items: center; gap: 8px; color: #71717a; margin-bottom: 4px;">
  //                 <span style="color: #965CDE;">&#8644;</span>
  //                 <span><strong style="color: #a1a1aa;">Drag area:</strong> Change active range</span>
  //               </div>
  //               <div style="display: flex; align-items: center; gap: 8px; color: #71717a;">
  //                 <span style="color: #965CDE;">&#9711;</span>
  //                 <span><strong style="color: #a1a1aa;">Scroll:</strong> Zoom in/out active range</span>
  //               </div>
  //             </div>

  // Set up chart update: always fetch time-series data, plus live interval when live
  useEffect(() => {
    // Clear existing interval
    if (chartUpdateIntervalRef.current) {
      clearInterval(chartUpdateIntervalRef.current);
    }

    // Always fetch time-series API data (populates ref for live merging, updates chart in non-live)
    fetchChartData();

    if (isLive) {
      // In live mode, also run interval to merge API data + live traces
      updateChartData();
      chartUpdateIntervalRef.current = setInterval(() => {
        updateChartData();
      }, CHART_CONFIG.updateInterval);
    }

    return () => {
      if (chartUpdateIntervalRef.current) {
        clearInterval(chartUpdateIntervalRef.current);
        chartUpdateIntervalRef.current = null;
      }
    };
  }, [isLive, timeRange, customDateRange, updateChartData, fetchChartData]);

  // Get time range label for display
  const getTimeRangeLabel = () => {
    if (customDateRange) {
      const [start, end] = customDateRange;
      return `${start.format("MMM D")} - ${end.format("MMM D")}`;
    }
    const preset = PRESET_OPTIONS.find((o) => o.value === timeRange);
    return preset?.label?.replace("Last ", "") || "5 minutes";
  };

  return (
    <div className="px-[3.5rem] pb-8">
      {/* Header */}
      {/* <div className="mb-6">
        <Text_26_600_FFFFFF className="block mb-2">Logs</Text_26_600_FFFFFF>
        <Text_12_400_B3B3B3 className="max-w-[850px]">
          View OpenTelemetry traces and spans for this prompt. Monitor request
          flow, performance metrics, and debug issues across your AI pipeline.
        </Text_12_400_B3B3B3>
      </div> */}

      {/* Chart Section */}
      {/* <div className="bg-[#101010] border border-[#1F1F1F]  p-4 mb-4 mt-4"> */}
      <div className=" border-0 border-[#1F1F1F]  p-3 mt-4">
        {/* Chart Controls */}
        <div className="flex justify-end items-center gap-2 mb-2">
          <LogfireDateRangePicker
            value={
              customDateRange
                ? { startDate: customDateRange[0], endDate: customDateRange[1] }
                : { preset: timeRange || "5m" }
            }
            onChange={handleDateRangeChange}
          />
          <div className="flex items-center border border-[#3a3a3a] rounded-md overflow-hidden max-h-[1.6rem]">
            <button
              className={`p-[.4rem] border-r border-[#3a3a3a] transition-colors ${viewMode === 'traces'
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
              className={`p-[.4rem] transition-colors ${viewMode === 'flatten'
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
        <div ref={chartRef} className="w-full h-[130px] 1680px:h-[200px] 1920px:h-[270px] 2048px:h-[350px] 2560px:h-[450px]" />
      </div>

      {/* Logs List Section */}
      <div className=" border border-[#1F1F1F]  overflow-hidden">
        {/* List Header */}
        <div className="px-4 py-3 pb-[1rem] border-b border-[#1F1F1F] flex justify-between items-center">
          <Text_12_400_B3B3B3>
            {isLoading
              ? "Loading traces..."
              : `Showing ${totalRecord} records from the last ${getTimeRangeLabel()}`}
          </Text_12_400_B3B3B3>
          <div className="flex items-center gap-4">
            {/* Expand/Collapse button - only show in traces view */}
            {viewMode === 'traces' && (
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
            )}

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
          <div ref={scrollContainerRef} className="max-h-[calc(100vh-400px)] min-h-[300px] overflow-auto">
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
                {/* Reverse scroll trigger - scroll to top to load more */}
                <div ref={loadMoreTopRef} className="h-4">
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
                {/* Reverse scroll trigger - scroll to top to load more */}
                <div ref={loadMoreTopRef} className="h-4">
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
                {/* Flatten view - flat list of all spans sorted chronologically */}
                {(() => {
                  // Calculate max duration once for all rows (memoized within render)
                  const maxDuration = Math.max(...logsData.map(l => l.duration), 1);
                  return logsData.map((log) => (
                    <FlatLogRow
                      key={log.id}
                      row={log}
                      referenceDuration={maxDuration}
                      isSelected={selectedId === log.id}
                      onSelect={() => setSelectedId(log.id)}
                      onViewDetails={openLogDetailsDrawer}
                    />
                  ));
                })()}
              </div>
            )}
          </div>
        </div>
      </div>

    </div>
  );
};

export default LogsTab;
