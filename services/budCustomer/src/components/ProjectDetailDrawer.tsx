import React, { useEffect, useState } from "react";
import {
  Drawer,
  Tag,
  Spin,
  Empty,
  Card,
  Row,
  Col,
  Typography,
  Space,
  Button,
  Tooltip,
} from "antd";
import {
  CopyOutlined,
  TagsOutlined,
  UserOutlined,
  FolderOutlined,
} from "@ant-design/icons";
import { successToast, errorToast } from "@/components/toast";
import { copyToClipboard } from "@/utils/clipboard";
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
  credentials: {
    id: string;
    last_used_at: string;
    name: string;
  }[];
  credentials_count: number;
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

export const ProjectDetailContent: React.FC<{
  projectId: string;
  onClose: () => void;
}> = ({ projectId, onClose }) => {
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
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
            credentials_count: response.data.credentials_count || 0,
            credentials: response.data.credentials || [],
          });
        }
      } catch (error) {
        console.error("Failed to fetch project details:", error);
      } finally {
        setLoading(false);
      }
    };

    if (projectId) {
      fetchProjectDetails();
    }
  }, [projectId]);

  const handleCopyToClipboard = async (text: string) => {
    await copyToClipboard(text, {
      onSuccess: () => successToast("Copied to clipboard"),
      onError: () => errorToast("Failed to copy to clipboard"),
    });
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
                  <Title
                    level={4}
                    className="!mb-1 text-black dark:text-[#EEEEEE]"
                  >
                    {project.name}
                  </Title>
                  <Text className="text-gray-400">{project.description}</Text>
                </div>
              </div>
              <div className="hR w-full bg-[#1F1F1F50] h-[1px]"></div>
              {/* Project Information */}
              <Row gutter={[16, 16]} className="px-[1.4rem] mt-[1rem]">
                <Col span={24}>
                  <div className="flex items-center justify-start py-[1rem]">
                    <Text className="text-gray-400">Tags: &nbsp;</Text>
                    <Space wrap>
                      {project.tags && project.tags.length > 0 ? (
                        project.tags.map((tag, index) => (
                          <Tag
                            key={index}
                            color={tag.color}
                            icon={<TagsOutlined />}
                          >
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
                  <div className="flex items-center justify-start">
                    <Text className="text-gray-400">Api Keys: &nbsp;</Text>
                    <Text className="text-[black] dark:text-white">
                      {project.credentials_count || 0}
                    </Text>
                  </div>
                </Col>

                {project.credentials && project.credentials.length > 0 && (
                  <Col span={24} className="mb-[1.5rem]">
                    <div className="bg-gray-100 dark:bg-[#1F1F1F50] rounded-lg p-3">
                      <Text className="text-gray-600 dark:text-gray-400 text-xs mb-2 block">
                        Available API Keys
                      </Text>
                      {project.credentials.map((credential) => (
                        <div
                          key={credential.id}
                          className="flex items-center justify-between py-2 border-b border-gray-300 dark:border-[#2a2a3e] last:border-0"
                        >
                          <Text className="text-gray-900 dark:text-white text-sm">
                            {credential.name}
                          </Text>
                          <Text className="text-gray-600 dark:text-gray-500 text-xs">
                            {credential.last_used_at
                              ? `Last used: ${dayjs(credential.last_used_at).format("MMM DD, YYYY HH:mm")}`
                              : "Never used"}
                          </Text>
                        </div>
                      ))}
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
