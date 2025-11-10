import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Checkbox, Input, Spin } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import { useProjects } from "src/hooks/useProjects";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "@/components/ui/text";
import { usePromptsAgents } from "@/stores/usePromptsAgents";
import { useAddAgent } from "@/stores/useAddAgent";
import { useRouter } from "next/router";

export default function SelectProject() {
  const router = useRouter();
  const { openDrawerWithStep } = useDrawer();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [selectedProjectData, setSelectedProjectData] = useState<any>(null);

  // Use the projects hook to fetch actual project data
  const { projects, loading, getProjects } = useProjects();

  // Use prompts agents store to set project filter
  const { setProjectId } = usePromptsAgents();

  // Use the Add Agent store for workflow management
  const {
    createWorkflow,
    setSelectedProject: setStoreSelectedProject,
    loading: workflowLoading
  } = useAddAgent();

  // Fetch projects on component mount and when search changes
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      getProjects(1, 50, searchTerm || undefined);
    }, 300); // Debounce search

    return () => clearTimeout(delayDebounceFn);
  }, [searchTerm]);

  const handleNext = async () => {
    if (!selectedProject || !selectedProjectData) {
      errorToast("Please select a project");
      return;
    }

    try {
      // Store selected project in prompts agents store for filtering
      setProjectId(selectedProject);

      // Store selected project in Add Agent store
      setStoreSelectedProject(selectedProjectData.project || selectedProjectData);

      // Create or update the workflow with the selected project
      const response = await createWorkflow(selectedProject);

      if (!response) {
        errorToast("Failed to create agent workflow");
        return;
      }

      // Update URL with workflow ID
      if (response.workflow_id) {
        // Build URL manually to avoid encoding issues
        // Use window.location.pathname to get the actual browser URL (not router.pathname which includes /home)
        const currentPath = window.location.pathname;
        const queryParts: string[] = [];

        // Add all existing query params except 'agent'
        Object.entries(router.query).forEach(([key, value]) => {
          if (key !== 'agent' && value) {
            // Don't encode commas in prompt parameter
            if (key === 'prompt') {
              queryParts.push(`${key}=${value}`);
            } else {
              queryParts.push(`${key}=${encodeURIComponent(String(value))}`);
            }
          }
        });

        // Add new agent param
        queryParts.push(`agent=${response.workflow_id}`);

        // Build the final URL
        const newUrl = queryParts.length > 0
          ? `${currentPath}?${queryParts.join('&')}`
          : currentPath;

        // Use window.history.replaceState to update URL
        window.history.replaceState(
          { ...window.history.state },
          '',
          newUrl
        );

        console.log('Updated URL with workflow ID:', response.workflow_id);
      }

      // Move to next step - Select Type screen (now step 2)
      openDrawerWithStep("add-agent-select-type");

    } catch (error) {
      console.error("Failed to select project:", error);
      errorToast("Failed to select project");
    }
  };

  const handleProjectSelect = (project: any) => {
    // Handle nested project structure
    const projectId = project.project?.id || project.id;
    setSelectedProject(projectId);
    setSelectedProjectData(project);
  };

  const handleBack = () => {
    // Since SelectProject is now the first step, we don't have a back navigation
    // This will close the drawer or can be handled differently based on requirements
  };

  return (
    <BudForm
      data={{}}
      onNext={handleNext}
      onBack={handleBack}
      backText=""
      nextText="Next"
      disableNext={!selectedProject || loading || workflowLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Projects"
            description="Select the project to add model"
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
                      key={project.project?.id || project.id || index}
                      onClick={() => handleProjectSelect(project)}
                      className={`pt-[1.05rem] pb-[.8rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] flex-row flex hover:bg-[#FFFFFF08] transition-all ${
                        index === 0 ? "border-t-[#1F1F1F]" : ""
                      } ${
                        selectedProject === (project.project?.id || project.id)
                          ? "border-y-[#965CDE] bg-[#965CDE10]"
                          : "border-y-[#1F1F1F] hover:border-[#757575]"
                      }`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-[1rem]">
                          {/* Project Icon */}
                          <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center shrink-0">
                            <span className="text-[1.2rem]">
                              {project.project.icon &&
                              project.project.icon != "string"
                                ? project.project.icon
                                : "📁"}
                            </span>
                          </div>

                          {/* Project Details */}
                          <div className="flex flex-col">
                            <Text_14_400_EEEEEE className="mb-[0.25rem]">
                              {project.project.name}
                            </Text_14_400_EEEEEE>
                            {project.project.description && (
                              <Text_12_400_757575 className="line-clamp-1">
                                {project.project.description}
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
                            checked={selectedProject === project.project.id}
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
