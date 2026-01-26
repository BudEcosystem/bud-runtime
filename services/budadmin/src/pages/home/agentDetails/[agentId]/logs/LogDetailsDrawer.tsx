import React, { useState, useMemo } from "react";
import { Tabs, Tag } from "antd";
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

  const INDENT_SIZE = 20; // pixels per indent level
  const LINE_HEIGHT = 24; // line height in pixels

  // Render the vertical guide lines for indentation
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

  // Common row wrapper with indent lines
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
      className={`relative flex items-start ${clickable ? "cursor-pointer hover:bg-[rgba(255,255,255,0.03)]" : ""}`}
      style={{ minHeight: `${LINE_HEIGHT}px`, lineHeight: `${LINE_HEIGHT}px` }}
      onClick={onClick}
    >
      {renderIndentLines(depth)}
      <div
        className="flex items-start flex-1"
        style={{ paddingLeft: `${depth * INDENT_SIZE}px` }}
      >
        {children}
      </div>
    </div>
  );

  // Render key with quotes
  const renderKey = (key: string) => (
    <span className="text-[#abb2bf]">"{key}"</span>
  );

  // Render colon separator
  const renderColon = () => <span className="text-[#EEEEEE]">: </span>;

  // Render comma (if not last item)
  const renderComma = () =>
    !isLast ? <span className="text-[#EEEEEE]">,</span> : null;

  // Null value
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
        {/* <span className="text-[#6B9BD2]">null</span> */}
        {renderComma()}
      </RowWrapper>
    );
  }

  // Boolean value
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

  // Number value
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

  // String value
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

  // Array
  if (Array.isArray(data)) {
    const itemCount = data.length;
    const itemLabel = itemCount === 1 ? "item" : "items";

    return (
      <div>
        {/* Header row with chevron and opening bracket */}
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

        {/* Expanded content */}
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
            {/* Closing bracket */}
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

  // Object
  if (typeof data === "object") {
    const keys = Object.keys(data);
    const itemCount = keys.length;
    const itemLabel = itemCount === 1 ? "item" : "items";

    return (
      <div>
        {/* Header row with chevron and opening brace */}
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

        {/* Expanded content */}
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
            {/* Closing brace */}
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

// Details Tab Content
const DetailsTabContent = ({ spanData }: { spanData: SpanData }) => {
  const attributes = spanData.rawData?.span_attributes || {};
  const resourceAttributes = spanData.rawData?.resource_attributes || {};

  const codeFilepath = attributes["code.filepath"];
  const codeFunction = attributes["code.function"];
  const codeLineno = attributes["code.lineno"];

  return (
    <div className="space-y-6">
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

// Format duration for display
const formatDurationDisplay = (seconds: number): string => {
  if (seconds >= 60) {
    return `${(seconds / 60).toFixed(2)}m`;
  }
  return `${seconds.toFixed(2)}s`;
};

export default function LogDetailsDrawer() {
  const { closeDrawer, drawerProps } = useDrawer();
  const spanData: SpanData | null = drawerProps?.spanData || null;
  const [activeTab, setActiveTab] = useState("details");

  // Build metadata tags
  const metadataTags = useMemo(() => {
    if (!spanData) return [];

    const tags: { label: string; value: string }[] = [];

    if (spanData.title) {
      tags.push({ label: "span_name", value: spanData.title });
    }
    if (spanData.metrics?.tag) {
      tags.push({ label: "service_name", value: spanData.metrics.tag });
    }
    if (spanData.rawData?.scope_name) {
      tags.push({ label: "otel_scope_name", value: spanData.rawData.scope_name });
    }
    if (spanData.rawData?.span_kind) {
      tags.push({ label: "kind", value: spanData.rawData.span_kind });
    }
    if (spanData.traceId) {
      tags.push({ label: "trace_id", value: `...${spanData.traceId.slice(-6)}` });
    }
    if (spanData.spanId) {
      tags.push({ label: "span_id", value: `...${spanData.spanId.slice(-6)}` });
    }

    return tags;
  }, [spanData]);

  if (!spanData) return null;

  const tabItems = [
    {
      key: "details",
      label: "Details",
      children: <DetailsTabContent spanData={spanData} />,
    },
    {
      key: "rawData",
      label: "Raw Data",
      children: <RawDataTabContent spanData={spanData} />,
    },
  ];

  return (
    <BudForm
      data={{}}
      onBack={() => closeDrawer()}
      nextText="Close"
      onNext={async () => {
        closeDrawer();
      }}
    >
      <BudWraperBox classNames="mt-[2.2rem]">
        <BudDrawerLayout>
          {/* Header Section */}
          <div className="flex flex-col items-start justify-start w-full px-[1.4rem] py-[1.05rem] pb-[1.4rem] border-b-[.5px] border-b-[#1F1F1F]">
            <Text_10_400_B3B3B3 className="mb-2">{spanData.status}</Text_10_400_B3B3B3>
            <Text_16_400_EEEEEE className="mb-4 font-semibold">{spanData.title}</Text_16_400_EEEEEE>

            {/* Metadata Tags */}
            <div className="flex flex-wrap gap-2 mb-4">
              {metadataTags.map((tag, index) => (
                <Tag
                  key={index}
                  className="bg-[#1a1a1a] border-[#3a3a3a] text-[#B3B3B3] text-xs rounded-full px-3 py-1"
                >
                  <span className="text-[#757575]">{tag.label}</span>{" "}
                  <span className="text-[#EEEEEE]">{tag.value}</span>
                </Tag>
              ))}
            </div>

            {/* Duration info */}
            <div className="flex items-center gap-2 text-[#B3B3B3]">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12,6 12,12 16,14" />
              </svg>
              <Text_12_400_B3B3B3>
                Span took {formatDurationDisplay(spanData.duration)} at {spanData.time}
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
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
