"use client";

import React from "react";
import { Select, Button, Typography } from "antd";
import { Icon } from "@iconify/react/dist/iconify.js";
import { useProject } from "@/context/projectContext";
import { PlusOutlined } from "@ant-design/icons";

const { Text } = Typography;

interface ProjectSelectorProps {
  onCreateProject?: () => void;
  size?: "small" | "middle" | "large";
  className?: string;
}

const ProjectSelector: React.FC<ProjectSelectorProps> = ({
  onCreateProject,
  size = "middle",
  className = "",
}) => {
  const { currentProject, projects, setCurrentProject } = useProject();

  const activeProjects = projects.filter((p) => p.status === "active");

  const handleProjectChange = (projectId: string) => {
    const project = projects.find((p) => p.id === projectId);
    setCurrentProject(project || null);
  };

  const formatProjectOption = (project: any) => ({
    value: project.id,
    label: (
      <div className="flex items-center gap-3 py-1">
        <div
          className="w-6 h-6 rounded flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: project.color }}
        >
          <Icon icon="ph:folder" className="text-white text-sm" />
        </div>
        <div className="flex-1 min-w-0">
          <Text className="text-bud-text-primary font-medium text-sm line-clamp-1">
            {project.name}
          </Text>
          <Text className="text-bud-text-disabled text-xs line-clamp-1">
            {project.project_type === "client_app"
              ? "Client App"
              : "Existing App"}
          </Text>
        </div>
      </div>
    ),
    project, // Store the full project object for easy access
  });

  const projectOptions = activeProjects.map(formatProjectOption);

  // Add "Create New Project" option
  if (onCreateProject) {
    projectOptions.push({
      value: "create_new",
      label: (
        <div className="flex items-center gap-3 py-1 text-bud-purple hover:text-bud-purple-hover">
          <div className="w-6 h-6 rounded border border-bud-purple border-dashed flex items-center justify-center flex-shrink-0">
            <PlusOutlined className="text-bud-purple text-xs" />
          </div>
          <Text className="text-bud-purple font-medium text-sm">
            Create New Project
          </Text>
        </div>
      ),
      project: null,
    });
  }

  const currentProjectFormatted = currentProject
    ? formatProjectOption(currentProject)
    : null;

  return (
    <div className={`project-selector ${className}`}>
      <Select
        value={currentProject?.id || undefined}
        onChange={(value) => {
          if (value === "create_new" && onCreateProject) {
            onCreateProject();
          } else {
            handleProjectChange(value);
          }
        }}
        options={projectOptions}
        placeholder={
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 rounded border border-bud-border border-dashed flex items-center justify-center">
              <Icon
                icon="ph:folder"
                className="text-bud-text-disabled text-sm"
              />
            </div>
            <Text className="text-bud-text-disabled text-sm">
              Select Project
            </Text>
          </div>
        }
        size={size}
        className="w-full h-auto"
        popupRender={(menu) => (
          <div className="bg-bud-bg-secondary border border-bud-border rounded-lg shadow-lg">
            {activeProjects.length === 0 ? (
              <div className="p-4 text-center">
                <Icon
                  icon="ph:folder-plus"
                  className="text-2xl text-bud-text-disabled mb-2"
                />
                <Text className="text-bud-text-muted text-sm block mb-3">
                  No active projects found
                </Text>
                {onCreateProject && (
                  <Button
                    type="primary"
                    size="small"
                    icon={<PlusOutlined />}
                    className="bg-bud-purple border-bud-purple hover:bg-bud-purple-hover"
                    onClick={onCreateProject}
                  >
                    Create First Project
                  </Button>
                )}
              </div>
            ) : (
              <>
                <div className="p-3 border-b border-bud-border bg-bud-bg-secondary">
                  <Text className="text-bud-text-disabled text-xs uppercase tracking-wider">
                    Active Projects ({activeProjects.length})
                  </Text>
                </div>
                <div className="bg-bud-bg-secondary">{menu}</div>
              </>
            )}
          </div>
        )}
        popupMatchSelectWidth={false}
        classNames={{
          popup: {
            root: "project-selector-dropdown",
          },
        }}
      />

      {currentProject && (
        <div className="mt-2 text-xs text-bud-text-disabled">
          {currentProject.resources.api_keys} keys •{" "}
          {currentProject.resources.batches} batches •{" "}
          {currentProject.resources.logs.toLocaleString()} logs
        </div>
      )}
    </div>
  );
};

export default ProjectSelector;
