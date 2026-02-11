import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Spin, Button, Popover } from "antd";
import { SearchOutlined } from "@ant-design/icons";
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
    isStandaloneDeployment,
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


  const handleBack = () => {
    openDrawerWithStep("deployment-types");
  };

  const handleNext = async () => {
    if (!selectedDeployment) {
      errorToast("Please select a deployment");
      return;
    }

    try {
      // Get all state from store
      const state = useGuardrails.getState();
      const { currentWorkflow, selectedProvider, selectedProject: projectFromStore, selectedProbes } = state;

      // Build the complete payload with all required fields
      const payload: any = {
        step_number: 9,
        endpoint_ids: [selectedDeployment], // Send as array per new requirement
        trigger_workflow: false,
      };

      // REQUIRED: Include workflow_id
      if (currentWorkflow?.workflow_id) {
        payload.workflow_id = currentWorkflow.workflow_id;
      } else {
        console.error("Missing workflow_id - this is required!");
      }

      // REQUIRED: Include provider data from previous steps
      // Use from selectedProvider first, then fallback to currentWorkflow
      payload.provider_type = selectedProvider?.provider_type || currentWorkflow?.provider_type || "bud";
      payload.provider_id = selectedProvider?.id || currentWorkflow?.provider_id;

      if (!payload.provider_id) {
        console.error("Missing provider_id - this is required!");
      }

      // REQUIRED: Include probe selections from previous steps
      // Check multiple sources for probe_selections
      let probeSelections = null;

      // Priority 1: Check currentWorkflow.probe_selections
      if (currentWorkflow?.probe_selections && currentWorkflow.probe_selections.length > 0) {
        probeSelections = currentWorkflow.probe_selections;
        console.log("Found probe_selections in currentWorkflow");
      }
      // Priority 2: Check currentWorkflow.workflow_data
      else if (currentWorkflow?.workflow_data?.probe_selections && currentWorkflow.workflow_data.probe_selections.length > 0) {
        probeSelections = currentWorkflow.workflow_data.probe_selections;
        console.log("Found probe_selections in currentWorkflow.workflow_data");
      }
      // Priority 3: Check if it's nested in the response
      else if (currentWorkflow?.data?.probe_selections && currentWorkflow.data.probe_selections.length > 0) {
        probeSelections = currentWorkflow.data.probe_selections;
        console.log("Found probe_selections in currentWorkflow.data");
      }
      // Priority 4: Try to reconstruct from selectedProbes in store
      else if (selectedProbes && selectedProbes.length > 0) {
        console.log("Reconstructing probe_selections from selectedProbes in store");
        probeSelections = selectedProbes.map((probe: any) => {
          // Check if probe has rules information
          if (probe.rules && Array.isArray(probe.rules)) {
            return {
              id: probe.id,
              rules: probe.rules
            };
          }
          // Otherwise just include the probe id
          return { id: probe.id };
        });
      }

      // CRITICAL: probe_selections is absolutely required
      if (probeSelections && probeSelections.length > 0) {
        payload.probe_selections = probeSelections;
        console.log("Successfully added probe_selections to payload");
      } else {
        console.error("CRITICAL ERROR: probe_selections is missing!");
        console.error("currentWorkflow:", currentWorkflow);
        console.error("selectedProbes:", selectedProbes);

        // As a last resort, check if we at least have probe IDs somewhere
        errorToast("Missing probe selections. Please go back and select probes again.");
        return; // Don't proceed without probe_selections
      }

      // REQUIRED: Include is_standalone from the store (set in DeploymentTypes step)
      payload.is_standalone = isStandaloneDeployment;

      // REQUIRED: Include project_id from previous step
      const projectId = selectedProject?.project?.id || selectedProject?.id ||
                       projectFromStore?.project?.id || projectFromStore?.id ||
                       currentWorkflow?.project_id;
      if (projectId) {
        payload.project_id = projectId;
      } else {
        console.error("Missing project_id - this is required!");
      }

      console.log("=== FINAL PAYLOAD FOR STEP 5 ===");
      console.log("workflow_id:", payload.workflow_id);
      console.log("step_number:", payload.step_number);
      console.log("provider_type:", payload.provider_type);
      console.log("provider_id:", payload.provider_id);
      console.log("probe_selections:", JSON.stringify(payload.probe_selections, null, 2));
      console.log("is_standalone:", payload.is_standalone);
      console.log("project_id:", payload.project_id);
      console.log("endpoint_ids:", payload.endpoint_ids);
      console.log("================================");

      // Update workflow with complete data and wait for response
      const success = await updateWorkflow(payload);

      // Only navigate to next step if API call was successful
      if (success) {
        // Store the selected deployment in the guardrails store
        setSelectedDeploymentInStore(selectedDeploymentData);
        // Move to probe settings
        openDrawerWithStep("probe-settings");
      }
      // If not successful, stay on current page (error toast is shown by updateWorkflow)
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

            {/* Deployments Section */}
            <div className="mb-[1rem]">
              <div className="flex items-center gap-[0.5rem] px-[1.35rem] mb-[1rem]">
                <Text_14_600_FFFFFF>Deployments</Text_14_600_FFFFFF>
                <Text_12_400_757575>
                  ({totalEndpoints || 0})
                </Text_12_400_757575>
              </div>
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
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
