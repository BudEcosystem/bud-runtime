/**
 * Access - Tab component for the Use Case deployment detail page
 *
 * Displays access information for a deployed use case, including:
 *  - Web UI access ("Open UI" button + subdomain URL) when ui.enabled
 *  - API access (base URL, auth instructions, collapsible endpoint reference
 *    with per-endpoint curl examples) when api.enabled
 *  - A "not yet running" hint when access modes are configured but the
 *    deployment is not fully running
 *  - An empty state when neither UI nor API access is configured
 *
 * Ported from DeployUseCaseSuccess.tsx; adapted to accept a Deployment prop
 * instead of reading from Zustand store.
 */

import React, { useEffect, useMemo, useState } from "react";
import { Button, Tag, Collapse, Image } from "antd";
import { RightOutlined } from "@ant-design/icons";
import { ExternalLink, Monitor, Copy } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";

import {
  Text_12_400_757575,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_14_600_FFFFFF,
  Text_20_400_FFFFFF,
} from "@/components/ui/text";
import { copyToClipboard } from "@/utils/clipboard";
import { successToast } from "@/components/toast";
import CustomPopover from "src/flows/components/customPopover";
import type { Deployment, ApiEndpointSpec, AccessConfig } from "@/lib/budusecases";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE_URL =
  process.env.NEXT_PUBLIC_COPY_CODE_API_BASE_URL ||
  process.env.NEXT_PUBLIC_BASE_URL ||
  "";

/** HTTP method badge colors (dark-theme friendly) */
const METHOD_COLORS: Record<string, string> = {
  GET: "#10B981",
  POST: "#3B82F6",
  PUT: "#F59E0B",
  PATCH: "#8B5CF6",
  DELETE: "#EF4444",
  OPTIONS: "#6B7280",
  HEAD: "#6B7280",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getAuthToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("access_token") || "";
}

/** Backend status strings are UPPERCASE — always compare via .toLowerCase(). */
function isDeploymentRunning(status?: string): boolean {
  if (!status) return false;
  const lower = status.toLowerCase();
  return lower === "running" || lower === "completed";
}

function buildUiUrl(deploymentId: string, token: string): string {
  const base = API_BASE_URL.replace(/\/+$/, "");
  return `${base}/budusecases/usecases/${deploymentId}/ui/?token=${token}`;
}

function buildApiBaseUrl(deploymentId: string): string {
  return `${API_BASE_URL.replace(/\/+$/, "")}/usecases/${deploymentId}/api`;
}

function generateCurlForEndpoint(
  apiBaseUrl: string,
  endpoint: ApiEndpointSpec,
): string {
  const url = `${apiBaseUrl}${endpoint.path}`;
  const method = endpoint.method.toUpperCase();

  if (method === "GET" || method === "DELETE" || method === "HEAD") {
    return `curl --location --request ${method} '${url}' \\\n  --header 'Authorization: Bearer {API_KEY_HERE}'`;
  }

  const body = endpoint.request_body?.schema
    ? JSON.stringify(endpoint.request_body.schema, null, 2)
    : "{}";

  return `curl --location --request ${method} '${url}' \\\n  --header 'Authorization: Bearer {API_KEY_HERE}' \\\n  --header 'Content-Type: application/json' \\\n  --data '${body}'`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Inline copy button with transient "Copied" feedback. */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await copyToClipboard(text, {
      onSuccess: () => {
        setCopied(true);
        successToast("Copied to clipboard");
      },
      enableLogging: false,
    });
  };

  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(t);
  }, [copied]);

  return (
    <CustomPopover
      title={copied ? "Copied" : "Copy"}
      contentClassNames="py-[.3rem]"
      Placement="top"
    >
      <div
        className="w-[1.5rem] h-[1.5rem] rounded-[4px] flex justify-center items-center cursor-pointer hover:bg-[#FFFFFF10] transition-colors"
        onClick={handleCopy}
      >
        <Copy className="w-[.875rem] h-[.875rem] text-[#757575]" />
      </div>
    </CustomPopover>
  );
}

/** Single API endpoint row inside the collapsible reference. */
function EndpointRow({
  endpoint,
  apiBaseUrl,
}: {
  endpoint: ApiEndpointSpec;
  apiBaseUrl: string;
}) {
  const method = endpoint.method.toUpperCase();
  const color = METHOD_COLORS[method] || "#6B7280";
  const curl = generateCurlForEndpoint(apiBaseUrl, endpoint);

  return (
    <div className="border border-[#FFFFFF10] rounded-[6px] overflow-hidden mb-[.5rem]">
      {/* Header row */}
      <div className="flex items-center gap-[.5rem] px-[.75rem] py-[.5rem] bg-[#FFFFFF05]">
        <Tag
          color={color}
          style={{
            margin: 0,
            fontSize: "0.625rem",
            fontWeight: 600,
            lineHeight: "1",
            padding: "2px 6px",
            borderRadius: 4,
            minWidth: "2.5rem",
            textAlign: "center",
          }}
        >
          {method}
        </Tag>
        <Text_12_400_EEEEEE className="flex-1 font-mono">
          {endpoint.path}
        </Text_12_400_EEEEEE>
      </div>

      {/* Description */}
      {endpoint.description && (
        <div className="px-[.75rem] py-[.375rem]">
          <Text_12_400_757575>{endpoint.description}</Text_12_400_757575>
        </div>
      )}

      {/* Curl example */}
      <div className="px-[.75rem] pb-[.5rem]">
        <div className="flex items-center justify-between mb-[.25rem]">
          <Text_12_400_757575>curl</Text_12_400_757575>
          <CopyButton text={curl} />
        </div>
        <div className="custom-code rounded-[6px] bg-[#FFFFFF08] overflow-hidden">
          <div className="markdown-body text-[0.6875rem]">
            <SyntaxHighlighter
              language="bash"
              style={oneDark}
              customStyle={{
                margin: 0,
                padding: "0.5rem",
                fontSize: "0.6875rem",
                background: "transparent",
              }}
            >
              {curl}
            </SyntaxHighlighter>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface AccessProps {
  deployment?: Deployment;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function Access({ deployment }: AccessProps) {
  const deploymentId = deployment?.id || "";
  const apiBaseUrl = useMemo(() => buildApiBaseUrl(deploymentId), [deploymentId]);
  const [urlCopied, setUrlCopied] = useState(false);

  useEffect(() => {
    if (!urlCopied) return;
    const t = setTimeout(() => setUrlCopied(false), 2000);
    return () => clearTimeout(t);
  }, [urlCopied]);

  if (!deployment) return null;

  const accessConfig: AccessConfig | undefined = deployment.access_config;
  const uiEnabled = accessConfig?.ui?.enabled === true;
  const apiEnabled = accessConfig?.api?.enabled === true;
  const running = isDeploymentRunning(deployment.status);
  const apiSpec = accessConfig?.api?.spec || [];

  const handleOpenUI = () => {
    const token = getAuthToken();
    const url = buildUiUrl(deploymentId, token);
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const handleCopyUrl = async () => {
    await copyToClipboard(apiBaseUrl, {
      onSuccess: () => {
        setUrlCopied(true);
        successToast("API base URL copied to clipboard");
      },
      enableLogging: false,
    });
  };

  const parameters = deployment.parameters;
  const paramEntries = parameters ? Object.entries(parameters) : [];

  const formatParamValue = (value: unknown): string => {
    if (value === null || value === undefined) return "-";
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  const handleCopyMeta = async (value: string) => {
    const result = await copyToClipboard(value);
    if (result.success) {
      successToast("Copied to clipboard");
    }
  };

  return (
    <div className="flex flex-col gap-[1rem] pb-8">
      {/* ---- Access Section ---- */}

      {/* Not-yet-running hint */}
      {(uiEnabled || apiEnabled) && !running && (
        <div className="bg-[#111113] rounded-lg p-6 border border-[#1F1F1F]">
          <div className="flex items-center gap-[.5rem]">
            <div className="w-[.5rem] h-[.5rem] rounded-full bg-[#F59E0B] shrink-0" />
            <Text_12_400_757575>
              Access actions (UI / API) will become available once the deployment
              is fully running.
            </Text_12_400_757575>
          </div>
        </div>
      )}

      {/* Empty state for access */}
      {!uiEnabled && !apiEnabled && (
        <div className="bg-[#111113] rounded-lg p-6 border border-[#1F1F1F]">
          <Text_12_400_757575 className="text-center leading-[160%]">
            No access modes are configured for this deployment. UI and API access
            can be enabled in the use case template.
          </Text_12_400_757575>
        </div>
      )}

      {/* UI Access card */}
      {uiEnabled && running && (
        <div className="bg-[#111113] rounded-lg p-6 border border-[#1F1F1F]">
          <div className="flex flex-col gap-[.75rem]">
            <Text_20_400_FFFFFF className="tracking-[.03rem]">
              Web UI
            </Text_20_400_FFFFFF>
            <Text_12_400_757575>
              Open the deployed service&apos;s dashboard in a new browser tab.
            </Text_12_400_757575>

            <div className="flex items-center gap-[.5rem] bg-[#FFFFFF08] rounded-[6px] px-[.75rem] py-[.5rem] border border-[#FFFFFF10]">
              <Text_12_400_EEEEEE className="flex-1 font-mono break-all">
                {buildUiUrl(deploymentId, "")}
              </Text_12_400_EEEEEE>
            </div>

            <Button
              type="primary"
              onClick={handleOpenUI}
              style={{
                background: "#8B5CF6",
                borderColor: "#8B5CF6",
                display: "flex",
                alignItems: "center",
                gap: "0.375rem",
                width: "fit-content",
              }}
              icon={<Monitor className="w-[.875rem] h-[.875rem]" />}
            >
              <span className="flex items-center gap-[.25rem]">
                Open UI
                <ExternalLink className="w-[.75rem] h-[.75rem]" />
              </span>
            </Button>
          </div>
        </div>
      )}

      {/* API Access card */}
      {apiEnabled && running && (
        <div className="bg-[#111113] rounded-lg p-6 border border-[#1F1F1F]">
          <div className="flex flex-col gap-[.75rem]">
            <Text_20_400_FFFFFF className="tracking-[.03rem]">
              API Endpoint
            </Text_20_400_FFFFFF>
            <Text_12_400_757575>
              Use the base URL below to call this deployment&apos;s API. Include
              your project API key in the Authorization header.
            </Text_12_400_757575>

            <div className="flex items-center gap-[.5rem] bg-[#FFFFFF08] rounded-[6px] px-[.75rem] py-[.5rem] border border-[#FFFFFF10]">
              <Text_12_400_EEEEEE className="flex-1 font-mono break-all">
                {apiBaseUrl}
              </Text_12_400_EEEEEE>
              <CustomPopover
                title={urlCopied ? "Copied" : "Copy URL"}
                contentClassNames="py-[.3rem]"
                Placement="top"
              >
                <div
                  className="w-[1.5rem] h-[1.5rem] rounded-[4px] flex justify-center items-center cursor-pointer hover:bg-[#FFFFFF10] transition-colors shrink-0"
                  onClick={handleCopyUrl}
                >
                  <Image
                    preview={false}
                    src="/images/drawer/Copy.png"
                    alt="Copy"
                    style={{ height: ".75rem" }}
                  />
                </div>
              </CustomPopover>
            </div>

            <div className="bg-[#FFFFFF05] rounded-[6px] px-[.75rem] py-[.5rem] border border-[#FFFFFF08]">
              <Text_12_600_EEEEEE className="mb-[.375rem]">
                Authentication
              </Text_12_600_EEEEEE>
              <Text_12_400_B3B3B3 className="leading-[160%]">
                Add the following header to every request:
              </Text_12_400_B3B3B3>
              <div className="flex items-center gap-[.5rem] mt-[.375rem] bg-[#FFFFFF08] rounded-[4px] px-[.5rem] py-[.375rem]">
                <Text_12_400_EEEEEE className="font-mono flex-1">
                  Authorization: Bearer {"<YOUR_API_KEY>"}
                </Text_12_400_EEEEEE>
                <CopyButton text="Authorization: Bearer <YOUR_API_KEY>" />
              </div>
            </div>

            {apiSpec.length > 0 && (
              <div className="mt-[.25rem]">
                <Collapse
                  ghost
                  expandIcon={({ isActive }) => (
                    <RightOutlined
                      rotate={isActive ? 90 : 0}
                      style={{ color: "#757575", fontSize: "0.625rem" }}
                    />
                  )}
                  items={[
                    {
                      key: "api-reference",
                      label: (
                        <Text_12_600_EEEEEE>
                          API Reference ({apiSpec.length} endpoint
                          {apiSpec.length !== 1 ? "s" : ""})
                        </Text_12_600_EEEEEE>
                      ),
                      children: (
                        <div className="flex flex-col gap-0 mt-[.25rem]">
                          {apiSpec.map((endpoint, idx) => (
                            <EndpointRow
                              key={`${endpoint.method}-${endpoint.path}-${idx}`}
                              endpoint={endpoint}
                              apiBaseUrl={apiBaseUrl}
                            />
                          ))}
                        </div>
                      ),
                    },
                  ]}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* ---- Parameters Section ---- */}
      <div className="bg-[#111113] rounded-lg p-6 border border-[#1F1F1F]">
        <Text_14_600_FFFFFF className="mb-4">Parameters</Text_14_600_FFFFFF>

        {paramEntries.length === 0 ? (
          <Text_12_400_B3B3B3>No parameters configured</Text_12_400_B3B3B3>
        ) : (
          <div>
            {paramEntries.map(([key, value]) => (
              <div
                key={key}
                className="flex items-start justify-between py-2 border-b border-[#1F1F1F] last:border-0 gap-4"
              >
                <Text_12_400_757575 className="flex-shrink-0 min-w-[140px]">
                  {key}
                </Text_12_400_757575>
                <Text_12_400_EEEEEE className="text-right break-all">
                  {formatParamValue(value)}
                </Text_12_400_EEEEEE>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ---- Metadata Section ---- */}
      <div className="bg-[#111113] rounded-lg p-6 border border-[#1F1F1F]">
        <Text_14_600_FFFFFF className="mb-4">Metadata</Text_14_600_FFFFFF>

        <div>
          {[
            { label: "Deployment ID", value: deployment.id },
            { label: "Template ID", value: deployment.template_id },
            { label: "Cluster ID", value: deployment.cluster_id },
            { label: "Project ID", value: deployment.project_id },
            { label: "Pipeline Execution ID", value: deployment.pipeline_execution_id },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="flex items-center justify-between py-2 border-b border-[#1F1F1F] last:border-0"
            >
              <Text_12_400_757575>{label}</Text_12_400_757575>
              <div className="flex items-center gap-1.5">
                <Text_12_400_EEEEEE className="font-mono truncate max-w-[260px]">
                  {value ?? "-"}
                </Text_12_400_EEEEEE>
                {value && (
                  <button
                    onClick={() => handleCopyMeta(value)}
                    className="flex-shrink-0 text-[#757575] hover:text-[#EEEEEE] transition-colors cursor-pointer"
                    aria-label="Copy to clipboard"
                  >
                    <Copy className="w-[12px] h-[12px]" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
