"use client";
import React, { useState, useEffect, useCallback, useMemo } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Card, Row, Col, Flex, Dropdown, Button, Spin, App, Empty } from "antd";
import { Typography } from "antd";
import { PlusOutlined, MoreOutlined } from "@ant-design/icons";
import { PrimaryButton } from "@/components/ui/button";
import { Icon } from "@iconify/react/dist/iconify.js";
import dayjs from "dayjs";
import { type Project as ContextProject } from "@/context/projectContext";
import { useProjects } from "@/hooks/useProjects";
import { useDrawer } from "@/hooks/useDrawer";
import BudDrawer from "@/components/ui/bud/drawer/BudDrawer";
import SearchHeaderInput from "@/flows/components/SearchHeaderInput";
import styles from "./projects.module.scss";
import { motion } from "framer-motion";
import { useEndPoints } from "@/hooks/useEndPoint";
import { openWarning } from "@/components/warningMessage";
import { useOverlay } from "@/context/overlayContext";

const { Text, Title } = Typography;

// Separate component for project card to prevent re-renders
const ProjectCard = React.memo(
  ({
    project,
    onDelete,
    onEdit,
    onClick,
  }: {
    project: ContextProject;
    onDelete: (project: ContextProject) => void;
    onEdit: (project: ContextProject) => void;
    onClick: (project: ContextProject) => void;
  }) => {
    // Handle menu item clicks
    const handleMenuClick = useCallback(
      (e: any) => {
        e.domEvent?.stopPropagation?.();

        switch (e.key) {
          case "edit":
            onEdit(project);
            break;
          case "delete":
            onDelete(project);
            break;
        }
      },
      [project, onEdit, onDelete],
    );

    // Static menu items without onClick handlers
    const menuItems = useMemo(
      () => [
        {
          key: "edit",
          label: "Edit",
          icon: (
            <Icon icon="ph:pencil-simple" className="text-bud-text-primary" />
          ),
          className: "hover:!bg-bud-bg-tertiary",
        },
        {
          key: "delete",
          label: "Delete",
          icon: <Icon icon="ph:trash" className="text-bud-error" />,
          danger: true,
          className: "hover:!bg-bud-bg-tertiary text-bud-error",
        },
      ],
      [],
    );

    return (
      <Card
        className="h-full bg-bud-bg-secondary border-bud-border hover:border-bud-purple hover:shadow-lg transition-all duration-300 cursor-pointer overflow-hidden"
        styles={{ body: { padding: 0 } }}
        onClick={() => onClick(project)}
      >
        <div className="p-6 mb-20">
          {/* Header with Icon and Actions */}
          <div className="flex items-start justify-between mb-6">
            <div
              className="w-12 h-12 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: project.color }}
            >
              <Icon icon="ph:folder" className="text-white text-[1.5rem]" />
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
            <Icon icon="ph:key" className="text-bud-text-disabled text-sm" />
            <Text className="text-bud-text-primary text-[13px]">
              {project.resources?.api_keys || 0} API Keys
            </Text>
          </div>
        </div>
      </Card>
    );
  },
);

ProjectCard.displayName = "ProjectCard";

export default function ProjectsPage() {
  const {
    globalProjects,
    getGlobalProjects,
    loading,
    getGlobalProject,
    deleteProject,
  } = useProjects();

  const { openDrawer } = useDrawer();
  const { getEndPoints, endPointsCount } = useEndPoints();
  const { notification } = App.useApp();
  const { setOverlayVisible } = useOverlay();
  const [searchValue, setSearchValue] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(10);

  // Fetch projects from API on mount
  useEffect(() => {
    getGlobalProjects(currentPage, pageSize, searchValue);
  }, [currentPage, pageSize, searchValue, getGlobalProjects]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      getGlobalProjects(1, pageSize, searchValue);
      setCurrentPage(1);
    }, 500);
    return () => clearTimeout(timer);
  }, [searchValue, pageSize, getGlobalProjects]);

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

  const handleEditProject = useCallback(
    async (project: ContextProject) => {
      try {
        // Fetch the full project data from API
        const projectData = globalProjects.find(
          (p) => p.project.id === project.id,
        );
        if (projectData) {
          // Set the selected project for editing
          await getGlobalProject(project.id);
          // Open the edit drawer after project is fetched
          setTimeout(() => {
            openDrawer("edit-project", {});
          }, 100);
        }
      } catch (error) {
        console.error("Failed to open edit project:", error);
      }
    },
    [globalProjects, getGlobalProject, openDrawer],
  );

  const handleProjectClick = useCallback(
    async (project: ContextProject) => {
      try {
        // Set the selected project for viewing details
        await getGlobalProject(project.id);
        // Open the view drawer after project is fetched
        setTimeout(() => {
          openDrawer("view-project-details", {});
        }, 100);
      } catch (error) {
        console.error("Failed to open project details:", error);
      }
    },
    [getGlobalProject, openDrawer],
  );

  const handleDeleteProject = useCallback(
    async (project: ContextProject) => {
      console.log("Delete clicked for project:", project);

      try {
        // Set the selected project for deletion
        await getGlobalProject(project.id);

        // Get endpoints count for this project
        await getEndPoints({ id: project.id, page: 1, limit: 1 });

        // Set overlay visible first
        setOverlayVisible(true);

        // Wait a bit for the state to update
        setTimeout(() => {
          const count = endPointsCount || 0;
          console.log("Endpoints count:", count);

          let description =
            count > 0
              ? "This project has active resources. Please pause or delete all resources before deleting the project."
              : "You can safely delete this project.";

          let title =
            count > 0
              ? `You're not allowed to delete "${project.name}"`
              : `You're about to delete "${project.name}"`;

          const updateNotificationMessage = openWarning({
            title: title,
            description: description,
            deleteDisabled: count > 0,
            notification: notification,
            onDelete: () => {
              deleteProject(project.id, null)
                .then((result) => {
                  if (result) {
                    setOverlayVisible(false);
                    notification.destroy(`${title}-delete-notification`);
                    // Refresh the project list
                    getGlobalProjects(currentPage, pageSize, searchValue);
                  } else {
                    updateNotificationMessage("An unknown error occurred.");
                    setOverlayVisible(false);
                  }
                })
                .catch((error) => {
                  console.error("Error deleting project:", error);
                  updateNotificationMessage("An unknown error occurred.");
                  setOverlayVisible(false);
                });
            },
            onCancel: () => {
              setOverlayVisible(false);
            },
          });
        }, 500); // Give time for endpoint count to update
      } catch (error) {
        console.error("Failed to handle delete project:", error);
        setOverlayVisible(false);
      }
    },
    [
      notification,
      getGlobalProject,
      getEndPoints,
      endPointsCount,
      deleteProject,
      setOverlayVisible,
      currentPage,
      pageSize,
      searchValue,
      getGlobalProjects,
    ],
  );

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
              <SearchHeaderInput
                placeholder="Search projects..."
                searchValue={searchValue}
                setSearchValue={(value) => {
                  setSearchValue(value);
                  setCurrentPage(1);
                }}
              />
              <PrimaryButton onClick={handleCreateProject}>
                <PlusOutlined className="mr-2" />
                <span>Project</span>
              </PrimaryButton>
            </Flex>
          </Flex>

          {/* Loading State */}
          {loading && activeProjects.length === 0 && (
            <div className="flex justify-center items-center">
              <div className="w-full flex flex-col gap-6">
                {[0, 1].map((row) => (
                  <div key={row} className="flex gap-6">
                    {[0, 1, 2].map((col) => (
                      <div
                        key={col}
                        className="flex-1 h-[200px] rounded-lg bg-bud-bg-secondary border-bud-border relative overflow-hidden"
                        style={{ minWidth: 0 }}
                      >
                        {/* Animated light pass */}
                        <div className="absolute inset-0 pointer-events-none">
                          <motion.div
                            className={styles.loadingBar}
                            initial={{ width: "0%" }}
                            animate={{ width: "100%" }}
                            transition={{
                              duration: 1.5,
                              ease: "easeInOut",
                              repeat: Infinity,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Projects */}
          {activeProjects.length > 0 && (
            <div className="mb-[3rem]">
              <Row gutter={[24, 24]}>
                {activeProjects.map((project) => (
                  <Col key={project.id} xs={24} sm={12} lg={8}>
                    <ProjectCard
                      project={project}
                      onDelete={handleDeleteProject}
                      onEdit={handleEditProject}
                      onClick={handleProjectClick}
                    />
                  </Col>
                ))}
              </Row>
            </div>
          )}

          {/* Loading indicator for pagination/search */}
          {loading && activeProjects.length > 0 && (
            <div className="flex justify-center items-center py-4">
              <Spin />
            </div>
          )}
          {/* Empty State */}
          {!loading && activeProjects.length === 0 && (
            // <div className="text-center py-16">
            //   <Text className="text-bud-text-primary text-lg mb-2 block">
            //     No projects found
            //   </Text>
            // </div>
            <Empty
              description={
                <Text className="text-bud-text-muted">
                  {searchValue
                    ? "No projects found"
                    : "No projects available"}
                </Text>
              }
              className="mt-16"
            />
          )}
        </div>
      </div>
      <BudDrawer />
    </DashboardLayout>
  );
}
