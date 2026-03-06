/**
 * DeployUseCaseSuccess - Step 4 of the Deploy Use Case wizard
 *
 * Displays a success message with deployment details, and when the deployment
 * has access modes enabled (UI / API), shows:
 *  - "Open UI" button that opens the service's web UI in a new browser tab
 *  - API Endpoint section with base URL, auth instructions, collapsible
 *    endpoint reference, and copy-paste curl examples
 *
 * Existing behavior (deployment name, template name, "View Deployments",
 * "Close" buttons) is preserved.
 */

import React, { useEffect, useMemo, useState } from "react";
import { Image, Tag, Collapse, Button } from "antd";
import { RightOutlined } from "@ant-design/icons";
import { ExternalLink, Monitor, Copy } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";

import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import BudStepAlert from "src/flows/components/BudStepAlert";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import CustomPopover from "src/flows/components/customPopover";
import {
  Text_12_400_757575,
  Text_12_400_EEEEEE,
  Text_14_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_20_400_FFFFFF,
  Text_12_400_B3B3B3,
} from "@/components/ui/text";
import { useUseCases } from "src/stores/useUseCases";
import { useDrawer } from "src/hooks/useDrawer";
import { copyToClipboard } from "@/utils/clipboard";
import { successToast } from "@/components/toast";
import type { ApiEndpointSpec, AccessConfig } from "@/lib/budusecases";

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
  // External gateway URL for API access
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
// Main component
// ---------------------------------------------------------------------------

export default function DeployUseCaseSuccess() {
  const { selectedDeployment, selectedTemplate } = useUseCases();
  const { closeDrawer } = useDrawer();

  const accessConfig: AccessConfig | undefined =
    selectedDeployment?.access_config || selectedTemplate?.access;

  const uiEnabled = accessConfig?.ui?.enabled === true;
  const apiEnabled = accessConfig?.api?.enabled === true;
  const running = isDeploymentRunning(selectedDeployment?.status);

  const deploymentId = selectedDeployment?.id || "";
  const apiBaseUrl = useMemo(() => buildApiBaseUrl(deploymentId), [deploymentId]);

  const apiSpec = accessConfig?.api?.spec || [];

  // ------ UI button handler ------
  const handleOpenUI = () => {
    const token = getAuthToken();
    const url = buildUiUrl(deploymentId, token);
    window.open(url, "_blank", "noopener,noreferrer");
  };

  // ------ Copy base URL handler ------
  const [urlCopied, setUrlCopied] = useState(false);

  const handleCopyUrl = async () => {
    await copyToClipboard(apiBaseUrl, {
      onSuccess: () => {
        setUrlCopied(true);
        successToast("API base URL copied to clipboard");
      },
      enableLogging: false,
    });
  };

  useEffect(() => {
    if (!urlCopied) return;
    const t = setTimeout(() => setUrlCopied(false), 2000);
    return () => clearTimeout(t);
  }, [urlCopied]);

  return (
    <BudForm
      data={{}}
      nextText="View Deployments"
      onNext={() => {
        closeDrawer();
      }}
    >
      <BudWraperBox>
        {/* ---- Success Alert ---- */}
        <BudDrawerLayout>
          <BudStepAlert
            type="success"
            title="Deployment Started Successfully"
            description={`Your use case deployment "${selectedDeployment?.name || "deployment"}" has been created and started. It may take a few minutes for all components to be fully deployed.`}
          />
        </BudDrawerLayout>

        {/* ---- Deployment Details Card ---- */}
        <BudDrawerLayout>
          <DrawerCard>
            <div className="flex flex-col gap-2">
              {selectedDeployment?.name && (
                <div className="flex items-start gap-2">
                  <Text_12_400_757575 className="w-[6rem] shrink-0 pt-[1px]">
                    Deployment
                  </Text_12_400_757575>
                  <Text_14_400_EEEEEE className="leading-[140%]">
                    {selectedDeployment.name}
                  </Text_14_400_EEEEEE>
                </div>
              )}

              {(selectedTemplate?.display_name || selectedDeployment?.template_name) && (
                <div className="flex items-start gap-2">
                  <Text_12_400_757575 className="w-[6rem] shrink-0 pt-[1px]">
                    Template
                  </Text_12_400_757575>
                  <Text_14_400_EEEEEE className="leading-[140%]">
                    {selectedTemplate?.display_name || selectedDeployment?.template_name}
                  </Text_14_400_EEEEEE>
                </div>
              )}

              {selectedDeployment?.components && (
                <div className="flex items-start gap-2">
                  <Text_12_400_757575 className="w-[6rem] shrink-0 pt-[1px]">
                    Components
                  </Text_12_400_757575>
                  <Text_14_400_EEEEEE className="leading-[140%]">
                    {selectedDeployment.components.length} component{selectedDeployment.components.length !== 1 ? "s" : ""}
                  </Text_14_400_EEEEEE>
                </div>
              )}

              {/* Access mode badges */}
              {(uiEnabled || apiEnabled) && (
                <div className="flex items-start gap-2">
                  <Text_12_400_757575 className="w-[6rem] shrink-0 pt-[1px]">
                    Access
                  </Text_12_400_757575>
                  <div className="flex items-center gap-[.375rem] flex-wrap">
                    {uiEnabled && (
                      <Tag
                        color="#8B5CF6"
                        style={{
                          margin: 0,
                          fontSize: "0.625rem",
                          fontWeight: 600,
                          lineHeight: "1",
                          padding: "2px 8px",
                          borderRadius: 4,
                        }}
                      >
                        UI
                      </Tag>
                    )}
                    {apiEnabled && (
                      <Tag
                        color="#3B82F6"
                        style={{
                          margin: 0,
                          fontSize: "0.625rem",
                          fontWeight: 600,
                          lineHeight: "1",
                          padding: "2px 8px",
                          borderRadius: 4,
                        }}
                      >
                        API
                      </Tag>
                    )}
                  </div>
                </div>
              )}
            </div>
          </DrawerCard>
        </BudDrawerLayout>

        {/* ---- Open UI Button ---- */}
        {uiEnabled && running && (
          <BudDrawerLayout>
            <DrawerCard>
              <div className="flex flex-col gap-[.75rem]">
                <Text_20_400_FFFFFF className="tracking-[.03rem]">
                  Web UI
                </Text_20_400_FFFFFF>
                <Text_12_400_757575>
                  Open the deployed service's dashboard in a new browser tab.
                </Text_12_400_757575>
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
            </DrawerCard>
          </BudDrawerLayout>
        )}

        {/* ---- API Endpoint Section ---- */}
        {apiEnabled && running && (
          <BudDrawerLayout>
            <DrawerCard>
              <div className="flex flex-col gap-[.75rem]">
                <Text_20_400_FFFFFF className="tracking-[.03rem]">
                  API Endpoint
                </Text_20_400_FFFFFF>
                <Text_12_400_757575>
                  Use the base URL below to call this deployment's API. Include your project API key in the Authorization header.
                </Text_12_400_757575>

                {/* Base URL with copy */}
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

                {/* Auth instructions */}
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
                    <CopyButton text='Authorization: Bearer <YOUR_API_KEY>' />
                  </div>
                </div>

                {/* API Reference (collapsible) */}
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
                              API Reference ({apiSpec.length} endpoint{apiSpec.length !== 1 ? "s" : ""})
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
            </DrawerCard>
          </BudDrawerLayout>
        )}

        {/* ---- Not-yet-running hint ---- */}
        {(uiEnabled || apiEnabled) && !running && (
          <BudDrawerLayout>
            <DrawerCard>
              <div className="flex items-center gap-[.5rem]">
                <div className="w-[.5rem] h-[.5rem] rounded-full bg-[#F59E0B] shrink-0" />
                <Text_12_400_757575>
                  Access actions (UI / API) will become available once the deployment
                  is fully running.
                </Text_12_400_757575>
              </div>
            </DrawerCard>
          </BudDrawerLayout>
        )}
      </BudWraperBox>
    </BudForm>
  );
}
