/**
 * TemplateDetail - Read-only view for a use case template
 *
 * Displays template metadata, components (with helm-specific details),
 * deployment order, and parameters inside a drawer layout.
 *
 * Helm components show chart reference, version, and collapsible default
 * values.  Non-helm components show default component and compatible
 * component lists.
 */

import React, { useEffect, useState } from "react";
import { Tag, Collapse, Button, Input, Select } from "antd";
import { RightOutlined, CodeOutlined, RocketOutlined } from "@ant-design/icons";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_13_400_B3B3B3,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import { useUseCases } from "src/stores/useUseCases";
import { useCluster } from "src/hooks/useCluster";
import { useDrawer } from "src/hooks/useDrawer";
import { successToast, errorToast } from "@/components/toast";
import type {
  TemplateComponent,
  ComponentType,
} from "@/lib/budusecases";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Badge color per component type (dark-theme friendly) */
const COMPONENT_TYPE_COLORS: Record<ComponentType, string> = {
  model: "#8B5CF6",
  llm: "#8B5CF6",
  embedder: "#6366F1",
  reranker: "#EC4899",
  vector_db: "#10B981",
  memory_store: "#F59E0B",
  helm: "#06B6D4",
};

/** Human-readable labels for component types */
const COMPONENT_TYPE_LABELS: Record<ComponentType, string> = {
  model: "Model",
  llm: "LLM",
  embedder: "Embedder",
  reranker: "Reranker",
  vector_db: "Vector DB",
  memory_store: "Memory Store",
  helm: "Helm Chart",
};

// ---------------------------------------------------------------------------
// Helper sub-components
// ---------------------------------------------------------------------------

/** Small colored badge for a component type */
function TypeBadge({ type }: { type: ComponentType }) {
  const color = COMPONENT_TYPE_COLORS[type] || "#757575";
  const label = COMPONENT_TYPE_LABELS[type] || type;

  return (
    <Tag
      style={{
        backgroundColor: `${color}20`,
        color,
        border: `1px solid ${color}40`,
        borderRadius: 4,
        fontSize: "0.625rem",
        lineHeight: "1.2",
        padding: "2px 6px",
        margin: 0,
      }}
    >
      {label}
    </Tag>
  );
}

/** Source badge (system vs user) */
function SourceBadge({ source }: { source: string }) {
  const isSystem = source === "system";
  const color = isSystem ? "#10B981" : "#6366F1";
  const label = isSystem ? "System" : "User";

  return (
    <Tag
      style={{
        backgroundColor: `${color}20`,
        color,
        border: `1px solid ${color}40`,
        borderRadius: 4,
        fontSize: "0.625rem",
        lineHeight: "1.2",
        padding: "2px 6px",
        margin: 0,
      }}
    >
      {label}
    </Tag>
  );
}

/** Renders a key-value row used in detail sections */
function DetailRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 py-[0.35rem]">
      <Text_12_400_757575 className="w-[7.5rem] shrink-0 pt-[1px]">
        {label}
      </Text_12_400_757575>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component cards
// ---------------------------------------------------------------------------

/** Card for a single helm-type component */
function HelmComponentCard({ component }: { component: TemplateComponent }) {
  const hasValues =
    component.chart?.values &&
    Object.keys(component.chart.values).length > 0;

  return (
    <div className="border border-[#1F1F1F] rounded-lg p-4 mb-3">
      {/* Header row */}
      <div className="flex items-center gap-2 mb-2">
        <TypeBadge type="helm" />
        <Text_14_400_EEEEEE className="leading-[140%]">
          {component.display_name || component.name}
        </Text_14_400_EEEEEE>
        {component.required && (
          <span className="text-[0.6rem] text-[#FF4D4F] ml-auto">
            Required
          </span>
        )}
      </div>

      {component.description && (
        <Text_12_400_B3B3B3 className="leading-[160%] mb-2">
          {component.description}
        </Text_12_400_B3B3B3>
      )}

      {/* Chart details */}
      <div className="mt-2 pl-1">
        <DetailRow label="Chart Ref">
          <span className="text-[0.75rem] font-mono text-[#EEEEEE] break-all">
            {component.chart?.ref || "-"}
          </span>
        </DetailRow>

        <DetailRow label="Chart Version">
          <span className="text-[0.75rem] text-[#EEEEEE]">
            {component.chart?.version || "latest"}
          </span>
        </DetailRow>
      </div>

      {/* Collapsible default values */}
      {hasValues && (
        <Collapse
          ghost
          expandIcon={({ isActive }) => (
            <RightOutlined
              rotate={isActive ? 90 : 0}
              style={{ color: "#757575", fontSize: 10 }}
            />
          )}
          className="mt-2"
          items={[
            {
              key: "values",
              label: (
                <span className="text-[0.7rem] text-[#B3B3B3] flex items-center gap-1">
                  <CodeOutlined style={{ fontSize: 11 }} />
                  Default Values
                </span>
              ),
              children: (
                <pre
                  className="text-[0.7rem] leading-[1.5] font-mono text-[#EEEEEE] bg-[#111113] rounded p-3 overflow-x-auto max-h-[14rem]"
                  style={{ margin: 0 }}
                >
                  {JSON.stringify(component.chart?.values, null, 2)}
                </pre>
              ),
            },
          ]}
        />
      )}
    </div>
  );
}

/** Card for a non-helm (standard) component */
function StandardComponentCard({
  component,
}: {
  component: TemplateComponent;
}) {
  return (
    <div className="border border-[#1F1F1F] rounded-lg p-4 mb-3">
      {/* Header row */}
      <div className="flex items-center gap-2 mb-2">
        <TypeBadge type={component.component_type} />
        <Text_14_400_EEEEEE className="leading-[140%]">
          {component.display_name || component.name}
        </Text_14_400_EEEEEE>
        {component.required && (
          <span className="text-[0.6rem] text-[#FF4D4F] ml-auto">
            Required
          </span>
        )}
      </div>

      {component.description && (
        <Text_12_400_B3B3B3 className="leading-[160%] mb-2">
          {component.description}
        </Text_12_400_B3B3B3>
      )}

      <div className="mt-2 pl-1">
        {component.default_component && (
          <DetailRow label="Default">
            <span className="text-[0.75rem] font-mono text-[#EEEEEE] break-all">
              {component.default_component}
            </span>
          </DetailRow>
        )}

        {component.compatible_components &&
          component.compatible_components.length > 0 && (
            <DetailRow label="Compatible">
              <div className="flex flex-wrap gap-1">
                {component.compatible_components.map((c, i) => (
                  <Tag
                    key={i}
                    style={{
                      backgroundColor: "#1F1F1F",
                      color: "#B3B3B3",
                      border: "1px solid #2A2A2A",
                      borderRadius: 4,
                      fontSize: "0.65rem",
                      padding: "1px 5px",
                      margin: 0,
                    }}
                  >
                    {c}
                  </Tag>
                ))}
              </div>
            </DetailRow>
          )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function TemplateDetail() {
  const {
    selectedTemplate: template,
    createDeployment,
    setDeploymentName,
    setSelectedCluster,
    selectComponent,
    selectDeployment,
    fetchDeployments,
  } = useUseCases();
  const { clusters, getClusters } = useCluster();
  const { openDrawer } = useDrawer();

  const [showDeployForm, setShowDeployForm] = useState(false);
  const [deployName, setDeployName] = useState("");
  const [deployClusterId, setDeployClusterId] = useState<string | null>(null);
  const [isDeploying, setIsDeploying] = useState(false);

  useEffect(() => {
    if (showDeployForm && (!clusters || clusters.length === 0)) {
      getClusters({ page: 1, limit: 50 });
    }
  }, [showDeployForm]);

  const handleDeploy = async () => {
    if (!deployName.trim()) {
      errorToast("Deployment name is required");
      return;
    }
    if (!deployClusterId) {
      errorToast("Please select a cluster");
      return;
    }

    setIsDeploying(true);
    try {
      setDeploymentName(deployName.trim());
      setSelectedCluster(deployClusterId);
      // Auto-select components using defaults from the template
      if (template.components) {
        for (const comp of template.components) {
          const value = comp.default_component || comp.name;
          selectComponent(comp.name, value);
        }
      }
      const deployment = await createDeployment();
      if (deployment) {
        await fetchDeployments();
        selectDeployment(deployment);
        openDrawer("deployment-progress", { deployment });
      }
    } finally {
      setIsDeploying(false);
    }
  };

  if (!template) {
    return (
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="p-6 text-center">
            <Text_13_400_B3B3B3>No template selected.</Text_13_400_B3B3B3>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    );
  }

  // Sort components by sort_order for display
  const sortedComponents = [...(template.components || [])].sort(
    (a, b) => a.sort_order - b.sort_order
  );

  const hasParameters =
    template.parameters && Object.keys(template.parameters).length > 0;

  const hasDeploymentOrder =
    template.deployment_order && template.deployment_order.length > 0;

  return (
    <BudWraperBox>
      {/* ----------------------------------------------------------------- */}
      {/* Section 1: Header / Metadata                                      */}
      {/* ----------------------------------------------------------------- */}
      <BudDrawerLayout>
        <DrawerTitleCard
          title="Template Details"
          description="View the configuration of this deployment template."
        />
        <DrawerCard>
          {/* Name + version row */}
          <div className="flex items-center gap-2 mb-2">
            <Text_14_400_EEEEEE className="leading-[140%]">
              {template.display_name || template.name}
            </Text_14_400_EEEEEE>
            <span className="text-[0.7rem] text-[#757575]">
              v{template.version}
            </span>
            <SourceBadge source={template.source} />
          </div>

          {/* Tags */}
          {template.tags && template.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {template.tags.map((tag, i) => (
                <Tag
                  key={i}
                  style={{
                    backgroundColor: "#1F1F1F",
                    color: "#B3B3B3",
                    border: "1px solid #2A2A2A",
                    borderRadius: 4,
                    fontSize: "0.625rem",
                    padding: "2px 6px",
                    margin: 0,
                  }}
                >
                  {tag}
                </Tag>
              ))}
            </div>
          )}

          {/* Category */}
          {template.category && (
            <div className="mb-2">
              <Text_12_400_757575 className="leading-[160%]">
                Category:{" "}
                <span className="text-[#B3B3B3]">{template.category}</span>
              </Text_12_400_757575>
            </div>
          )}

          {/* Description */}
          {template.description && (
            <Text_12_400_B3B3B3 className="leading-[170%] mt-1">
              {template.description}
            </Text_12_400_B3B3B3>
          )}
        </DrawerCard>
      </BudDrawerLayout>

      {/* ----------------------------------------------------------------- */}
      {/* Section 2: Components                                             */}
      {/* ----------------------------------------------------------------- */}
      <BudDrawerLayout>
        <DrawerTitleCard
          title={`Components (${sortedComponents.length})`}
          description="The building blocks of this template. Helm components deploy charts directly; others deploy AI models or services."
        />
        <DrawerCard>
          {sortedComponents.length > 0 ? (
            sortedComponents.map((comp) =>
              comp.component_type === "helm" ? (
                <HelmComponentCard key={comp.id} component={comp} />
              ) : (
                <StandardComponentCard key={comp.id} component={comp} />
              )
            )
          ) : (
            <div className="py-4 text-center border border-[#1F1F1F] rounded-[6px]">
              <Text_12_400_B3B3B3>
                No components defined in this template.
              </Text_12_400_B3B3B3>
            </div>
          )}
        </DrawerCard>
      </BudDrawerLayout>

      {/* ----------------------------------------------------------------- */}
      {/* Section 3: Deployment Order                                       */}
      {/* ----------------------------------------------------------------- */}
      {hasDeploymentOrder && (
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Deployment Order"
            description="Components are deployed in this sequence."
          />
          <DrawerCard>
            <div className="flex flex-col gap-0">
              {template.deployment_order.map((step, idx) => {
                const isLast =
                  idx === template.deployment_order.length - 1;
                return (
                  <div key={idx} className="flex items-center gap-2">
                    {/* Step number circle */}
                    <div
                      className="w-[1.4rem] h-[1.4rem] rounded-full flex items-center justify-center shrink-0"
                      style={{
                        backgroundColor: "#1F1F1F",
                        border: "1px solid #2A2A2A",
                      }}
                    >
                      <span className="text-[0.6rem] text-[#EEEEEE] font-mono">
                        {idx + 1}
                      </span>
                    </div>

                    {/* Step name */}
                    <Text_12_400_B3B3B3 className="leading-[100%] py-[0.5rem]">
                      {step}
                    </Text_12_400_B3B3B3>

                    {/* Arrow indicator (except after the last step) */}
                    {!isLast && (
                      <RightOutlined
                        style={{
                          color: "#757575",
                          fontSize: 9,
                          marginLeft: "auto",
                        }}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </DrawerCard>
        </BudDrawerLayout>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* Section 4: Parameters                                             */}
      {/* ----------------------------------------------------------------- */}
      {hasParameters && (
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Parameters"
            description="Configurable parameters that can be adjusted at deployment time."
          />
          <DrawerCard>
            <Collapse
              ghost
              expandIcon={({ isActive }) => (
                <RightOutlined
                  rotate={isActive ? 90 : 0}
                  style={{ color: "#757575", fontSize: 10 }}
                />
              )}
              defaultActiveKey={["params"]}
              items={[
                {
                  key: "params",
                  label: (
                    <span className="text-[0.75rem] text-[#B3B3B3]">
                      {Object.keys(template.parameters).length} parameter
                      {Object.keys(template.parameters).length !== 1
                        ? "s"
                        : ""}
                    </span>
                  ),
                  children: (
                    <div className="flex flex-col gap-2">
                      {Object.entries(template.parameters).map(
                        ([key, param]) => (
                          <div
                            key={key}
                            className="border border-[#1F1F1F] rounded-md p-3"
                          >
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-[0.75rem] font-mono text-[#EEEEEE]">
                                {key}
                              </span>
                              <Tag
                                style={{
                                  backgroundColor: "#1F1F1F",
                                  color: "#757575",
                                  border: "1px solid #2A2A2A",
                                  borderRadius: 4,
                                  fontSize: "0.6rem",
                                  padding: "1px 4px",
                                  margin: 0,
                                }}
                              >
                                {param.type}
                              </Tag>
                            </div>

                            {param.description && (
                              <Text_12_400_757575 className="leading-[160%] mb-1">
                                {param.description}
                              </Text_12_400_757575>
                            )}

                            <div className="flex gap-3 mt-1">
                              <Text_12_400_757575>
                                Default:{" "}
                                <span className="text-[#B3B3B3] font-mono">
                                  {JSON.stringify(param.default)}
                                </span>
                              </Text_12_400_757575>

                              {param.min !== undefined && (
                                <Text_12_400_757575>
                                  Min:{" "}
                                  <span className="text-[#B3B3B3] font-mono">
                                    {param.min}
                                  </span>
                                </Text_12_400_757575>
                              )}

                              {param.max !== undefined && (
                                <Text_12_400_757575>
                                  Max:{" "}
                                  <span className="text-[#B3B3B3] font-mono">
                                    {param.max}
                                  </span>
                                </Text_12_400_757575>
                              )}
                            </div>
                          </div>
                        )
                      )}
                    </div>
                  ),
                },
              ]}
            />
          </DrawerCard>
        </BudDrawerLayout>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* Section 5: Deploy Action                                          */}
      {/* ----------------------------------------------------------------- */}
      <BudDrawerLayout>
        <DrawerCard>
          {!showDeployForm ? (
            <Button
              type="primary"
              icon={<RocketOutlined />}
              onClick={() => setShowDeployForm(true)}
              block
              className="!bg-[#965CDE] !border-[#965CDE] hover:!bg-[#7C3AED] hover:!border-[#7C3AED]"
            >
              Deploy This Template
            </Button>
          ) : (
            <div className="flex flex-col gap-3">
              <Text_14_400_EEEEEE>Quick Deploy</Text_14_400_EEEEEE>

              <div>
                <Text_12_400_757575 className="mb-1 block">
                  Deployment Name
                </Text_12_400_757575>
                <Input
                  placeholder={`e.g. my-${template.name}-deployment`}
                  value={deployName}
                  onChange={(e) => setDeployName(e.target.value)}
                  disabled={isDeploying}
                  className="!bg-transparent !text-[#EEEEEE] !border-[#757575] hover:!border-[#CFCFCF] focus:!border-[#CFCFCF] placeholder:!text-[#808080]"
                />
              </div>

              <div>
                <Text_12_400_757575 className="mb-1 block">
                  Target Cluster
                </Text_12_400_757575>
                <Select
                  placeholder="Select a cluster"
                  value={deployClusterId}
                  onChange={(value) => setDeployClusterId(value)}
                  disabled={isDeploying}
                  className="w-full"
                  popupClassName="!bg-[#111113]"
                  options={
                    clusters?.filter((c: any) => c.cluster_id).map((c: any) => ({
                      label: c.cluster_name || c.name || c.id,
                      value: c.cluster_id,
                    })) || []
                  }
                  notFoundContent={
                    <span className="text-[#757575] text-[0.75rem]">
                      No clusters available
                    </span>
                  }
                />
              </div>

              <div className="flex gap-2 mt-1">
                <Button
                  type="primary"
                  icon={<RocketOutlined />}
                  onClick={handleDeploy}
                  loading={isDeploying}
                  className="flex-1 !bg-[#965CDE] !border-[#965CDE] hover:!bg-[#7C3AED] hover:!border-[#7C3AED]"
                >
                  {isDeploying ? "Deploying..." : "Deploy"}
                </Button>
                <Button
                  onClick={() => setShowDeployForm(false)}
                  disabled={isDeploying}
                  className="!bg-transparent !border-[#757575] !text-[#EEEEEE] hover:!bg-[#FFFFFF08] hover:!border-[#CFCFCF]"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </DrawerCard>
      </BudDrawerLayout>
    </BudWraperBox>
  );
}
