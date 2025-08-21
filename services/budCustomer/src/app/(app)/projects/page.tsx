"use client";
import React, { useState, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Button,
  Card,
  Row,
  Col,
  Flex,
  Input,
  Dropdown,
} from "antd";
import { Typography } from "antd";
import { PlusOutlined, MoreOutlined } from "@ant-design/icons";
import { Icon } from "@iconify/react/dist/iconify.js";
import dayjs from "dayjs";
import { useProject, type Project as ContextProject } from "@/context/projectContext";
import { useProjects } from "@/hooks/useProjects";
import { useDrawer } from "@/hooks/useDrawer";
import BudDrawer from "@/components/ui/bud/drawer/BudDrawer";

const { Text, Title } = Typography;

// Mock data for projects
const mockProjects: ContextProject[] = [
  {
    id: "proj_001",
    name: "E-commerce AI Assistant",
    description:
      "AI-powered customer service chatbot for e-commerce platform with personalized recommendations and order tracking capabilities.",
    created_at: "2024-01-15T10:30:00Z",
    updated_at: "2024-01-20T14:30:00Z",
    user_id: "user_123",
    project_type: "client_app",
    status: "active",
    resources: {
      api_keys: 3,
      batches: 12,
      logs: 1250,
      models: 2,
    },
    color: "#965CDE",
  },
  {
    id: "proj_002",
    name: "Content Generation Suite",
    description:
      "Automated content generation system for blogs, social media, and marketing materials using advanced language models.",
    created_at: "2024-01-10T08:15:00Z",
    updated_at: "2024-01-19T16:45:00Z",
    user_id: "user_123",
    project_type: "existing_app",
    status: "active",
    resources: {
      api_keys: 5,
      batches: 8,
      logs: 890,
      models: 4,
    },
    color: "#4077E6",
  },
  {
    id: "proj_003",
    name: "Document Analysis Tool",
    description:
      "Enterprise document processing and analysis system with OCR, summarization, and key information extraction.",
    created_at: "2023-12-20T14:00:00Z",
    updated_at: "2024-01-18T12:20:00Z",
    user_id: "user_123",
    project_type: "client_app",
    status: "active",
    resources: {
      api_keys: 2,
      batches: 25,
      logs: 2100,
      models: 3,
    },
    color: "#479D5F",
  },
  {
    id: "proj_004",
    name: "Image Recognition API",
    description:
      "Computer vision API for product categorization and quality control in manufacturing processes.",
    created_at: "2023-11-15T09:30:00Z",
    updated_at: "2024-01-05T10:15:00Z",
    user_id: "user_123",
    project_type: "existing_app",
    status: "inactive",
    resources: {
      api_keys: 1,
      batches: 3,
      logs: 145,
      models: 1,
    },
    color: "#DE9C5C",
  },
  {
    id: "proj_005",
    name: "Voice Assistant Integration",
    description:
      "Smart home voice assistant with natural language processing and IoT device control capabilities.",
    created_at: "2023-10-01T16:00:00Z",
    updated_at: "2023-12-15T14:30:00Z",
    user_id: "user_123",
    project_type: "client_app",
    status: "archived",
    resources: {
      api_keys: 2,
      batches: 1,
      logs: 67,
      models: 2,
    },
    color: "#EC7575",
  },
];

export default function ProjectsPage() {
  const { projects: contextProjects } =
    useProject();
  const {
    globalProjects,
    getGlobalProjects,
    loading,
    deleteProject: apiDeleteProject,
    getGlobalProject
  } = useProjects();

  const { openDrawer } = useDrawer();
  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(10);

  // Fetch projects from API on mount
  useEffect(() => {
    getGlobalProjects(currentPage, pageSize, searchTerm);
  }, [currentPage, pageSize]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      getGlobalProjects(1, pageSize, searchTerm);
      setCurrentPage(1);
    }, 500);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Convert API projects to context format or use mock data
  const projects: ContextProject[] = globalProjects.length > 0
    ? globalProjects.map(p => {
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
            api_keys: p.endpoints_count || 0,
            batches: 0,
            logs: 0,
            models: 0,
          },
          color: profileColor,
        };
      })
    : contextProjects.length > 0
      ? contextProjects
      : mockProjects;


  const handleCreateProject = () => {
    openDrawer("new-project", {});
  };


  const handleEditProject = (project: ContextProject) => {
    try {
      // Fetch the full project data from API
      const projectData = globalProjects.find(p => p.project.id === project.id);
      if (projectData) {
        // Set the selected project for editing
        getGlobalProject(project.id);
        // Open the edit drawer
        openDrawer("edit-project", {});
      }
    } catch (error) {
      console.error("Failed to open edit project:", error);
    }
  };

  const handleDeleteProject = async (projectId: string) => {
    try {
      await apiDeleteProject(projectId, null);
      // Refresh the project list
      getGlobalProjects(currentPage, pageSize, searchTerm);
    } catch (error) {
      console.error("Failed to delete project:", error);
    }
  };



  const getProjectMenuItems = (project: ContextProject) => [
    {
      key: "edit",
      label: "Edit Project",
      icon: <Icon icon="ph:pencil" />,
      onClick: () => handleEditProject(project),
    },
    {
      key: "delete",
      label: "Delete",
      icon: <Icon icon="ph:trash" />,
      danger: true,
      onClick: () => handleDeleteProject(project.id),
    },
  ];


  // Filter to only show active projects or all if status is not available
  const activeProjects = projects.filter((p) => !p.status || p.status === "active");

  return (
    <DashboardLayout>
      <div className="boardPageView">
        <div className="boardMainContainer pt-[2.25rem]">
          {/* Header */}
          <Flex justify="space-between" align="center" className="mb-[2rem]">
            <div>
              <Title level={2} className="!text-bud-text-primary !mb-0">
                Projects
              </Title>
              <Text className="text-bud-text-muted text-[14px] mt-[0.5rem] block">
                Organize your AI resources and manage project workflows
              </Text>
            </div>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              className="bg-bud-purple border-bud-purple hover:bg-bud-purple-hover h-[2.5rem] px-[1.5rem]"
              onClick={handleCreateProject}
            >
              Create Project
            </Button>
          </Flex>

          {/* Search Bar */}
          <div className="mb-[2rem]">
            <Input
              placeholder="Search projects..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="max-w-md"
              prefix={<Icon icon="ph:magnifying-glass" className="text-bud-text-disabled" />}
            />
          </div>

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
                              menu={{ items: getProjectMenuItems(project) }}
                              trigger={["click"]}
                              placement="bottomRight"
                            >
                              <Button
                                type="text"
                                icon={<MoreOutlined />}
                                className="text-bud-text-disabled hover:text-bud-text-primary"
                                size="small"
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
                No projects yet
              </Text>
              <Text className="text-bud-text-muted mb-6 block">
                Create your first project to start organizing your AI resources
              </Text>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                className="bg-bud-purple border-bud-purple hover:bg-bud-purple-hover"
                onClick={handleCreateProject}
              >
                Create Your First Project
              </Button>
            </div>
          )}


        </div>
      </div>
      <BudDrawer />
    </DashboardLayout>
  );
}
