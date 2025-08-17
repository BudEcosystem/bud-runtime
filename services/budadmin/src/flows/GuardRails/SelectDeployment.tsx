import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Collapse } from "antd";
import { SearchOutlined, RightOutlined, DownOutlined } from "@ant-design/icons";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

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
  const [expandedSections, setExpandedSections] = useState<string[]>(["models", "routes", "tools", "agents"]);

  // Mock deployment data - would typically come from API
  const deployments: Deployment[] = [
    // Models
    {
      id: "model-1",
      name: "GPT-4 Production",
      type: "model",
      description: "Main production LLM endpoint",
      status: "Active",
      icon: "🤖"
    },
    {
      id: "model-2",
      name: "Claude-3 Staging",
      type: "model",
      description: "Staging environment for Claude",
      status: "Active",
      icon: "🧠"
    },
    {
      id: "model-3",
      name: "Llama-2 Dev",
      type: "model",
      description: "Development Llama model",
      status: "Active",
      icon: "🦙"
    },

    // Routes
    {
      id: "route-1",
      name: "API Gateway Main",
      type: "route",
      description: "Primary API routing endpoint",
      status: "Active",
      icon: "🔀"
    },
    {
      id: "route-2",
      name: "Load Balancer",
      type: "route",
      description: "Traffic distribution route",
      status: "Active",
      icon: "⚖️"
    },

    // Tools
    {
      id: "tool-1",
      name: "Code Interpreter",
      type: "tool",
      description: "Python code execution tool",
      status: "Active",
      icon: "🔧"
    },
    {
      id: "tool-2",
      name: "Web Search Tool",
      type: "tool",
      description: "Internet search capability",
      status: "Active",
      icon: "🔍"
    },
    {
      id: "tool-3",
      name: "Database Query Tool",
      type: "tool",
      description: "SQL database access",
      status: "Active",
      icon: "💾"
    },

    // Agents
    {
      id: "agent-1",
      name: "Customer Support Agent",
      type: "agent",
      description: "Automated support assistant",
      status: "Active",
      icon: "👤"
    },
    {
      id: "agent-2",
      name: "Research Assistant",
      type: "agent",
      description: "Research and analysis agent",
      status: "Active",
      icon: "📚"
    },
  ];

  const handleBack = () => {
    openDrawerWithStep("select-project");
  };

  const handleNext = () => {
    if (!selectedDeployment) {
      errorToast("Please select a deployment");
      return;
    }
    // Move to probe settings
    openDrawerWithStep("probe-settings");
  };

  const handleDeploymentSelect = (deploymentId: string) => {
    setSelectedDeployment(deploymentId);
  };

  const getFilteredDeployments = () => {
    if (!searchTerm) return deployments;

    return deployments.filter(deployment =>
      deployment.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      deployment.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      deployment.type.toLowerCase().includes(searchTerm.toLowerCase())
    );
  };

  const groupedDeployments = getFilteredDeployments().reduce((acc, deployment) => {
    const key = deployment.type + 's';
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(deployment);
    return acc;
  }, {} as Record<string, Deployment[]>);

  const renderDeploymentItem = (deployment: Deployment) => (
    <div
      key={deployment.id}
      onClick={() => handleDeploymentSelect(deployment.id)}
      className={`pt-[1.05rem] pb-[.8rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] flex-row flex hover:bg-[#FFFFFF08] transition-all ${
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
            {deployment.description && (
              <Text_12_400_757575>
                {deployment.description}
              </Text_12_400_757575>
            )}
          </div>
        </div>

        {/* Selection Indicator */}
        <div className="flex items-center gap-[0.75rem]">
          {deployment.status && (
            <span className="px-[0.5rem] py-[0.25rem] bg-[#52C41A20] border border-[#52C41A] rounded-[4px]">
              <Text_12_400_757575 className="text-[#52C41A]">
                {deployment.status}
              </Text_12_400_757575>
            </span>
          )}
          <Checkbox
            checked={selectedDeployment === deployment.id}
            onChange={() => handleDeploymentSelect(deployment.id)}
            className="AntCheckbox"
          />
        </div>
      </div>
    </div>
  );

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
      disableNext={!selectedDeployment}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Deployment"
            description="Select from the available deployment to which you would like to add the Guardrail to."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Search Bar */}
            <div className="mb-[1.5rem]">
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
              className="bg-transparent border-none [&_.ant-collapse-item]:!bg-transparent [&_.ant-collapse-header]:!bg-transparent [&_.ant-collapse-header]:!border-none [&_.ant-collapse-content]:!bg-transparent [&_.ant-collapse-content-box]:!bg-transparent [&_.ant-collapse-item]:!border-none [&_.ant-collapse-content]:!border-none"
              style={{ backgroundColor: "transparent" }}
              bordered={false}
            >
              {/* Models Section */}
              {groupedDeployments.models && groupedDeployments.models.length > 0 && (
                <Panel
                  header={
                    <div className="flex items-center gap-[0.5rem]">
                      <Text_14_600_FFFFFF>Models</Text_14_600_FFFFFF>
                      <Text_12_400_757575>({groupedDeployments.models.length})</Text_12_400_757575>
                    </div>
                  }
                  key="models"
                  className="border-none mb-[1rem] !bg-transparent"
                  style={{ backgroundColor: "transparent" }}
                >
                  <div className="space-y-0">
                    {groupedDeployments.models.map(renderDeploymentItem)}
                  </div>
                </Panel>
              )}

              {/* Routes Section */}
              {groupedDeployments.routes && groupedDeployments.routes.length > 0 && (
                <Panel
                  header={
                    <div className="flex items-center gap-[0.5rem]">
                      <Text_14_600_FFFFFF>Routes</Text_14_600_FFFFFF>
                      <Text_12_400_757575>({groupedDeployments.routes.length})</Text_12_400_757575>
                    </div>
                  }
                  key="routes"
                  className="border-none mb-[1rem] !bg-transparent"
                  style={{ backgroundColor: "transparent" }}
                >
                  <div className="space-y-0">
                    {groupedDeployments.routes.map(renderDeploymentItem)}
                  </div>
                </Panel>
              )}

              {/* Tools Section */}
              {groupedDeployments.tools && groupedDeployments.tools.length > 0 && (
                <Panel
                  header={
                    <div className="flex items-center gap-[0.5rem]">
                      <Text_14_600_FFFFFF>Tools</Text_14_600_FFFFFF>
                      <Text_12_400_757575>({groupedDeployments.tools.length})</Text_12_400_757575>
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
              {groupedDeployments.agents && groupedDeployments.agents.length > 0 && (
                <Panel
                  header={
                    <div className="flex items-center gap-[0.5rem]">
                      <Text_14_600_FFFFFF>Agents</Text_14_600_FFFFFF>
                      <Text_12_400_757575>({groupedDeployments.agents.length})</Text_12_400_757575>
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

            {/* No Results */}
            {Object.keys(groupedDeployments).length === 0 && (
              <div className="text-center py-[2rem]">
                <Text_12_400_757575>No deployments found matching your search</Text_12_400_757575>
              </div>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
