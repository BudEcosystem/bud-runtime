"use client";
import React, { useState, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Button,
  Card,
  Row,
  Col,
  Flex,
  Modal,
  Input,
  Select,
  Dropdown,
  Popconfirm,
  Tag,
} from "antd";
import { Typography } from "antd";
import { PlusOutlined, MoreOutlined } from "@ant-design/icons";
import { Icon } from "@iconify/react/dist/iconify.js";
import dayjs from "dayjs";
import styles from "./projects.module.scss";
import { useProject, type Project } from "@/context/projectContext";

const { Text, Title } = Typography;
const { TextArea } = Input;

// Mock data for projects
const mockProjects: Project[] = [
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
  const { projects, addProject, updateProject, deleteProject, setProjects } =
    useProject();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    project_type: "client_app" as "client_app" | "existing_app",
    color: "#965CDE",
  });

  // Initialize with mock data if no projects exist
  useEffect(() => {
    if (projects.length === 0) {
      setProjects(mockProjects);
    }
  }, [projects.length, setProjects]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "#479D5F";
      case "inactive":
        return "#DE9C5C";
      case "archived":
        return "#757575";
      default:
        return "#B3B3B3";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "active":
        return "ph:play-circle";
      case "inactive":
        return "ph:pause-circle";
      case "archived":
        return "ph:archive";
      default:
        return "ph:circle";
    }
  };

  const getProjectTypeIcon = (type: string) => {
    return type === "client_app" ? "ph:device-mobile" : "ph:cloud";
  };

  const handleCreateProject = () => {
    const newProject: Project = {
      id: `proj_${Date.now()}`,
      name: formData.name,
      description: formData.description,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      user_id: "user_123",
      project_type: formData.project_type,
      status: "active",
      resources: {
        api_keys: 0,
        batches: 0,
        logs: 0,
        models: 0,
      },
      color: formData.color,
    };

    addProject(newProject);
    setShowCreateModal(false);
    setFormData({
      name: "",
      description: "",
      project_type: "client_app",
      color: "#965CDE",
    });
  };

  const handleEditProject = () => {
    if (!selectedProject) return;

    updateProject(selectedProject.id, {
      name: formData.name,
      description: formData.description,
      project_type: formData.project_type,
      color: formData.color,
    });

    setShowEditModal(false);
    setSelectedProject(null);
    setFormData({
      name: "",
      description: "",
      project_type: "client_app",
      color: "#965CDE",
    });
  };

  const handleDeleteProject = (projectId: string) => {
    deleteProject(projectId);
  };

  const openEditModal = (project: Project) => {
    setSelectedProject(project);
    setFormData({
      name: project.name,
      description: project.description,
      project_type: project.project_type,
      color: project.color,
    });
    setShowEditModal(true);
  };

  const getProjectMenuItems = (project: Project) => [
    {
      key: "edit",
      label: "Edit Project",
      icon: <Icon icon="ph:pencil" />,
      onClick: () => openEditModal(project),
    },
    {
      key: "duplicate",
      label: "Duplicate",
      icon: <Icon icon="ph:copy" />,
      onClick: () => console.log("Duplicate project:", project.id),
    },
    {
      type: "divider" as const,
    },
    {
      key: "archive",
      label: project.status === "archived" ? "Unarchive" : "Archive",
      icon: <Icon icon="ph:archive" />,
      onClick: () => {
        const newStatus = project.status === "archived" ? "active" : "archived";
        updateProject(project.id, { status: newStatus });
      },
    },
    {
      key: "delete",
      label: "Delete",
      icon: <Icon icon="ph:trash" />,
      danger: true,
      onClick: () => handleDeleteProject(project.id),
    },
  ];

  const colorOptions = [
    "#965CDE",
    "#4077E6",
    "#479D5F",
    "#DE9C5C",
    "#EC7575",
    "#50C7C7",
    "#F59E0B",
    "#8B5CF6",
  ];

  // Filter projects by status for organization
  const activeProjects = projects.filter((p) => p.status === "active");
  const inactiveProjects = projects.filter((p) => p.status === "inactive");
  const archivedProjects = projects.filter((p) => p.status === "archived");

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
              onClick={() => setShowCreateModal(true)}
            >
              Create Project
            </Button>
          </Flex>

          {/* Stats Cards */}
          <Flex gap={16} className="mb-[2rem]">
            <div className="bg-bud-bg-secondary border border-bud-border rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon
                  icon="ph:play-circle"
                  className="text-[#479D5F] text-[1.25rem]"
                />
                <Text className="text-bud-text-disabled text-[12px]">
                  Active Projects
                </Text>
              </Flex>
              <Text className="text-bud-text-primary text-[24px] font-medium mt-[0.5rem] block">
                {activeProjects.length}
              </Text>
            </div>
            <div className="bg-bud-bg-secondary border border-bud-border rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon
                  icon="ph:archive"
                  className="text-[#DE9C5C] text-[1.25rem]"
                />
                <Text className="text-bud-text-disabled text-[12px]">
                  Total Projects
                </Text>
              </Flex>
              <Text className="text-bud-text-primary text-[24px] font-medium mt-[0.5rem] block">
                {projects.length}
              </Text>
            </div>
            <div className="bg-bud-bg-secondary border border-bud-border rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon icon="ph:key" className="text-[#4077E6] text-[1.25rem]" />
                <Text className="text-bud-text-disabled text-[12px]">
                  Total API Keys
                </Text>
              </Flex>
              <Text className="text-bud-text-primary text-[24px] font-medium mt-[0.5rem] block">
                {projects.reduce((acc, p) => acc + p.resources.api_keys, 0)}
              </Text>
            </div>
            <div className="bg-bud-bg-secondary border border-bud-border rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon
                  icon="ph:stack"
                  className="text-[#965CDE] text-[1.25rem]"
                />
                <Text className="text-bud-text-disabled text-[12px]">
                  Total Batches
                </Text>
              </Flex>
              <Text className="text-bud-text-primary text-[24px] font-medium mt-[0.5rem] block">
                {projects.reduce((acc, p) => acc + p.resources.batches, 0)}
              </Text>
            </div>
          </Flex>

          {/* Active Projects */}
          {activeProjects.length > 0 && (
            <div className="mb-[3rem]">
              <Text className="text-bud-text-primary font-semibold text-[16px] mb-[1.5rem] block">
                Active Projects ({activeProjects.length})
              </Text>
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

                        {/* Status and Type Tags */}
                        <div className="flex items-center gap-2 mb-6">
                          <Tag
                            icon={<Icon icon={getStatusIcon(project.status)} />}
                            color={getStatusColor(project.status)}
                            className="border-0 px-[0.75rem] py-[0.25rem] text-[0.75rem]"
                          >
                            {project.status.charAt(0).toUpperCase() +
                              project.status.slice(1)}
                          </Tag>

                          <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-[var(--bg-tertiary)] text-[var(--text-muted)]">
                            <Icon
                              icon={getProjectTypeIcon(project.project_type)}
                              className="text-xs"
                            />
                            <Text className="text-[12px]">
                              {project.project_type === "client_app"
                                ? "Client App"
                                : "Existing App"}
                            </Text>
                          </div>
                        </div>

                        {/* Resources Stats */}
                        <div className="grid grid-cols-2 gap-3 mb-4">
                          <div className="flex items-center gap-2">
                            <Icon
                              icon="ph:key"
                              className="text-bud-text-disabled text-sm"
                            />
                            <Text className="text-bud-text-muted text-[12px]">
                              {project.resources.api_keys} Keys
                            </Text>
                          </div>
                          <div className="flex items-center gap-2">
                            <Icon
                              icon="ph:stack"
                              className="text-bud-text-disabled text-sm"
                            />
                            <Text className="text-bud-text-muted text-[12px]">
                              {project.resources.batches} Batches
                            </Text>
                          </div>
                          <div className="flex items-center gap-2">
                            <Icon
                              icon="ph:file-text"
                              className="text-bud-text-disabled text-sm"
                            />
                            <Text className="text-bud-text-muted text-[12px]">
                              {project.resources.logs.toLocaleString()} Logs
                            </Text>
                          </div>
                          <div className="flex items-center gap-2">
                            <Icon
                              icon="ph:cpu"
                              className="text-bud-text-disabled text-sm"
                            />
                            <Text className="text-bud-text-muted text-[12px]">
                              {project.resources.models} Models
                            </Text>
                          </div>
                        </div>
                      </div>

                      {/* Footer Section */}
                      <div className="bg-bud-bg-tertiary px-6 py-4 border-t border-bud-border absolute bottom-0 left-0 w-full">
                        <Text className="text-bud-text-disabled text-[12px] mb-1 block">
                          Last Updated
                        </Text>
                        <Text className="text-bud-text-primary text-[13px]">
                          {dayjs(project.updated_at).format(
                            "MMM DD, YYYY HH:mm",
                          )}
                        </Text>
                      </div>
                    </Card>
                  </Col>
                ))}
              </Row>
            </div>
          )}

          {/* Inactive Projects */}
          {inactiveProjects.length > 0 && (
            <div className="mb-[3rem]">
              <Text className="text-bud-text-primary font-semibold text-[16px] mb-[1.5rem] block">
                Inactive Projects ({inactiveProjects.length})
              </Text>
              <Row gutter={[24, 24]}>
                {inactiveProjects.map((project) => (
                  <Col key={project.id} xs={24} sm={12} lg={8}>
                    <Card
                      className="h-full bg-bud-bg-secondary border-bud-border hover:border-bud-purple hover:shadow-lg transition-all duration-300 cursor-pointer overflow-hidden opacity-75"
                      styles={{ body: { padding: 0 } }}
                    >
                      {/* Similar structure as active projects but with opacity */}
                      <div className="p-6">
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

                        <Text className="text-bud-text-primary text-[19px] font-semibold mb-3 line-clamp-1 block">
                          {project.name}
                        </Text>

                        <Text className="text-bud-text-muted text-[13px] mb-6 line-clamp-2 leading-relaxed block">
                          {project.description}
                        </Text>

                        <div className="flex items-center gap-2 mb-6">
                          <Tag
                            icon={<Icon icon={getStatusIcon(project.status)} />}
                            color={getStatusColor(project.status)}
                            className="border-0 px-[0.75rem] py-[0.25rem] text-[0.75rem]"
                          >
                            {project.status.charAt(0).toUpperCase() +
                              project.status.slice(1)}
                          </Tag>

                          <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-bud-bg-tertiary text-bud-text-muted">
                            <Icon
                              icon={getProjectTypeIcon(project.project_type)}
                              className="text-xs"
                            />
                            <Text className="text-[12px]">
                              {project.project_type === "client_app"
                                ? "Client App"
                                : "Existing App"}
                            </Text>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3 mb-4">
                          <div className="flex items-center gap-2">
                            <Icon
                              icon="ph:key"
                              className="text-bud-text-disabled text-sm"
                            />
                            <Text className="text-bud-text-muted text-[12px]">
                              {project.resources.api_keys} Keys
                            </Text>
                          </div>
                          <div className="flex items-center gap-2">
                            <Icon
                              icon="ph:stack"
                              className="text-bud-text-disabled text-sm"
                            />
                            <Text className="text-bud-text-muted text-[12px]">
                              {project.resources.batches} Batches
                            </Text>
                          </div>
                          <div className="flex items-center gap-2">
                            <Icon
                              icon="ph:file-text"
                              className="text-bud-text-disabled text-sm"
                            />
                            <Text className="text-bud-text-muted text-[12px]">
                              {project.resources.logs.toLocaleString()} Logs
                            </Text>
                          </div>
                          <div className="flex items-center gap-2">
                            <Icon
                              icon="ph:cpu"
                              className="text-bud-text-disabled text-sm"
                            />
                            <Text className="text-bud-text-muted text-[12px]">
                              {project.resources.models} Models
                            </Text>
                          </div>
                        </div>
                      </div>

                      <div className="bg-bud-bg-tertiary px-6 py-4 border-t border-bud-border">
                        <Text className="text-bud-text-disabled text-[12px] mb-1 block">
                          Last Updated
                        </Text>
                        <Text className="text-bud-text-primary text-[13px]">
                          {dayjs(project.updated_at).format(
                            "MMM DD, YYYY HH:mm",
                          )}
                        </Text>
                      </div>
                    </Card>
                  </Col>
                ))}
              </Row>
            </div>
          )}

          {/* Archived Projects */}
          {archivedProjects.length > 0 && (
            <div className="mb-[3rem]">
              <Text className="text-bud-text-primary font-semibold text-[16px] mb-[1.5rem] block">
                Archived Projects ({archivedProjects.length})
              </Text>
              <Row gutter={[24, 24]}>
                {archivedProjects.map((project) => (
                  <Col key={project.id} xs={24} sm={12} lg={8}>
                    <Card
                      className="h-full bg-bud-bg-secondary border-bud-border hover:border-bud-purple hover:shadow-lg transition-all duration-300 cursor-pointer overflow-hidden opacity-60"
                      styles={{ body: { padding: 0 } }}
                    >
                      {/* Similar structure with even more opacity for archived */}
                      <div className="p-6">
                        <div className="flex items-start justify-between mb-6">
                          <div className="w-12 h-12 rounded-lg flex items-center justify-center bg-gray-500">
                            <Icon
                              icon="ph:archive"
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

                        <Text className="text-bud-text-primary text-[19px] font-semibold mb-3 line-clamp-1 block">
                          {project.name}
                        </Text>

                        <Text className="text-bud-text-muted text-[13px] mb-6 line-clamp-2 leading-relaxed block">
                          {project.description}
                        </Text>

                        <div className="flex items-center gap-2 mb-6">
                          <Tag
                            icon={<Icon icon={getStatusIcon(project.status)} />}
                            color={getStatusColor(project.status)}
                            className="border-0 px-[0.75rem] py-[0.25rem] text-[0.75rem]"
                          >
                            {project.status.charAt(0).toUpperCase() +
                              project.status.slice(1)}
                          </Tag>
                        </div>
                      </div>

                      <div className="bg-bud-bg-tertiary px-6 py-4 border-t border-bud-border">
                        <Text className="text-bud-text-disabled text-[12px] mb-1 block">
                          Archived On
                        </Text>
                        <Text className="text-bud-text-primary text-[13px]">
                          {dayjs(project.updated_at).format("MMM DD, YYYY")}
                        </Text>
                      </div>
                    </Card>
                  </Col>
                ))}
              </Row>
            </div>
          )}

          {/* Empty State */}
          {projects.length === 0 && (
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
                onClick={() => setShowCreateModal(true)}
              >
                Create Your First Project
              </Button>
            </div>
          )}

          {/* Create Project Modal */}
          <Modal
            title={
              <Text className="text-bud-text-primary font-semibold text-[19px]">
                Create New Project
              </Text>
            }
            open={showCreateModal}
            onCancel={() => {
              setShowCreateModal(false);
              setFormData({
                name: "",
                description: "",
                project_type: "client_app",
                color: "#965CDE",
              });
            }}
            footer={[
              <Button key="cancel" onClick={() => setShowCreateModal(false)}>
                Cancel
              </Button>,
              <Button
                key="create"
                type="primary"
                className="bg-bud-purple border-bud-purple hover:bg-bud-purple-hover"
                onClick={handleCreateProject}
                disabled={!formData.name.trim()}
              >
                Create Project
              </Button>,
            ]}
            className={styles.modal}
            width={600}
          >
            <div className="space-y-[1rem]">
              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Project Name *
                </Text>
                <Input
                  placeholder="e.g., E-commerce AI Assistant"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  className="bg-bud-bg-tertiary border-bud-border-secondary"
                />
              </div>

              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Description
                </Text>
                <TextArea
                  placeholder="Describe what this project is for and its main objectives..."
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  className="bg-bud-bg-tertiary border-bud-border-secondary"
                  rows={3}
                />
              </div>

              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Project Type
                </Text>
                <Select
                  value={formData.project_type}
                  onChange={(value) =>
                    setFormData({ ...formData, project_type: value })
                  }
                  className="w-full"
                  options={[
                    {
                      value: "client_app",
                      label: (
                        <div className="flex items-center gap-2">
                          <Icon icon="ph:device-mobile" />
                          Client App - Created in this application
                        </div>
                      ),
                    },
                    {
                      value: "existing_app",
                      label: (
                        <div className="flex items-center gap-2">
                          <Icon icon="ph:cloud" />
                          Existing App - Imported from main platform
                        </div>
                      ),
                    },
                  ]}
                />
              </div>

              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Theme Color
                </Text>
                <div className="flex gap-2">
                  {colorOptions.map((color) => (
                    <button
                      key={color}
                      className={`w-8 h-8 rounded-full border-2 transition-all ${
                        formData.color === color
                          ? "border-bud-text-primary shadow-md scale-110"
                          : "border-bud-border hover:border-bud-text-muted"
                      }`}
                      style={{ backgroundColor: color }}
                      onClick={() => setFormData({ ...formData, color })}
                    />
                  ))}
                </div>
              </div>
            </div>
          </Modal>

          {/* Edit Project Modal */}
          <Modal
            title={
              <Text className="text-bud-text-primary font-semibold text-[19px]">
                Edit Project
              </Text>
            }
            open={showEditModal}
            onCancel={() => {
              setShowEditModal(false);
              setSelectedProject(null);
              setFormData({
                name: "",
                description: "",
                project_type: "client_app",
                color: "#965CDE",
              });
            }}
            footer={[
              <Button key="cancel" onClick={() => setShowEditModal(false)}>
                Cancel
              </Button>,
              <Button
                key="save"
                type="primary"
                className="bg-bud-purple border-bud-purple hover:bg-bud-purple-hover"
                onClick={handleEditProject}
                disabled={!formData.name.trim()}
              >
                Save Changes
              </Button>,
            ]}
            className={styles.modal}
            width={600}
          >
            <div className="space-y-[1rem]">
              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Project Name *
                </Text>
                <Input
                  placeholder="e.g., E-commerce AI Assistant"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  className="bg-bud-bg-tertiary border-bud-border-secondary"
                />
              </div>

              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Description
                </Text>
                <TextArea
                  placeholder="Describe what this project is for and its main objectives..."
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  className="bg-bud-bg-tertiary border-bud-border-secondary"
                  rows={3}
                />
              </div>

              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Project Type
                </Text>
                <Select
                  value={formData.project_type}
                  onChange={(value) =>
                    setFormData({ ...formData, project_type: value })
                  }
                  className="w-full"
                  options={[
                    {
                      value: "client_app",
                      label: (
                        <div className="flex items-center gap-2">
                          <Icon icon="ph:device-mobile" />
                          Client App - Created in this application
                        </div>
                      ),
                    },
                    {
                      value: "existing_app",
                      label: (
                        <div className="flex items-center gap-2">
                          <Icon icon="ph:cloud" />
                          Existing App - Imported from main platform
                        </div>
                      ),
                    },
                  ]}
                />
              </div>

              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Theme Color
                </Text>
                <div className="flex gap-2">
                  {colorOptions.map((color) => (
                    <button
                      key={color}
                      className={`w-8 h-8 rounded-full border-2 transition-all ${
                        formData.color === color
                          ? "border-bud-text-primary shadow-md scale-110"
                          : "border-bud-border hover:border-bud-text-muted"
                      }`}
                      style={{ backgroundColor: color }}
                      onClick={() => setFormData({ ...formData, color })}
                    />
                  ))}
                </div>
              </div>
            </div>
          </Modal>
        </div>
      </div>
    </DashboardLayout>
  );
}
