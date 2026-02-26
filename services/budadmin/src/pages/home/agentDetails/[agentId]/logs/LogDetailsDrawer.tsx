import React, { useState, useMemo, useEffect, useCallback } from "react";
import { Tabs, Spin, Tooltip } from "antd";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_10_400_B3B3B3,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_14_400_EEEEEE,
  Text_16_400_EEEEEE,
} from "@/components/ui/text";
import { useDrawer } from "src/hooks/useDrawer";
import { AppRequest } from "src/pages/api/requests";
import { DrawerLogTree, DrawerLogEntry } from "./components/DrawerLogTree";
import Tags from "src/flows/components/DrawerTags";

// Types
interface SpanData {
  id: string;
  time: string;
  status: string;
  title: string;
  duration: number;
  traceId?: string;
  spanId?: string;
  parentSpanId?: string;
  metrics?: {
    tag?: string;
  };
  rawData?: Record<string, any>;
}

interface TraceSpan {
  timestamp: string;
  trace_id: string;
  span_id: string;
  parent_span_id: string;
  span_name: string;
  span_kind: string;
  service_name: string;
  resource_attributes: Record<string, string>;
  scope_name: string;
  span_attributes: Record<string, any>;
  duration?: number;
  child_span_count?: number;
}



// JSON Tree View Component for expandable JSON display (Logfire-style)
const JsonTreeView = ({
  data,
  depth = 0,
  keyName,
  isLast = true,
}: {
  data: any;
  depth?: number;
  keyName?: string;
  isLast?: boolean;
}) => {
  const [isExpanded, setIsExpanded] = useState(depth < 2);

  const INDENT_SIZE = 20;
  const LINE_HEIGHT = 22;
  const FONT_SIZE = "0.75rem";

  const renderIndentLines = (currentDepth: number) => {
    const lines = [];
    for (let i = 0; i < currentDepth; i++) {
      lines.push(
        <div
          key={i}
          className="absolute top-0 bottom-0 w-px bg-[#3a3a3a]"
          style={{ left: `${i * INDENT_SIZE + 8}px` }}
        />
      );
    }
    return lines;
  };

  const RowWrapper = ({
    children,
    clickable = false,
    onClick,
  }: {
    children: React.ReactNode;
    clickable?: boolean;
    onClick?: () => void;
  }) => (
    <div
      className={`relative ${clickable ? "cursor-pointer hover:bg-[rgba(255,255,255,0.03)]" : ""}`}
      style={{ minHeight: `${LINE_HEIGHT}px`, lineHeight: `${LINE_HEIGHT}px`, fontSize: FONT_SIZE }}
      onClick={onClick}
    >
      {renderIndentLines(depth)}
      <div
        style={{ paddingLeft: `${depth * INDENT_SIZE}px` }}
      >
        {children}
      </div>
    </div>
  );

  const renderKey = (key: string) => (
    <span className="text-[#abb2bf]">"{key}"</span>
  );

  const renderColon = () => <span className="text-[#EEEEEE]">: </span>;

  const renderComma = () =>
    !isLast ? <span className="text-[#EEEEEE]">,</span> : null;

  if (data === null) {
    return (
      <RowWrapper>
        {keyName && (
          <>
            {renderKey(keyName)}
            {renderColon()}
          </>
        )}
        <span className="text-[#98c379]">null</span>
        {renderComma()}
      </RowWrapper>
    );
  }

  if (typeof data === "boolean") {
    return (
      <RowWrapper>
        {keyName && (
          <>
            {renderKey(keyName)}
            {renderColon()}
          </>
        )}
        <span className="text-[#98c379]">{data.toString()}</span>
        {renderComma()}
      </RowWrapper>
    );
  }

  if (typeof data === "number") {
    return (
      <RowWrapper>
        {keyName && (
          <>
            {renderKey(keyName)}
            {renderColon()}
          </>
        )}
        <span className="text-[#EEEEEE]">{data}</span>
        {renderComma()}
      </RowWrapper>
    );
  }

  if (typeof data === "string") {
    return (
      <RowWrapper>
        {keyName && (
          <>
            {renderKey(keyName)}
            {renderColon()}
          </>
        )}
        <span className="text-[#98c379]">"{data}"</span>
        {renderComma()}
      </RowWrapper>
    );
  }

  if (Array.isArray(data)) {
    const itemCount = data.length;
    const itemLabel = itemCount === 1 ? "item" : "items";

    return (
      <div>
        <RowWrapper clickable onClick={() => setIsExpanded(!isExpanded)}>
          <span className="text-[#757575] w-4 flex-shrink-0 select-none">
            {isExpanded ? "▾" : "▸"}
          </span>
          {keyName && (
            <>
              {renderKey(keyName)}
              {renderColon()}
            </>
          )}
          <span className="text-[#EEEEEE]">[</span>
          <span className="text-[#757575] ml-1 italic">
            {itemCount} {itemLabel}
          </span>
          {!isExpanded && (
            <>
              <span className="text-[#EEEEEE]">]</span>
              {renderComma()}
            </>
          )}
        </RowWrapper>

        {isExpanded && (
          <>
            {data.map((item, index) => (
              <JsonTreeView
                key={index}
                data={item}
                depth={depth + 1}
                keyName={String(index)}
                isLast={index === data.length - 1}
              />
            ))}
            <RowWrapper>
              <span className="w-4 flex-shrink-0" />
              <span className="text-[#EEEEEE]">]</span>
              {renderComma()}
            </RowWrapper>
          </>
        )}
      </div>
    );
  }

  if (typeof data === "object") {
    const keys = Object.keys(data);
    const itemCount = keys.length;
    const itemLabel = itemCount === 1 ? "item" : "items";

    return (
      <div>
        <RowWrapper clickable onClick={() => setIsExpanded(!isExpanded)}>
          <span className="text-[#757575] w-4 flex-shrink-0 select-none">
            {isExpanded ? "▾" : "▸"}
          </span>
          {keyName && (
            <>
              {renderKey(keyName)}
              {renderColon()}
            </>
          )}
          <span className="text-[#EEEEEE]">{"{"}</span>
          <span className="text-[#757575] ml-1 italic">
            {itemCount} {itemLabel}
          </span>
          {!isExpanded && (
            <>
              <span className="text-[#EEEEEE]">{"}"}</span>
              {renderComma()}
            </>
          )}
        </RowWrapper>

        {isExpanded && (
          <>
            {keys.map((key, index) => (
              <JsonTreeView
                key={key}
                data={data[key]}
                depth={depth + 1}
                keyName={key}
                isLast={index === keys.length - 1}
              />
            ))}
            <RowWrapper>
              <span className="w-4 flex-shrink-0" />
              <span className="text-[#EEEEEE]">{"}"}</span>
              {renderComma()}
            </RowWrapper>
          </>
        )}
      </div>
    );
  }

  return null;
};

// Format time for display
const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};

// Build trace tree from flat spans
const buildTraceTree = (spans: TraceSpan[]): DrawerLogEntry[] => {
  if (!spans || spans.length === 0) return [];

  // Create a map of span_id to DrawerLogEntry
  const nodeMap = new Map<string, DrawerLogEntry>();
  const spanDataMap = new Map<string, TraceSpan>();

  // First pass: create all nodes
  spans.forEach((span) => {
    spanDataMap.set(span.span_id, span);
    const node: DrawerLogEntry = {
      id: span.span_id,
      time: formatTime(span.timestamp),
      namespace: span.resource_attributes?.["service.name"] || "",
      title: span.span_name,
      serviceName: span.service_name,
      duration: (span.duration ?? 0) / 1_000_000_000,
      childCount: span.child_span_count,
      children: [],
      rawData: span as unknown as Record<string, any>,
    };
    nodeMap.set(span.span_id, node);
  });

  // Second pass: build parent-child relationships
  const rootNodes: DrawerLogEntry[] = [];

  spans.forEach((span) => {
    const node = nodeMap.get(span.span_id);
    if (!node) return;

    if (!span.parent_span_id || span.parent_span_id === "") {
      // Root node
      rootNodes.push(node);
    } else if (nodeMap.has(span.parent_span_id)) {
      // Child of another node
      const parent = nodeMap.get(span.parent_span_id)!;
      parent.children = parent.children || [];
      parent.children.push(node);
    } else {
      // Parent not in this trace, treat as root
      rootNodes.push(node);
    }
  });

  // Sort children by timestamp
  const sortChildren = (node: DrawerLogEntry) => {
    if (node.children && node.children.length > 0) {
      const getTimestamp = (n: DrawerLogEntry) => {
        const span = spanDataMap.get(n.id);
        return span ? new Date(span.timestamp).getTime() : 0;
      };
      node.children.sort((a, b) => getTimestamp(a) - getTimestamp(b));
      node.children.forEach(sortChildren);
    }
  };

  rootNodes.forEach(sortChildren);
  rootNodes.sort((a, b) => {
    const spanA = spanDataMap.get(a.id);
    const spanB = spanDataMap.get(b.id);
    return (spanA ? new Date(spanA.timestamp).getTime() : 0) - (spanB ? new Date(spanB.timestamp).getTime() : 0);
  });

  return rootNodes;
};

// Get all node IDs up to a certain depth for initial expansion
const getExpandedIdsToDepth = (nodes: DrawerLogEntry[], maxDepth: number, currentDepth = 0): Set<string> => {
  const ids = new Set<string>();
  if (currentDepth >= maxDepth) return ids;

  nodes.forEach((node) => {
    if (node.children && node.children.length > 0) {
      ids.add(node.id);
      const childIds = getExpandedIdsToDepth(node.children, maxDepth, currentDepth + 1);
      childIds.forEach((id) => ids.add(id));
    }
  });

  return ids;
};

// Full Trace Section Component
const FullTraceSection = ({
  traceId,
  promptName,
  projectId,
  selectedSpanId,
  onSpanSelect,
}: {
  traceId: string;
  promptName: string;
  projectId: string;
  selectedSpanId: string;
  onSpanSelect: (node: DrawerLogEntry) => void;
}) => {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [traceTree, setTraceTree] = useState<DrawerLogEntry[]>([]);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Fetch full trace data
  useEffect(() => {
    const fetchTrace = async () => {
      if (!traceId || !promptName || !projectId) return;

      setIsLoading(true);
      setError(null);

      try {
        const response: any = await AppRequest.Get(
          `/prompts/${promptName}/traces/${traceId}`,
          {
            params: { project_id: projectId },
          }
        );

        if (response.data?.spans && response.data.spans.length > 0) {
          const tree = buildTraceTree(response.data.spans);
          setTraceTree(tree);
          // Auto-expand first 2 levels
          const initialExpanded = getExpandedIdsToDepth(tree, 2);
          setExpandedIds(initialExpanded);
        } else {
          setError("No trace data found");
        }
      } catch (err: any) {
        console.error("Error fetching trace:", err);
        setError(err?.message || "Failed to fetch trace");
      } finally {
        setIsLoading(false);
      }
    };

    fetchTrace();
  }, [traceId, promptName, projectId]);

  const handleToggleExpand = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  if (isCollapsed) {
    return (
      <div className="mt-4">
        <div
          className="flex items-center gap-2 cursor-pointer py-2 px-4 bg-[#0a0a0a] border border-[#1F1F1F] rounded-lg"
          onClick={() => setIsCollapsed(false)}
        >
          <span className="text-[#757575]">▸</span>
          <Text_14_400_EEEEEE className="font-semibold">Full Trace</Text_14_400_EEEEEE>
          <Text_12_400_757575>({traceTree.length > 0 ? `${traceTree.length} root spans` : "loading..."})</Text_12_400_757575>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-4">
      <div
        className="flex items-center gap-2 cursor-pointer py-2 px-4 bg-[#0a0a0a] border border-[#1F1F1F] rounded-t-lg border-b-0"
        onClick={() => setIsCollapsed(true)}
      >
        <span className="text-[#757575]">▾</span>
        <Text_14_400_EEEEEE className="font-semibold">Full Trace</Text_14_400_EEEEEE>
      </div>

      <div className="bg-[#0a0a0a] border border-[#1F1F1F] rounded-b-lg max-h-[300px] overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Spin size="small" />
            <Text_12_400_757575 className="ml-2">Loading trace...</Text_12_400_757575>
          </div>
        ) : error ? (
          <div className="text-center py-8">
            <Text_12_400_757575>{error}</Text_12_400_757575>
          </div>
        ) : traceTree.length === 0 ? (
          <div className="text-center py-8">
            <Text_12_400_757575>No spans found in trace</Text_12_400_757575>
          </div>
        ) : (
          <div className="py-1">
            <DrawerLogTree
              nodes={traceTree}
              selectedId={selectedSpanId}
              expandedIds={expandedIds}
              onToggleExpand={handleToggleExpand}
              onSelect={onSpanSelect}
            />
          </div>
        )}
      </div>
    </div>
  );
};

// Details Tab Content
const DetailsTabContent = ({ spanData }: { spanData: SpanData }) => {
  const [copied, setCopied] = useState(false);
  const attributes = spanData.rawData?.span_attributes || {};
  const resourceAttributes = spanData.rawData?.resource_attributes || {};

  const codeFilepath = attributes["code.filepath"];
  const codeFunction = attributes["code.function"];
  const codeLineno = attributes["code.lineno"];
  const gatewayPath = attributes["gateway_analytics.path"];

  const handleCopyPath = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (gatewayPath) {
      navigator.clipboard.writeText(gatewayPath);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Gateway Path - Copy Option */}
      {gatewayPath && (
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-1 py-[.2rem]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <span className="text-xs flex-shrink-0">🔗</span>
              <Text_12_400_EEEEEE className="truncate">{gatewayPath}</Text_12_400_EEEEEE>
            </div>
            <button
              type="button"
              onClick={handleCopyPath}
              className="flex items-center gap-1 px-2 py-1 ml-2 rounded bg-[#2a2a2a] hover:bg-[#3a3a3a] transition-colors flex-shrink-0"
            >
              {copied ? (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#98C379" strokeWidth="2">
                    <polyline points="20,6 9,17 4,12" />
                  </svg>
                  <span className="text-[#98C379] text-[.5rem]">Copied</span>
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#B3B3B3" strokeWidth="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5,15H4A2,2,0,0,1,2,13V4A2,2,0,0,1,4,2H13A2,2,0,0,1,15,4V5" />
                  </svg>
                  {/* <span className="text-[#B3B3B3] text-xs">Copy Path</span> */}
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Code File Path */}
      {(codeFilepath || codeFunction) && (
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">📄</span>
            <Text_12_400_EEEEEE>
              {codeFilepath}
              {codeLineno && `:${codeLineno}`}
            </Text_12_400_EEEEEE>
            {codeFunction && (
              <>
                <span className="text-[#757575]">in</span>
                <Text_14_400_EEEEEE className="text-[#98C379]">
                  {codeFunction}
                </Text_14_400_EEEEEE>
              </>
            )}
          </div>
        </div>
      )}

      {Object.keys(attributes).length > 0 && (
        <div>
          <Text_16_400_EEEEEE className="mb-3 block font-semibold">Span Attributes</Text_16_400_EEEEEE>
          <div className="bg-[#0a0a0a] border border-[#1F1F1F] rounded-lg p-4 font-mono text-sm overflow-x-auto">
            <JsonTreeView data={attributes} />
          </div>
        </div>
      )}

      {Object.keys(resourceAttributes).length > 0 && (
        <div>
          <Text_16_400_EEEEEE className="mb-3 block font-semibold">Resource Attributes</Text_16_400_EEEEEE>
          <div className="bg-[#0a0a0a] border border-[#1F1F1F] rounded-lg p-4 font-mono text-sm overflow-x-auto">
            <JsonTreeView data={resourceAttributes} />
          </div>
        </div>
      )}

      {Object.keys(attributes).length === 0 && Object.keys(resourceAttributes).length === 0 && (
        <div className="text-center py-8">
          <Text_12_400_757575>No attributes available for this span</Text_12_400_757575>
        </div>
      )}
    </div>
  );
};

// Raw Data Tab Content
const RawDataTabContent = ({ spanData }: { spanData: SpanData }) => {
  const rawData = spanData.rawData || {};

  return (
    <div>
      <div className="bg-[#0a0a0a] border border-[#1F1F1F] rounded-lg p-4 font-mono text-sm overflow-x-auto">
        <JsonTreeView data={rawData} />
      </div>
    </div>
  );
};

// Format duration for display (header)
const formatDurationDisplay = (seconds: number): string => {
  if (seconds >= 60) {
    return `${(seconds / 60).toFixed(2)}m`;
  }
  return `${seconds.toFixed(2)}s`;
};

export default function LogDetailsDrawer() {
  const { closeDrawer, drawerProps } = useDrawer();
  const initialSpanData: SpanData | null = drawerProps?.spanData || null;
  const viewMode: string = drawerProps?.viewMode || "traces";
  const promptName: string = drawerProps?.promptName || "";
  const projectId: string = drawerProps?.projectId || "";

  const [activeTab, setActiveTab] = useState("details");
  const [currentSpanData, setCurrentSpanData] = useState<SpanData | null>(initialSpanData);
  const [spanLinkCopied, setSpanLinkCopied] = useState(false);

  // Reset current span data when drawer opens with new data
  useEffect(() => {
    setCurrentSpanData(initialSpanData);
  }, [initialSpanData]);

  // Copy span link handler
  const handleCopySpanLink = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (currentSpanData?.traceId) {
      const currentUrl = new URL(window.location.href);
      currentUrl.searchParams.set("trace_id", currentSpanData.traceId);
      navigator.clipboard.writeText(currentUrl.toString());
      setSpanLinkCopied(true);
      setTimeout(() => setSpanLinkCopied(false), 2000);
    }
  }, [currentSpanData?.traceId]);

  // Handle span selection from Full Trace tree
  const handleSpanSelect = useCallback((node: DrawerLogEntry) => {
    // Convert DrawerLogEntry to SpanData format
    const newSpanData: SpanData = {
      id: node.id,
      time: node.time,
      status: node.rawData?.span_kind || "",
      title: node.title,
      duration: node.duration,
      traceId: node.rawData?.trace_id,
      spanId: node.rawData?.span_id,
      parentSpanId: node.rawData?.parent_span_id,
      metrics: {
        tag: node.serviceName,
      },
      rawData: node.rawData,
    };
    setCurrentSpanData(newSpanData);
  }, []);

  // Build metadata tags
  const metadataTags = useMemo(() => {
    if (!currentSpanData) return [];

    const tags: { label: string; value: string; fullValue?: string }[] = [];

    if (currentSpanData.title) {
      tags.push({ label: "span_name", value: currentSpanData.title });
    }
    if (currentSpanData.metrics?.tag) {
      tags.push({ label: "service_name", value: currentSpanData.metrics.tag });
    }
    if (currentSpanData.rawData?.scope_name) {
      tags.push({ label: "otel_scope_name", value: currentSpanData.rawData.scope_name });
    }
    if (currentSpanData.rawData?.span_kind) {
      tags.push({ label: "kind", value: currentSpanData.rawData.span_kind });
    }
    if (currentSpanData.traceId) {
      tags.push({ label: "trace_id", value: `...${currentSpanData.traceId.slice(-6)}`, fullValue: currentSpanData.traceId });
    }
    if (currentSpanData.spanId) {
      tags.push({ label: "span_id", value: `...${currentSpanData.spanId.slice(-6)}`, fullValue: currentSpanData.spanId });
    }

    return tags;
  }, [currentSpanData]);

  if (!currentSpanData) return null;

  const tabItems = [
    {
      key: "details",
      label: "Details",
      children: <DetailsTabContent spanData={currentSpanData} />,
    },
    {
      key: "rawData",
      label: "Raw Data",
      children: <RawDataTabContent spanData={currentSpanData} />,
    },
  ];

  const showFullTrace = viewMode === "flatten" && currentSpanData.traceId && promptName && projectId;

  return (
    <BudForm
      data={{}}
      onBack={() => closeDrawer()}
      showMinimizeButton={false}
    >
      <BudWraperBox classNames="mt-[2.2rem]">
        <BudDrawerLayout>
          {/* Header Section */}
          <div className="flex flex-col items-start justify-start w-full px-[1.4rem] py-[1.05rem] pb-[1.4rem] border-b-[.5px] border-b-[#1F1F1F]">
            {/* Top row with status and copy button */}
            <div className="flex justify-between items-center w-full">
              <div className="max-w-[90%]">
                <Text_16_400_EEEEEE className="mb-4 font-semibold w-full truncate">{currentSpanData.title}</Text_16_400_EEEEEE>
              </div>
              <div className="flex items-center justify-between w-full mb-2">
                <Text_10_400_B3B3B3>{currentSpanData.status}</Text_10_400_B3B3B3>
                {currentSpanData.traceId && (
                  <Tooltip title={spanLinkCopied ? "Copied!" : "Copy span link"} placement="left">
                    <button
                      type="button"
                      onClick={handleCopySpanLink}
                      className="flex items-center justify-center w-7 h-7 rounded bg-[#2a2a2a] hover:bg-[#3a3a3a] transition-colors"
                    >
                      {spanLinkCopied ? (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#98C379" strokeWidth="2">
                          <polyline points="20,6 9,17 4,12" />
                        </svg>
                      ) : (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#B3B3B3" strokeWidth="2">
                          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                        </svg>
                      )}
                    </button>
                  </Tooltip>
                )}
              </div>
            </div>

            {/* Metadata Tags */}
            <div className="flex flex-wrap gap-2 mb-4">
              {metadataTags.map((tag, index) => (
                <Tags
                  key={index}
                  copyText={`${tag.label}: ${tag.fullValue ?? tag.value}`}
                  onTagClick={() => {}}
                  showTooltip
                  tooltipText="Copy"
                  name={
                    <>
                      <span className="text-[#757575]">{tag.label}</span>{" "}
                      <span className="text-[#EEEEEE]">{tag.value}</span>
                    </>
                  }
                  color="#B3B3B3"
                  classNames="rounded-full px-3 py-1"
                />
              ))}
            </div>

            {/* Duration info */}
            <div className="flex items-center gap-2 text-[#B3B3B3]">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12,6 12,12 16,14" />
              </svg>
              <Text_12_400_B3B3B3>
                Span took {formatDurationDisplay(currentSpanData.duration)} at {currentSpanData.time}
              </Text_12_400_B3B3B3>
            </div>
          </div>

          {/* Tabs Content */}
          <div className="flex-1 overflow-auto px-[1.4rem] py-4">
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              items={tabItems}
              className="log-details-tabs"
            />

            {/* Full Trace Section - only shown in flatten view */}
            {showFullTrace && (
              <FullTraceSection
                traceId={currentSpanData.traceId!}
                promptName={promptName}
                projectId={projectId}
                selectedSpanId={currentSpanData.spanId || currentSpanData.id}
                onSpanSelect={handleSpanSelect}
              />
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
