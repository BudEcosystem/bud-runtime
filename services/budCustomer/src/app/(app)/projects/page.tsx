"use client";
import React, { useState, useEffect, useCallback, useMemo } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Card, Row, Col, Flex, Input, Dropdown, Button } from "antd";
import { Typography } from "antd";
import { PlusOutlined, MoreOutlined } from "@ant-design/icons";
import { PrimaryButton } from "@/components/ui/button";
import { Icon } from "@iconify/react/dist/iconify.js";
import dayjs from "dayjs";
import { type Project as ContextProject } from "@/context/projectContext";
import { useProjects } from "@/hooks/useProjects";
import { useDrawer } from "@/hooks/useDrawer";
import BudDrawer from "@/components/ui/bud/drawer/BudDrawer";

const { Text, Title } = Typography;

// Separate component for project card to prevent re-renders
const ProjectCard = React.memo(({
  project,
  onDelete
}: {
  project: ContextProject;
  onDelete: (project: ContextProject) => void;
}) => {
  // Handle menu item clicks
  const handleMenuClick = useCallback((e: any) => {
    e.domEvent?.stopPropagation?.();

    switch (e.key) {
      case 'delete':
        onDelete(project);
        break;
    }
  }, [project, onDelete]);

  // Static menu items without onClick handlers - Edit removed temporarily
  const menuItems = useMemo(() => [
    {
      key: "delete",
      label: "Delete",
      icon: <Icon icon="ph:trash" className="text-bud-error" />,
      danger: true,
      className: "hover:!bg-bud-bg-tertiary text-bud-error",
    },
  ], []);

  return (
    <Card
      className="h-full bg-bud-bg-secondary border-bud-border hover:border-bud-purple hover:shadow-lg transition-all duration-300 cursor-pointer overflow-hidden"
      styles={{ body: { padding: 0 } }}
    >
      <div className="p-6 mb-20">
        {/* Header with Icon and Actions */}
        <div className="flex items-start justify-between mb-6">
          <div
            className="w-12 h-12 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: project.color }}
          >
            <Icon
              icon="ph:folder"
              className="text-white text-[1.5rem]"
            />
          </div>
          <div className="flex items-center gap-2">
            <Text className="text-bud-text-disabled text-[12px]">
              {dayjs(project.updated_at).format("DD MMM")}
            </Text>
            <Dropdown
              menu={{
                items: menuItems,
                onClick: handleMenuClick,
                className: "!bg-bud-bg-secondary !border-bud-border",
              }}
              trigger={["click"]}
              placement="bottomRight"
              overlayClassName="bud-dropdown-menu"
            >
              <Button
                type="text"
                icon={<MoreOutlined />}
                className="!text-bud-text-disabled hover:!text-bud-text-primary hover:!bg-bud-bg-tertiary transition-all"
                size="small"
                onClick={(e) => e.stopPropagation()}
              />
            </Dropdown>
          </div>
        </div>

        {/* Project Title */}
        <Text className="text-bud-text-primary text-[19px] font-semibold mb-3 line-clamp-1 block">
          {project.name}
        </Text>

        {/* Description */}
        <Text className="text-bud-text-muted text-[13px] mb-6 line-clamp-2 leading-relaxed block">
          {project.description}
        </Text>
      </div>

      {/* Footer Section */}
      <div className="bg-bud-bg-tertiary px-6 py-4 border-t border-bud-border absolute bottom-0 left-0 w-full">
        <div className="flex items-center gap-2">
          <Icon
            icon="ph:key"
            className="text-bud-text-disabled text-sm"
          />
          <Text className="text-bud-text-primary text-[13px]">
            {project.resources?.api_keys || 0} API Keys
          </Text>
        </div>
      </div>
    </Card>
  );
});

ProjectCard.displayName = "ProjectCard";

export default function ProjectsPage() {
  const { globalProjects, getGlobalProjects, loading, getGlobalProject } =
    useProjects();

  const { openDrawer } = useDrawer();
  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(10);

  // Fetch projects from API on mount
  useEffect(() => {
    getGlobalProjects(currentPage, pageSize, searchTerm);
  }, [currentPage, pageSize, searchTerm, getGlobalProjects]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      getGlobalProjects(1, pageSize, searchTerm);
      setCurrentPage(1);
    }, 500);
    return () => clearTimeout(timer);
  }, [searchTerm, pageSize, getGlobalProjects]);

  // Convert API projects to context format
  const projects: ContextProject[] = globalProjects.map((p) => {
    // Extract the nested project data
    const projectData = p.project;
    const profileColor = p.profile_colors?.[0] || "#965CDE";

    return {
      id: projectData.id,
      name: projectData.name,
      description: projectData.description || "",
      created_at: projectData.created_at,
      updated_at: projectData.modified_at || projectData.created_at,
      user_id: projectData.created_by,
      project_type: projectData.project_type,
      status: "active" as const,
      resources: {
        api_keys: p.credentials_count || 0,
        batches: 0,
        logs: 0,
        models: 0,
      },
      color: profileColor,
    };
  });

  const handleCreateProject = () => {
    openDrawer("new-project", {});
  };

  // Edit project functionality temporarily disabled due to infinite loop issue
  // const handleEditProject = useCallback(async (project: ContextProject) => {
  //   try {
  //     // Fetch the full project data from API
  //     const projectData = globalProjects.find(
  //       (p) => p.project.id === project.id,
  //     );
  //     if (projectData) {
  //       // Set the selected project for editing
  //       await getGlobalProject(project.id);
  //       // Open the edit drawer after project is fetched
  //       setTimeout(() => {
  //         openDrawer("edit-project", {});
  //       }, 100);
  //     }
  //   } catch (error) {
  //     console.error("Failed to open edit project:", error);
  //   }
  // }, [globalProjects, getGlobalProject, openDrawer]);

  const handleDeleteProject = useCallback(async (project: ContextProject) => {
    try {
      // Fetch the full project data from API
      const projectData = globalProjects.find(
        (p) => p.project.id === project.id,
      );
      if (projectData) {
        // Set the selected project for deletion
        await getGlobalProject(project.id);
        // Open the delete drawer after project is fetched
        setTimeout(() => {
          openDrawer("delete-project", {});
        }, 100);
      }
    } catch (error) {
      console.error("Failed to open delete project:", error);
    }
  }, [globalProjects, getGlobalProject, openDrawer]);

  // Filter to only show active projects or all if status is not available
  const activeProjects = projects.filter(
    (p) => !p.status || p.status === "active",
  );

  return (
    <DashboardLayout>
      <div className="boardPageView">
        <div className="boardMainContainer pt-[2.25rem]">
          {/* Header */}
          <Flex
            justify="space-between"
            align="center"
            className="mb-[2rem] pt-[1.5rem] pb-[1rem]"
          >
            <div>
              <Title level={2} className="!text-bud-text-primary !mb-0">
                Projects
              </Title>
              <Text className="text-bud-text-muted text-[14px] mt-[0.5rem] block">
                Organize your AI resources and manage project workflows
              </Text>
            </div>
            <Flex gap={16} align="center">
              <Input
                placeholder="Search projects..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-[280px] text-bud-text-primary placeholder:text-bud-text-disabled"
                prefix={
                  <Icon
                    icon="ph:magnifying-glass"
                    className="text-bud-text-disabled"
                  />
                }
              />
              <PrimaryButton onClick={handleCreateProject}>
                <PlusOutlined className="mr-2" />
                <span>Project</span>
              </PrimaryButton>
            </Flex>
          </Flex>

          {/* Loading State */}
          {loading && activeProjects.length === 0 && (
            <div className="text-center py-16">
              <Icon
                icon="ph:spinner"
                className="text-4xl text-bud-text-disabled mb-4 animate-spin"
              />
              <Text className="text-bud-text-muted block">
                Loading projects...
              </Text>
            </div>
          )}

          {/* Projects */}
          {!loading && activeProjects.length > 0 && (
            <div className="mb-[3rem]">
              <Row gutter={[24, 24]}>
                {activeProjects.map((project) => (
                  <Col key={project.id} xs={24} sm={12} lg={8}>
                    <ProjectCard
                      project={project}
                      onDelete={handleDeleteProject}
                    />
                  </Col>
                ))}
              </Row>
            </div>
          )}

          {/* Empty State */}
          {!loading && activeProjects.length === 0 && (
            <div className="text-center py-16">
              <Icon
                icon="ph:folder-plus"
                className="text-6xl text-bud-text-disabled mb-4"
              />
              <Text className="text-bud-text-primary text-lg mb-2 block">
                No projects found
              </Text>
              <Text className="text-bud-text-muted mb-6 block">
                Create your first project to start organizing your AI resources
              </Text>
              <PrimaryButton onClick={handleCreateProject}>
                <PlusOutlined className="mr-2" />
                <span>Create Your First Project</span>
              </PrimaryButton>
            </div>
          )}
        </div>
      </div>
      <BudDrawer />
    </DashboardLayout>
  );
}
