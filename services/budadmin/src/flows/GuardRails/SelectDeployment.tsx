import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Collapse, Spin, Button, Popover } from "antd";
import { SearchOutlined, RightOutlined, DownOutlined } from "@ant-design/icons";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import { useEndPoints } from "src/hooks/useEndPoint";
import useGuardrails from "src/hooks/useGuardrails";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";
import IconRender from "../components/BudIconRender";
import Tags from "../components/DrawerTags";
import { endpointStatusMapping } from "@/lib/colorMapping";

const { Panel } = Collapse;

interface Deployment {
  id: string;
  name: string;
  type: "model" | "route" | "tool" | "agent";
  description?: string;
  status?: string;
  icon?: string;
}

export default function SelectDeployment() {
  const { openDrawerWithStep } = useDrawer();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedDeployment, setSelectedDeployment] = useState<string>("");
  const [selectedDeploymentData, setSelectedDeploymentData] =
    useState<any>(null);
  const [expandedSections, setExpandedSections] = useState<string[]>([
    "deployments",
    "tools",
    "agents",
  ]);

  // Helper function to get status color
  const getStatusColor = (status: string): string => {
    const statusKey =
      status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();

    // Check for exact match first
    if (endpointStatusMapping[statusKey]) {
      return endpointStatusMapping[statusKey];
    }

    // Check for specific statuses
    if (status.toLowerCase() === "active") {
      return "#479D5F"; // Green for active
    }
    if (status.toLowerCase() === "running") {
      return "#479D5F"; // Green for running
    }
    if (status.toLowerCase() === "deploying") {
      return "#965CDE"; // Purple for deploying
    }
    if (status.toLowerCase() === "failed" || status.toLowerCase() === "error") {
      return "#EC7575"; // Red for failed/error
    }
    if (
      status.toLowerCase() === "stopped" ||
      status.toLowerCase() === "paused"
    ) {
      return "#DE5CD1"; // Pink for stopped/paused
    }
    if (
      status.toLowerCase() === "unhealthy" ||
      status.toLowerCase() === "processing"
    ) {
      return "#D1B854"; // Yellow for unhealthy/processing
    }

    // Default color if no match
    return "#757575"; // Gray as default
  };

  // Pagination states
  const [endpointsPage, setEndpointsPage] = useState(1);
  const pageSize = 10;

  // Use hooks for API data
  const {
    endPoints,
    loading: endpointsLoading,
    getEndPoints,
    totalRecords: totalEndpoints,
  } = useEndPoints();
  const {
    selectedProject,
    updateWorkflow,
    workflowLoading,
    setSelectedDeployment: setSelectedDeploymentInStore,
  } = useGuardrails();

  // Reset page when search term changes
  useEffect(() => {
    setEndpointsPage(1);
  }, [searchTerm]);

  // Fetch endpoints when component mounts or search/page changes
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      const projectId = selectedProject?.project?.id || selectedProject?.id;
      if (projectId) {
        getEndPoints({
          id: projectId,
          page: endpointsPage,
          limit: pageSize,
          name: searchTerm || undefined,
        });
      }
    }, 300);

    return () => clearTimeout(delayDebounceFn);
  }, [searchTerm, endpointsPage, selectedProject]);

  // Mock deployment data - would typically come from API
  const deployments: Deployment[] = [
    // Models
    {
      id: "model-1",
      name: "GPT-4 Production",
      type: "model",
      description: "Main production LLM endpoint",
      status: "Active",
      icon: "🤖",
    },
    {
      id: "model-2",
      name: "Claude-3 Staging",
      type: "model",
      description: "Staging environment for Claude",
      status: "Active",
      icon: "🧠",
    },
    {
      id: "model-3",
      name: "Llama-2 Dev",
      type: "model",
      description: "Development Llama model",
      status: "Active",
      icon: "🦙",
    },

    // Routes
    {
      id: "route-1",
      name: "API Gateway Main",
      type: "route",
      description: "Primary API routing endpoint",
      status: "Active",
      icon: "🔀",
    },
    {
      id: "route-2",
      name: "Load Balancer",
      type: "route",
      description: "Traffic distribution route",
      status: "Active",
      icon: "⚖️",
    },

    // Tools
    {
      id: "tool-1",
      name: "Code Interpreter",
      type: "tool",
      description: "Python code execution tool",
      status: "Active",
      icon: "🔧",
    },
    {
      id: "tool-2",
      name: "Web Search Tool",
      type: "tool",
      description: "Internet search capability",
      status: "Active",
      icon: "🔍",
    },
    {
      id: "tool-3",
      name: "Database Query Tool",
      type: "tool",
      description: "SQL database access",
      status: "Active",
      icon: "💾",
    },

    // Agents
    {
      id: "agent-1",
      name: "Customer Support Agent",
      type: "agent",
      description: "Automated support assistant",
      status: "Active",
      icon: "👤",
    },
    {
      id: "agent-2",
      name: "Research Assistant",
      type: "agent",
      description: "Research and analysis agent",
      status: "Active",
      icon: "📚",
    },
  ];

  const handleBack = () => {
    openDrawerWithStep("select-project");
  };

  const handleNext = async () => {
    if (!selectedDeployment) {
      errorToast("Please select a deployment");
      return;
    }

    try {
      // Update workflow with selected deployment (endpoint)
      await updateWorkflow({
        step_number: 5, // Deployment/endpoint selection is step 5
        workflow_total_steps: 6,
        endpoint_id: selectedDeployment,
        trigger_workflow: false,
      });

      // Move to probe settings
      openDrawerWithStep("probe-settings");
    } catch (error) {
      console.error("Failed to update workflow:", error);
    }
  };

  const handleDeploymentSelect = (deployment: any, type: string) => {
    const id = deployment.endpoint_id || deployment.id;
    setSelectedDeployment(id);
    setSelectedDeploymentData({ ...deployment, type });
    // Store the deployment in the guardrails store
    setSelectedDeploymentInStore({ ...deployment, type });
  };

  const getFilteredDeployments = () => {
    if (!searchTerm) return deployments;

    return deployments.filter(
      (deployment) =>
        deployment.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        deployment.description
          ?.toLowerCase()
          .includes(searchTerm.toLowerCase()) ||
        deployment.type.toLowerCase().includes(searchTerm.toLowerCase()),
    );
  };

  const groupedDeployments = getFilteredDeployments().reduce(
    (acc, deployment) => {
      const key = deployment.type + "s";
      if (!acc[key]) {
        acc[key] = [];
      }
      acc[key].push(deployment);
      return acc;
    },
    {} as Record<string, Deployment[]>,
  );

  // Render deployment/endpoint item
  const renderDeploymentListItem = (endpoint: any) => {
    const description = endpoint.endpoint_url || endpoint.description || "";
    const isLongDescription = description.length > 60;

    return (
      <div
        key={endpoint.endpoint_id || endpoint.id}
        onClick={() => handleDeploymentSelect(endpoint, "deployment")}
        className={`pt-[1.05rem] px-[1.35rem] pb-[.8rem] cursor-pointer hover:shadow-lg border-y-[0.5px] flex-row flex hover:bg-[#FFFFFF08] transition-all ${
          selectedDeployment === (endpoint.endpoint_id || endpoint.id)
            ? "border-y-[#965CDE] bg-[#965CDE10]"
            : "border-y-[#1F1F1F] hover:border-[#757575]"
        }`}
      >
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-[1rem]">
            {/* Deployment Icon - Use IconRender if model is available */}
            {endpoint.model ? (
              <IconRender
                icon={endpoint.model?.icon}
                size={43}
                imageSize={24}
                type={endpoint.model?.provider_type}
                model={endpoint.model}
              />
            ) : (
              <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center shrink-0">
                <span className="text-[1.2rem]">🚀</span>
              </div>
            )}

            {/* Deployment Details */}
            <div className="flex flex-col">
              <Text_14_400_EEEEEE className="mb-[0.25rem]">
                {endpoint.name || endpoint.endpoint_name}
              </Text_14_400_EEEEEE>
              {description && (
                <div className="flex items-center gap-[0.5rem]">
                  <Text_12_400_757575 className="line-clamp-1">
                    {description}
                  </Text_12_400_757575>
                  {isLongDescription && (
                    <Popover
                      content={
                        <div className="max-w-[400px]">
                          <Text_12_400_757575>{description}</Text_12_400_757575>
                        </div>
                      }
                      trigger="hover"
                      placement="top"
                      overlayClassName="[&_.ant-popover-inner]:!bg-[#2A2A2A] [&_.ant-popover-arrow]:!hidden"
                    >
                      <span
                        className="text-[#965CDE] text-[12px] cursor-pointer hover:text-[#a876e6] whitespace-nowrap"
                        onClick={(e) => e.stopPropagation()}
                      >
                        see more
                      </span>
                    </Popover>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Selection Indicator */}
          <div className="flex items-center gap-[0.75rem]">
            {endpoint.status && (
              <Tags
                name={
                  endpoint.status.charAt(0).toUpperCase() +
                  endpoint.status.slice(1).toLowerCase()
                }
                color={getStatusColor(endpoint.status)}
                textClass="!text-[0.75rem] px-[0.25rem]"
              />
            )}
            <Checkbox
              checked={
                selectedDeployment === (endpoint.endpoint_id || endpoint.id)
              }
              className="AntCheckbox pointer-events-none"
            />
          </div>
        </div>
      </div>
    );
  };

  const renderDeploymentItem = (deployment: Deployment) => {
    const description = deployment.description || "";
    const isLongDescription = description.length > 80;

    return (
      <div
        key={deployment.id}
        onClick={() => handleDeploymentSelect(deployment, deployment.type)}
        className={`pt-[1.05rem] px-[1.35rem] pb-[.8rem] cursor-pointer hover:shadow-lg border-y-[0.5px] flex-row flex hover:bg-[#FFFFFF08] transition-all ${
          selectedDeployment === deployment.id
            ? "border-y-[#965CDE] bg-[#965CDE10]"
            : "border-y-[#1F1F1F] hover:border-[#757575]"
        }`}
      >
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-[1rem]">
            {/* Deployment Icon */}
            <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center shrink-0">
              <span className="text-[1.2rem]">{deployment.icon}</span>
            </div>

            {/* Deployment Details */}
            <div className="flex flex-col">
              <Text_14_400_EEEEEE className="mb-[0.25rem]">
                {deployment.name}
              </Text_14_400_EEEEEE>
              {description && (
                <div className="flex items-center gap-[0.5rem]">
                  <Text_12_400_757575 className="line-clamp-1">
                    {description}
                  </Text_12_400_757575>
                  {isLongDescription && (
                    <Popover
                      content={
                        <div className="max-w-[400px]">
                          <Text_12_400_757575>{description}</Text_12_400_757575>
                        </div>
                      }
                      trigger="hover"
                      placement="top"
                      overlayClassName="[&_.ant-popover-inner]:!bg-[#2A2A2A] [&_.ant-popover-arrow]:!hidden"
                    >
                      <span
                        className="text-[#965CDE] text-[12px] cursor-pointer hover:text-[#a876e6] whitespace-nowrap"
                        onClick={(e) => e.stopPropagation()}
                      >
                        see more
                      </span>
                    </Popover>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Selection Indicator */}
          <div className="flex items-center gap-[0.75rem]">
            {deployment.status && (
              <Tags
                name={deployment.status}
                color={getStatusColor(deployment.status)}
                textClass="!text-[0.75rem] px-[0.25rem]"
              />
            )}
            <Checkbox
              checked={selectedDeployment === deployment.id}
              className="AntCheckbox pointer-events-none"
            />
          </div>
        </div>
      </div>
    );
  };

  const customExpandIcon = ({ isActive }: any) => (
    <div className="transition-transform duration-200">
      {isActive ? (
        <DownOutlined className="text-[#757575]" />
      ) : (
        <RightOutlined className="text-[#757575]" />
      )}
    </div>
  );

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Next"
      disableNext={!selectedDeployment || workflowLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Deployment"
            description="Select from the available deployment to which you would like to add the Guardrail to."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="pb-[1.35rem]">
            {/* Search Bar */}
            <div className="mb-[1.5rem] px-[1.35rem]">
              <Input
                placeholder="Search"
                prefix={<SearchOutlined className="text-[#757575]" />}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-transparent text-[#EEEEEE] border-[#757575] hover:border-[#EEEEEE] focus:border-[#EEEEEE]"
                style={{
                  backgroundColor: "transparent",
                  color: "#EEEEEE",
                }}
              />
            </div>

            {/* Deployment Sections */}
            <Collapse
              defaultActiveKey={expandedSections}
              onChange={(keys) => setExpandedSections(keys as string[])}
              expandIcon={customExpandIcon}
              className="bg-transparent border-none [&_.ant-collapse-item]:!bg-transparent [&_.ant-collapse-header]:!bg-transparent [&_.ant-collapse-header]:!border-none [&_.ant-collapse-content]:!bg-transparent [&_.ant-collapse-content-box]:!bg-transparent [&_.ant-collapse-content-box]:!px-0 [&_.ant-collapse-item]:!border-none [&_.ant-collapse-content]:!border-none"
              style={{ backgroundColor: "transparent" }}
              bordered={false}
            >
              {/* Deployments Section */}
              <Panel
                header={
                  <div className="flex items-center gap-[0.5rem]">
                    <Text_14_600_FFFFFF>Deployments</Text_14_600_FFFFFF>
                    <Text_12_400_757575>
                      ({totalEndpoints || 0})
                    </Text_12_400_757575>
                  </div>
                }
                key="deployments"
                className="border-none mb-[1rem] !bg-transparent"
                style={{ backgroundColor: "transparent" }}
              >
                {endpointsLoading ? (
                  <div className="flex justify-center py-[2rem]">
                    <Spin size="large" />
                  </div>
                ) : (
                  <>
                    {endPoints && endPoints.length > 0 ? (
                      <>
                        <div className="space-y-0">
                          {endPoints.map((endpoint) =>
                            renderDeploymentListItem(endpoint),
                          )}
                        </div>
                        {totalEndpoints > pageSize && (
                          <div className="flex justify-between items-center px-[1.35rem] py-[1rem]">
                            <Button
                              onClick={() =>
                                setEndpointsPage((prev) =>
                                  Math.max(1, prev - 1),
                                )
                              }
                              disabled={endpointsPage === 1}
                              className="bg-[#1F1F1F] text-[#EEEEEE] border-[#757575] hover:bg-[#2A2A2A] hover:border-[#EEEEEE]"
                            >
                              Previous
                            </Button>
                            <Text_12_400_757575>
                              Page {endpointsPage} of{" "}
                              {Math.ceil(totalEndpoints / pageSize)}
                            </Text_12_400_757575>
                            <Button
                              onClick={() =>
                                setEndpointsPage((prev) => prev + 1)
                              }
                              disabled={
                                endpointsPage >=
                                Math.ceil(totalEndpoints / pageSize)
                              }
                              className="bg-[#1F1F1F] text-[#EEEEEE] border-[#757575] hover:bg-[#2A2A2A] hover:border-[#EEEEEE]"
                            >
                              Next
                            </Button>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="text-center py-[2rem]">
                        <Text_12_400_757575>
                          No deployments found
                        </Text_12_400_757575>
                      </div>
                    )}
                  </>
                )}
              </Panel>

              {/* Tools Section */}
              {groupedDeployments.tools &&
                groupedDeployments.tools.length > 0 && (
                  <Panel
                    header={
                      <div className="flex items-center gap-[0.5rem]">
                        <Text_14_600_FFFFFF>Tools</Text_14_600_FFFFFF>
                        <Text_12_400_757575>
                          ({groupedDeployments.tools.length})
                        </Text_12_400_757575>
                      </div>
                    }
                    key="tools"
                    className="border-none mb-[1rem] !bg-transparent"
                    style={{ backgroundColor: "transparent" }}
                  >
                    <div className="space-y-0">
                      {groupedDeployments.tools.map(renderDeploymentItem)}
                    </div>
                  </Panel>
                )}

              {/* Agents Section */}
              {groupedDeployments.agents &&
                groupedDeployments.agents.length > 0 && (
                  <Panel
                    header={
                      <div className="flex items-center gap-[0.5rem]">
                        <Text_14_600_FFFFFF>Agents</Text_14_600_FFFFFF>
                        <Text_12_400_757575>
                          ({groupedDeployments.agents.length})
                        </Text_12_400_757575>
                      </div>
                    }
                    key="agents"
                    className="border-none mb-[1rem] !bg-transparent"
                    style={{ backgroundColor: "transparent" }}
                  >
                    <div className="space-y-0">
                      {groupedDeployments.agents.map(renderDeploymentItem)}
                    </div>
                  </Panel>
                )}
            </Collapse>

            {/* No Results - Only show if all sections have no data */}
            {!endpointsLoading &&
              (!endPoints || endPoints.length === 0) &&
              (!groupedDeployments.tools ||
                groupedDeployments.tools.length === 0) &&
              (!groupedDeployments.agents ||
                groupedDeployments.agents.length === 0) && (
                <div className="text-center py-[2rem]">
                  <Text_12_400_757575>
                    No deployments found matching your search
                  </Text_12_400_757575>
                </div>
              )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
