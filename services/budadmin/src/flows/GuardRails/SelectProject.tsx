import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Spin } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import { useProjects } from "src/hooks/useProjects";
import useGuardrails from "src/hooks/useGuardrails";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "@/components/ui/text";
import Tags from "../components/DrawerTags";

export default function SelectProject() {
  console.log("Rendering SelectProject component");
  const { openDrawerWithStep } = useDrawer();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [selectedProjectData, setSelectedProjectData] = useState<any>(null);

  // Use the projects hook to fetch actual project data
  const { projects, loading, getProjects } = useProjects();

  // Use guardrails hook to store selected project and update workflow
  const {
    setSelectedProject: setSelectedProjectInStore,
    updateWorkflow,
    workflowLoading,
    isStandaloneDeployment,
  } = useGuardrails();

  // Fetch projects on component mount and when search changes
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      getProjects(1, 50, searchTerm || undefined);
    }, 300); // Debounce search

    return () => clearTimeout(delayDebounceFn);
  }, [searchTerm]);

  const handleBack = () => {
    openDrawerWithStep("deployment-types");
  };

  const handleNext = async () => {
    if (!selectedProject || !selectedProjectData) {
      errorToast("Please select a project");
      return;
    }

    try {
      // Get current state BEFORE async operations
      const { currentWorkflow, selectedProvider } = useGuardrails.getState();

      // Build the complete payload
      const payload: any = {
        step_number: 4, // Project selection is step 4
        project_id: selectedProject,
        trigger_workflow: false,
      };

      if (currentWorkflow?.workflow_id) {
        payload.workflow_id = currentWorkflow.workflow_id;
      }

      // Include provider data from previous steps
      if (selectedProvider?.provider_type) {
        payload.provider_type = selectedProvider.provider_type;
      }
      if (selectedProvider?.id) {
        payload.provider_id = selectedProvider.id;
      }

      // Include probe selections from previous steps
      if (currentWorkflow?.probe_selections) {
        payload.probe_selections = currentWorkflow.probe_selections;
      }

      // Include is_standalone from the store (set in DeploymentTypes step)
      payload.is_standalone = isStandaloneDeployment;

      // Update workflow with complete data
      await updateWorkflow(payload);

      // Save selected project to guardrails store
      setSelectedProjectInStore(selectedProjectData);

      // Check if this is a standalone guardrail endpoint (skip deployment selection)
      // Use the store flag which was set in DeploymentTypes step
      if (isStandaloneDeployment) {
        // Skip deployment selection for guardrail-endpoint type
        openDrawerWithStep("probe-settings");
      } else {
        // Normal flow - go to deployment selection
        openDrawerWithStep("select-deployment");
      }
    } catch (error) {
      console.error("Failed to update workflow:", error);
    }
  };

  const handleProjectSelect = (project: any) => {
    // Handle nested project structure
    const projectId = project?.project?.id || project.id;
    setSelectedProject(projectId);
    setSelectedProjectData(project);
  };

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Next"
      disableNext={!selectedProject || workflowLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Project"
            description="Select the project where you would like deploy your Guardrail."
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

            {/* Project List */}
            <div className="space-y-0">
              {loading ? (
                <div className="flex justify-center py-[3rem]">
                  <Spin size="large" />
                </div>
              ) : (
                <>
                  {projects?.map((project, index) => (
                    <div
                      key={project?.project?.id || project.id || index}
                      onClick={() => handleProjectSelect(project)}
                      className={`pt-[1.05rem] pb-[.8rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] flex-row flex hover:bg-[#FFFFFF08] transition-all ${
                        index === 0 ? "border-t-[#1F1F1F]" : ""
                      } ${
                        selectedProject === (project?.project?.id || project.id)
                          ? "border-y-[#965CDE] bg-[#965CDE10]"
                          : "border-y-[#1F1F1F] hover:border-[#757575]"
                      }`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-[1rem]">
                          {/* Project Icon */}
                          <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center shrink-0">
                            <span className="text-[1.2rem]">
                              {project?.project?.icon &&
                              project?.project?.icon != "string"
                                ? project?.project?.icon
                                : "📁"}
                            </span>
                          </div>

                          {/* Project Details */}
                          <div className="flex flex-col">
                            <Text_14_400_EEEEEE className="mb-[0.25rem]">
                              {project?.project?.name}
                            </Text_14_400_EEEEEE>
                            {project?.tags?.length > 0 && (
                              <div className="flex gap-[0.3rem] mb-[0.25rem]">
                                {project?.tags?.map((tag: any, index) => (
                                  <Tags
                                    key={index}
                                    name={tag.name}
                                    color={tag.color || "#757575"}
                                  />
                                ))}
                              </div>
                            )}
                            {project?.project?.description && (
                              <Text_12_400_757575 className="line-clamp-1">
                                {project?.project?.description}
                              </Text_12_400_757575>
                            )}
                          </div>
                        </div>

                        {/* Selection Indicator */}
                        <div className="flex items-center gap-[0.75rem]">
                          {project.endpoints_count !== undefined && (
                            <Text_12_400_757575>
                              {project.endpoints_count} endpoints
                            </Text_12_400_757575>
                          )}
                          <Checkbox
                            checked={selectedProject === project?.project?.id}
                            className="AntCheckbox pointer-events-none"
                          />
                        </div>
                      </div>
                    </div>
                  ))}

                  {(!projects || projects.length === 0) && (
                    <div className="text-center py-[2rem]">
                      <Text_12_400_757575>
                        No projects found matching your search
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
