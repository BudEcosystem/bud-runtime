import React, { useEffect, useState } from "react";
import { Drawer, Tag, Spin, Empty, Card, Row, Col, Typography, Space, Button, Tooltip } from "antd";
import {
  CopyOutlined,
  TagsOutlined,
  UserOutlined,
  FolderOutlined,
} from "@ant-design/icons";
import { successToast } from "@/components/toast";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { AppRequest } from "@/services/api/requests";
import dayjs from "dayjs";

const { Title, Text } = Typography;

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
          <div>
            <div>
              <div className="flex items-center gap-4 px-[1.4rem] py-[1rem]">
                {/* <div className="text-4xl">{project.icon || "📁"}</div> */}
                <div className="flex-1">
                  <Title level={4} className="!mb-1 text-white">
                    {project.name}
                  </Title>
                  <Text className="text-gray-400">{project.description}</Text>
                </div>
              </div>
              <div className="hR w-full bg-[#1F1F1F50] h-[1px]"></div>
              {/* Project Information */}
              <Row gutter={[16, 16]} className="px-[1.4rem] mt-[1rem]">

                <Col span={24}>
                  <div className="flex items-center justify-between py-[1rem]">
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

                <Col span={24} className="mb-[1rem]">
                  <div className="flex items-center justify-between">
                    <Text className="text-gray-400">Endpoints</Text>
                    <Text className="text-white">{project.endpoints_count || 0}</Text>
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
            </div>
          </div>
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
