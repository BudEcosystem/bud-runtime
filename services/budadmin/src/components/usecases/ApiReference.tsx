/**
 * ApiReference - Interactive API reference for a deployed use case.
 *
 * Renders each endpoint from `access_config.api.spec` with:
 *   - Colour-coded HTTP method badge (Tag)
 *   - Endpoint path and description
 *   - Collapsible request/response schema sections (Collapse)
 *   - Copy-paste curl example
 *
 * Follows the dark-theme styling and Ant Design component conventions
 * used throughout budadmin (see TemplateDetail.tsx, PipelineTriggersPanel.tsx).
 */

import React, { useState } from "react";
import { Tag, Collapse, Button, Tooltip, Typography, Empty } from "antd";
import {
  CopyOutlined,
  CheckOutlined,
  RightOutlined,
  CodeOutlined,
  ApiOutlined,
} from "@ant-design/icons";
import { copyToClipboard } from "@/utils/clipboard";
import { successToast, errorToast } from "@/components/toast";
import type { ApiEndpointSpec } from "@/lib/budusecases";

const { Text } = Typography;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Colour map for HTTP method badges */
const METHOD_COLORS: Record<string, string> = {
  GET: "#1890ff",
  POST: "#52c41a",
  PUT: "#fa8c16",
  PATCH: "#fa8c16",
  DELETE: "#ff4d4f",
  HEAD: "#8c8c8c",
  OPTIONS: "#8c8c8c",
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ApiReferenceProps {
  /** Deployment ID used to build the full endpoint URL */
  deploymentId: string;
  /** Base URL of the gateway (e.g. https://gateway.bud.studio) */
  gatewayBaseUrl: string;
  /** List of endpoint specs from access_config.api.spec */
  spec: ApiEndpointSpec[];
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Small coloured pill showing the HTTP method */
function MethodBadge({ method }: { method: string }) {
  const upper = method.toUpperCase();
  const color = METHOD_COLORS[upper] || "#8c8c8c";
  return (
    <Tag
      className="border-0 font-mono text-[0.7rem] font-semibold leading-[1]"
      style={{
        backgroundColor: `${color}20`,
        color,
        minWidth: 52,
        textAlign: "center",
      }}
    >
      {upper}
    </Tag>
  );
}

/** Generates a curl command string for a given endpoint */
function buildCurl(
  method: string,
  fullPath: string,
  requestBody?: Record<string, any> | null,
): string {
  const upper = method.toUpperCase();
  let cmd = `curl -X ${upper} ${fullPath} \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json"`;
  if (requestBody && Object.keys(requestBody).length > 0) {
    const bodyStr = JSON.stringify(requestBody, null, 2);
    cmd += ` \\\n  -d '${bodyStr}'`;
  }
  return cmd;
}

// ---------------------------------------------------------------------------
// EndpointCard
// ---------------------------------------------------------------------------

function EndpointCard({
  endpoint,
  deploymentId,
  gatewayBaseUrl,
}: {
  endpoint: ApiEndpointSpec;
  deploymentId: string;
  gatewayBaseUrl: string;
}) {
  const [copiedCurl, setCopiedCurl] = useState(false);

  const fullPath = `${gatewayBaseUrl}/usecases/${deploymentId}/api${endpoint.path}`;
  const curlCmd = buildCurl(endpoint.method, fullPath, endpoint.request_body);

  const handleCopyCurl = async () => {
    const result = await copyToClipboard(curlCmd, { enableLogging: false });
    if (result.success) {
      setCopiedCurl(true);
      successToast("Curl command copied to clipboard");
      setTimeout(() => setCopiedCurl(false), 2000);
    } else {
      errorToast("Failed to copy to clipboard");
    }
  };

  // Build collapsible items for request body and response schema
  const collapseItems: { key: string; label: React.ReactNode; children: React.ReactNode }[] = [];

  if (endpoint.request_body && Object.keys(endpoint.request_body).length > 0) {
    collapseItems.push({
      key: "request",
      label: (
        <span className="text-[0.7rem] text-[#B3B3B3] flex items-center gap-1">
          <CodeOutlined style={{ fontSize: 11 }} />
          Request Body
        </span>
      ),
      children: (
        <pre
          className="text-[0.7rem] leading-[1.5] font-mono text-[#EEEEEE] bg-[#111113] rounded p-3 overflow-x-auto max-h-[14rem]"
          style={{ margin: 0 }}
        >
          {JSON.stringify(endpoint.request_body, null, 2)}
        </pre>
      ),
    });
  }

  if (endpoint.response && Object.keys(endpoint.response).length > 0) {
    collapseItems.push({
      key: "response",
      label: (
        <span className="text-[0.7rem] text-[#B3B3B3] flex items-center gap-1">
          <CodeOutlined style={{ fontSize: 11 }} />
          Response
        </span>
      ),
      children: (
        <pre
          className="text-[0.7rem] leading-[1.5] font-mono text-[#EEEEEE] bg-[#111113] rounded p-3 overflow-x-auto max-h-[14rem]"
          style={{ margin: 0 }}
        >
          {JSON.stringify(endpoint.response, null, 2)}
        </pre>
      ),
    });
  }

  return (
    <div className="border border-[#1F1F1F] rounded-lg p-4">
      {/* Header: method badge + path */}
      <div className="flex items-center gap-2 mb-1">
        <MethodBadge method={endpoint.method} />
        <span className="text-[0.8rem] font-mono text-[#EEEEEE] break-all">
          {endpoint.path}
        </span>
      </div>

      {/* Description */}
      {endpoint.description && (
        <p className="text-[0.75rem] text-[#B3B3B3] leading-[160%] mt-1 mb-2 pl-1">
          {endpoint.description}
        </p>
      )}

      {/* Curl example */}
      <div className="mt-3 relative">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[0.7rem] text-[#757575]">curl</span>
          <Tooltip title={copiedCurl ? "Copied!" : "Copy curl command"}>
            <Button
              type="text"
              size="small"
              icon={copiedCurl ? <CheckOutlined /> : <CopyOutlined />}
              onClick={handleCopyCurl}
              className="text-[#757575] hover:text-[#EEEEEE]"
              style={{ fontSize: 12 }}
            />
          </Tooltip>
        </div>
        <pre
          className="text-[0.7rem] leading-[1.5] font-mono text-[#EEEEEE] bg-[#111113] rounded p-3 overflow-x-auto max-h-[10rem]"
          style={{ margin: 0 }}
        >
          {curlCmd}
        </pre>
      </div>

      {/* Collapsible schema sections */}
      {collapseItems.length > 0 && (
        <Collapse
          ghost
          expandIcon={({ isActive }) => (
            <RightOutlined
              rotate={isActive ? 90 : 0}
              style={{ color: "#757575", fontSize: 10 }}
            />
          )}
          className="mt-3"
          items={collapseItems}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const ApiReference: React.FC<ApiReferenceProps> = ({
  deploymentId,
  gatewayBaseUrl,
  spec,
}) => {
  if (!spec || spec.length === 0) {
    return (
      <Empty
        description={
          <Text className="text-[#757575]">
            No API endpoints defined for this use case.
          </Text>
        }
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  return (
    <div className="space-y-3">
      {/* Section header */}
      <div className="flex items-center gap-2 mb-2">
        <ApiOutlined style={{ color: "#757575", fontSize: 14 }} />
        <span className="text-[0.8rem] text-[#B3B3B3] font-medium">
          API Endpoints ({spec.length})
        </span>
      </div>

      {/* Endpoint cards */}
      {spec.map((endpoint, index) => (
        <EndpointCard
          key={`${endpoint.method}-${endpoint.path}-${index}`}
          endpoint={endpoint}
          deploymentId={deploymentId}
          gatewayBaseUrl={gatewayBaseUrl}
        />
      ))}
    </div>
  );
};

export default ApiReference;
