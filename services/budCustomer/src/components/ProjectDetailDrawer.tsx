import React, { useEffect, useState } from "react";
import { Drawer, Tabs, Tag, Spin, Empty, Card, Row, Col, Typography, Divider, Space, Button, Tooltip } from "antd";
import type { TabsProps } from "antd";
import {
  CopyOutlined,
  CodeOutlined,
  TagsOutlined,
  InfoCircleOutlined,
  ApiOutlined,
  CalendarOutlined,
  UserOutlined,
  FolderOutlined,
} from "@ant-design/icons";
import { successToast } from "@/components/toast";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { AppRequest } from "@/services/api/requests";
import dayjs from "dayjs";

const { Title, Text, Paragraph } = Typography;

interface ProjectTag {
  name: string;
  color: string;
}

interface Project {
  id: string;
  name: string;
  description: string;
  tags: ProjectTag[];
  icon: string;
  project_type: string;
  created_at?: string;
  updated_at?: string;
  owner?: string;
  endpoints_count?: number;
  models_count?: number;
  clusters_count?: number;
}

interface ProjectDetailDrawerProps {
  visible: boolean;
  onClose: () => void;
  projectId: string | null;
}

export const ProjectDetailContent: React.FC<{ projectId: string; onClose: () => void }> = ({
  projectId,
  onClose,
}) => {
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("1");

  useEffect(() => {
    if (projectId) {
      fetchProjectDetails();
    }
  }, [projectId]);

  const fetchProjectDetails = async () => {
    try {
      setLoading(true);
      const response = await AppRequest.Get(`/projects/${projectId}`);
      if (response.data?.project) {
        setProject({
          ...response.data.project,
          endpoints_count: response.data.endpoints_count || 0,
          models_count: response.data.models_count || 0,
          clusters_count: response.data.clusters_count || 0,
        });
      }
    } catch (error) {
      console.error("Failed to fetch project details:", error);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    successToast("Copied to clipboard");
  };

  const getProjectTypeLabel = (type: string) => {
    const typeMap: Record<string, string> = {
      client_app: "Client Application",
      server_app: "Server Application",
      ml_model: "ML Model",
      data_pipeline: "Data Pipeline",
    };
    return typeMap[type] || type;
  };

  const GeneralTab = () => {
    if (!project) return null;

    return (
      <div className="p-4">
        <Card className="mb-4 bg-[#1a1a2e]/50 border-[#2a2a3e]">
          <Space direction="vertical" size="large" className="w-full">
            {/* Project Header */}
            <div className="flex items-center gap-4">
              <div className="text-4xl">{project.icon || "📁"}</div>
              <div className="flex-1">
                <Title level={4} className="!mb-1 text-white">
                  {project.name}
                </Title>
                <Text className="text-gray-400">{project.description}</Text>
              </div>
            </div>

            <Divider className="!my-3 border-[#2a2a3e]" />

            {/* Project Information */}
            <Row gutter={[16, 16]}>
              <Col span={24}>
                <div className="flex items-center justify-between">
                  <Text className="text-gray-400">Project ID</Text>
                  <Space>
                    <Text className="text-white font-mono">{project.id}</Text>
                    <Tooltip title="Copy ID">
                      <Button
                        type="text"
                        size="small"
                        icon={<CopyOutlined />}
                        onClick={() => copyToClipboard(project.id)}
                      />
                    </Tooltip>
                  </Space>
                </div>
              </Col>

              <Col span={24}>
                <div className="flex items-center justify-between">
                  <Text className="text-gray-400">Project Type</Text>
                  <Tag color="blue" icon={<FolderOutlined />}>
                    {getProjectTypeLabel(project.project_type)}
                  </Tag>
                </div>
              </Col>

              <Col span={24}>
                <div className="flex items-center justify-between">
                  <Text className="text-gray-400">Tags</Text>
                  <Space wrap>
                    {project.tags && project.tags.length > 0 ? (
                      project.tags.map((tag, index) => (
                        <Tag key={index} color={tag.color} icon={<TagsOutlined />}>
                          {tag.name}
                        </Tag>
                      ))
                    ) : (
                      <Text className="text-gray-500">No tags</Text>
                    )}
                  </Space>
                </div>
              </Col>

              {project.created_at && (
                <Col span={24}>
                  <div className="flex items-center justify-between">
                    <Text className="text-gray-400">Created</Text>
                    <Text className="text-white">
                      {dayjs(project.created_at).format("MMM DD, YYYY")}
                    </Text>
                  </div>
                </Col>
              )}

              {project.updated_at && (
                <Col span={24}>
                  <div className="flex items-center justify-between">
                    <Text className="text-gray-400">Last Updated</Text>
                    <Text className="text-white">
                      {dayjs(project.updated_at).format("MMM DD, YYYY")}
                    </Text>
                  </div>
                </Col>
              )}

              {project.owner && (
                <Col span={24}>
                  <div className="flex items-center justify-between">
                    <Text className="text-gray-400">Owner</Text>
                    <Space>
                      <UserOutlined className="text-gray-400" />
                      <Text className="text-white">{project.owner}</Text>
                    </Space>
                  </div>
                </Col>
              )}
            </Row>
          </Space>
        </Card>

        {/* Resource Statistics */}
        <Card className="bg-[#1a1a2e]/50 border-[#2a2a3e]">
          <Title level={5} className="!mb-4 text-white">
            Resources
          </Title>
          <Row gutter={[16, 16]}>
            <Col span={8}>
              <Card className="bg-[#0f0f1e] border-[#2a2a3e] text-center">
                <div className="text-2xl font-bold text-[#965CDE]">
                  {project.endpoints_count || 0}
                </div>
                <Text className="text-gray-400">Endpoints</Text>
              </Card>
            </Col>
            <Col span={8}>
              <Card className="bg-[#0f0f1e] border-[#2a2a3e] text-center">
                <div className="text-2xl font-bold text-[#965CDE]">
                  {project.models_count || 0}
                </div>
                <Text className="text-gray-400">Models</Text>
              </Card>
            </Col>
            <Col span={8}>
              <Card className="bg-[#0f0f1e] border-[#2a2a3e] text-center">
                <div className="text-2xl font-bold text-[#965CDE]">
                  {project.clusters_count || 0}
                </div>
                <Text className="text-gray-400">Clusters</Text>
              </Card>
            </Col>
          </Row>
        </Card>
      </div>
    );
  };

  const DetailsTab = () => {
    if (!project) return null;

    return (
      <div className="p-4">
        <Card className="bg-[#1a1a2e]/50 border-[#2a2a3e]">
          <Title level={5} className="!mb-4 text-white">
            Additional Details
          </Title>
          <Space direction="vertical" size="large" className="w-full">
            <div>
              <Text className="text-gray-400 block mb-2">Description</Text>
              <Paragraph className="text-white bg-[#0f0f1e] p-3 rounded">
                {project.description || "No description provided"}
              </Paragraph>
            </div>

            <div>
              <Text className="text-gray-400 block mb-2">Configuration</Text>
              <pre className="bg-[#0f0f1e] p-3 rounded text-white overflow-auto">
                {JSON.stringify(
                  {
                    id: project.id,
                    name: project.name,
                    type: project.project_type,
                    tags: project.tags,
                  },
                  null,
                  2
                )}
              </pre>
            </div>
          </Space>
        </Card>
      </div>
    );
  };

  const items: TabsProps["items"] = [
    {
      key: "1",
      label: "General",
      children: <GeneralTab />,
    },
    {
      key: "2",
      label: "Details",
      children: <DetailsTab />,
    },
  ];

  if (loading) {
    return (
      <BudForm
        data={{
          name: "Project details",
          description: "",
          tags: [],
          icon: "",
        }}
        onNext={onClose}
        nextText="Close"
        showBack={false}
      >
        <BudWraperBox>
          <BudDrawerLayout>
            <div className="flex justify-center items-center h-64">
              <Spin size="large" />
            </div>
          </BudDrawerLayout>
        </BudWraperBox>
      </BudForm>
    );
  }

  if (!project) {
    return (
      <BudForm
        data={{
          name: "Project details",
          description: "",
          tags: [],
          icon: "",
        }}
        onNext={onClose}
        nextText="Close"
        showBack={false}
      >
        <BudWraperBox>
          <BudDrawerLayout>
            <Empty description="Project not found" />
          </BudDrawerLayout>
        </BudWraperBox>
      </BudForm>
    );
  }

  return (
    <BudForm
      data={{
        name: "Project details",
        description: "",
        tags: [],
        icon: "",
      }}
      onNext={onClose}
      nextText="Close"
      showBack={false}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Project Details"
            description={`View detailed information about ${project.name}`}
          />
          <DrawerCard classNames="pb-0">
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              items={items}
              className="project-detail-tabs"
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

const ProjectDetailDrawer: React.FC<ProjectDetailDrawerProps> = ({
  visible,
  onClose,
  projectId,
}) => {
  if (!projectId) return null;

  return (
    <Drawer
      title={null}
      placement="right"
      onClose={onClose}
      open={visible}
      width={800}
      closable={false}
      className="project-detail-drawer"
      styles={{
        body: {
          padding: 0,
          background: "#0a0a0f",
        },
      }}
    >
      <ProjectDetailContent projectId={projectId} onClose={onClose} />
    </Drawer>
  );
};

export default ProjectDetailDrawer;
