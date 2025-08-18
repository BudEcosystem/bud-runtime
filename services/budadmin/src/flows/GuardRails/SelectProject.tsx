import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Image } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";

interface Project {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  deploymentCount?: number;
}

export default function SelectProject() {
  const { openDrawerWithStep } = useDrawer();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedProject, setSelectedProject] = useState<string>("");

  // Mock project data - would typically come from API
  const projects: Project[] = [
    {
      id: "proj-1",
      name: "Project Name 1",
      description: "Production AI Services",
      icon: "🚀",
      deploymentCount: 5
    },
    {
      id: "proj-2",
      name: "Project Name 2",
      description: "Development Environment",
      icon: "🔧",
      deploymentCount: 3
    },
    {
      id: "proj-3",
      name: "Project Name 3",
      description: "Testing and QA",
      icon: "🧪",
      deploymentCount: 2
    },
    {
      id: "proj-4",
      name: "AI Research Lab",
      description: "Experimental Models",
      icon: "🔬",
      deploymentCount: 8
    },
    {
      id: "proj-5",
      name: "Customer Portal",
      description: "Client-facing Services",
      icon: "👥",
      deploymentCount: 4
    },
  ];

  const handleBack = () => {
    openDrawerWithStep("deployment-types");
  };

  const handleNext = () => {
    if (!selectedProject) {
      errorToast("Please select a project");
      return;
    }
    // Move to deployment selection
    openDrawerWithStep("select-deployment");
  };

  const handleProjectSelect = (projectId: string) => {
    setSelectedProject(projectId);
  };

  const getFilteredProjects = () => {
    if (!searchTerm) return projects;

    return projects.filter(project =>
      project.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      project.description?.toLowerCase().includes(searchTerm.toLowerCase())
    );
  };

  const filteredProjects = getFilteredProjects();

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Next"
      disableNext={!selectedProject}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Project"
            description="Select the project where you would like deploy your Guardrail."
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

            {/* Project List */}
            <div className="space-y-0">
              {filteredProjects.map((project, index) => (
                <div
                  key={project.id}
                  onClick={() => handleProjectSelect(project.id)}
                  className={`pt-[1.05rem] pb-[.8rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] flex-row flex hover:bg-[#FFFFFF08] transition-all ${
                    index === 0 ? "border-t-[#1F1F1F]" : ""
                  } ${
                    selectedProject === project.id
                      ? "border-y-[#965CDE] bg-[#965CDE10]"
                      : "border-y-[#1F1F1F] hover:border-[#757575]"
                  }`}
                >
                  <div className="flex items-center justify-between w-full">
                    <div className="flex items-center gap-[1rem]">
                      {/* Project Icon */}
                      <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center shrink-0">
                        <span className="text-[1.2rem]">{project.icon}</span>
                      </div>

                      {/* Project Details */}
                      <div className="flex flex-col">
                        <Text_14_400_EEEEEE className="mb-[0.25rem]">
                          {project.name}
                        </Text_14_400_EEEEEE>
                        {project.description && (
                          <Text_12_400_757575>
                            {project.description}
                          </Text_12_400_757575>
                        )}
                      </div>
                    </div>

                    {/* Selection Indicator */}
                    <div className="flex items-center gap-[0.75rem]">
                      {project.deploymentCount && (
                        <Text_12_400_757575>
                          {project.deploymentCount} deployments
                        </Text_12_400_757575>
                      )}
                      <Checkbox
                        checked={selectedProject === project.id}
                        className="AntCheckbox pointer-events-none"
                      />
                    </div>
                  </div>
                </div>
              ))}

              {filteredProjects.length === 0 && (
                <div className="text-center py-[2rem]">
                  <Text_12_400_757575>No projects found matching your search</Text_12_400_757575>
                </div>
              )}
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
