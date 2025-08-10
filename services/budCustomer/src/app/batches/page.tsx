"use client";
import React, { useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Flex,
  Table,
  Button,
  Modal,
  Input,
  Tag,
  Progress,
  Tooltip,
} from "antd";
import { Typography } from "antd";

const { Text, Title } = Typography;
import { Icon } from "@iconify/react/dist/iconify.js";
import styles from "./batches.module.scss";

interface BatchJob {
  id: string;
  name: string;
  model: string;
  status: "queued" | "processing" | "completed" | "failed" | "cancelled";
  progress: number;
  totalRequests: number;
  completedRequests: number;
  failedRequests: number;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  estimatedTime?: string;
  cost: number;
}

export default function BatchesPage() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedBatch, setSelectedBatch] = useState<BatchJob | null>(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);

  // Mock data
  const batches: BatchJob[] = [
    {
      id: "batch_001",
      name: "Product Descriptions Generation",
      model: "gpt-4",
      status: "processing",
      progress: 65,
      totalRequests: 1000,
      completedRequests: 650,
      failedRequests: 5,
      createdAt: "2024-01-20T08:00:00Z",
      startedAt: "2024-01-20T08:05:00Z",
      estimatedTime: "15 minutes",
      cost: 12.5,
    },
    {
      id: "batch_002",
      name: "Customer Review Analysis",
      model: "claude-3-opus",
      status: "completed",
      progress: 100,
      totalRequests: 500,
      completedRequests: 498,
      failedRequests: 2,
      createdAt: "2024-01-19T14:00:00Z",
      startedAt: "2024-01-19T14:02:00Z",
      completedAt: "2024-01-19T14:45:00Z",
      cost: 8.75,
    },
    {
      id: "batch_003",
      name: "Image Alt Text Generation",
      model: "gpt-4-vision",
      status: "queued",
      progress: 0,
      totalRequests: 2500,
      completedRequests: 0,
      failedRequests: 0,
      createdAt: "2024-01-20T10:00:00Z",
      estimatedTime: "45 minutes",
      cost: 0,
    },
    {
      id: "batch_004",
      name: "Email Template Personalization",
      model: "gpt-3.5-turbo",
      status: "failed",
      progress: 23,
      totalRequests: 750,
      completedRequests: 172,
      failedRequests: 578,
      createdAt: "2024-01-18T16:00:00Z",
      startedAt: "2024-01-18T16:01:00Z",
      completedAt: "2024-01-18T16:15:00Z",
      cost: 2.1,
    },
    {
      id: "batch_005",
      name: "Document Summarization",
      model: "claude-3-sonnet",
      status: "processing",
      progress: 88,
      totalRequests: 300,
      completedRequests: 264,
      failedRequests: 1,
      createdAt: "2024-01-20T09:30:00Z",
      startedAt: "2024-01-20T09:32:00Z",
      estimatedTime: "5 minutes",
      cost: 5.4,
    },
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case "queued":
        return "var(--bud-text-disabled)";
      case "processing":
        return "#4077E6";
      case "completed":
        return "#479D5F";
      case "failed":
        return "#EC7575";
      case "cancelled":
        return "#DE9C5C";
      default:
        return "var(--bud-text-muted)";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "queued":
        return "ph:clock";
      case "processing":
        return "ph:spinner";
      case "completed":
        return "ph:check-circle";
      case "failed":
        return "ph:x-circle";
      case "cancelled":
        return "ph:minus-circle";
      default:
        return "ph:circle";
    }
  };

  const columns = [
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          BATCH NAME
        </Text>
      ),
      dataIndex: "name",
      key: "name",
      render: (text: string, record: BatchJob) => (
        <div>
          <Text className="text-bud-text-primary text-[14px] font-medium">
            {text}
          </Text>
          <Text className="mt-[0.25rem] text-bud-text-disabled text-[12px] block">
            {record.id}
          </Text>
        </div>
      ),
    },
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          MODEL
        </Text>
      ),
      dataIndex: "model",
      key: "model",
      render: (text: string) => (
        <Text className="text-bud-text-primary text-[13px]">{text}</Text>
      ),
    },
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          STATUS
        </Text>
      ),
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Flex align="center" gap={8}>
          <Icon
            icon={getStatusIcon(status)}
            className={`text-[1rem] ${status === "processing" ? "animate-spin" : ""}`}
            style={{ color: getStatusColor(status) }}
          />
          <Tag
            color={getStatusColor(status)}
            className="border-0 px-[0.75rem] py-[0.25rem] text-[0.75rem] uppercase"
          >
            {status}
          </Tag>
        </Flex>
      ),
    },
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          PROGRESS
        </Text>
      ),
      key: "progress",
      width: 200,
      render: (_: any, record: BatchJob) => (
        <div>
          <Flex justify="space-between" className="mb-[0.5rem]">
            <Text className="text-bud-text-muted text-[12px]">
              {record.completedRequests}/{record.totalRequests}
            </Text>
            <Text className="text-bud-text-muted text-[12px]">
              {record.progress}%
            </Text>
          </Flex>
          <Progress
            percent={record.progress}
            strokeColor={getStatusColor(record.status)}
            trailColor="var(--bud-border-secondary)"
            showInfo={false}
            size="small"
          />
        </div>
      ),
    },
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          REQUESTS
        </Text>
      ),
      key: "requests",
      render: (_: any, record: BatchJob) => (
        <Flex gap={16}>
          <Tooltip title="Completed">
            <Flex align="center" gap={4}>
              <Icon icon="ph:check" className="text-[#479D5F]" />
              <Text className="text-bud-text-primary text-[13px]">
                {record.completedRequests}
              </Text>
            </Flex>
          </Tooltip>
          <Tooltip title="Failed">
            <Flex align="center" gap={4}>
              <Icon icon="ph:x" className="text-[#EC7575]" />
              <Text className="text-bud-text-primary text-[13px]">
                {record.failedRequests}
              </Text>
            </Flex>
          </Tooltip>
        </Flex>
      ),
    },
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          COST
        </Text>
      ),
      dataIndex: "cost",
      key: "cost",
      render: (cost: number) => (
        <Text className="text-bud-purple text-[13px]">${cost.toFixed(2)}</Text>
      ),
    },
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          TIME
        </Text>
      ),
      key: "time",
      render: (_: any, record: BatchJob) => (
        <div>
          {record.status === "queued" && record.estimatedTime && (
            <Text className="text-bud-text-muted text-[12px]">
              Est. {record.estimatedTime}
            </Text>
          )}
          {record.status === "processing" && record.estimatedTime && (
            <Text className="text-bud-text-muted text-[12px]">
              ~{record.estimatedTime} left
            </Text>
          )}
          {record.completedAt && (
            <Text className="text-bud-text-muted text-[12px]">
              {new Date(record.completedAt).toLocaleString()}
            </Text>
          )}
        </div>
      ),
    },
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          ACTIONS
        </Text>
      ),
      key: "actions",
      render: (_: any, record: BatchJob) => (
        <Flex gap={8}>
          <Button
            type="text"
            icon={<Icon icon="ph:eye" />}
            onClick={() => {
              setSelectedBatch(record);
              setShowDetailsModal(true);
            }}
            className="text-bud-text-disabled hover:text-bud-text-primary"
          />
          {record.status === "processing" && (
            <Button
              type="text"
              icon={<Icon icon="ph:pause" />}
              className="text-orange-500 hover:text-bud-text-primary"
            />
          )}
          {(record.status === "queued" || record.status === "processing") && (
            <Button
              type="text"
              icon={<Icon icon="ph:x" />}
              className="text-red-500 hover:text-bud-text-primary"
            />
          )}
          {record.status === "completed" && (
            <Button
              type="text"
              icon={<Icon icon="ph:download-simple" />}
              className="text-green-500 hover:text-bud-text-primary"
            />
          )}
        </Flex>
      ),
    },
  ];

  // Calculate stats
  const stats = {
    active: batches.filter(
      (b) => b.status === "processing" || b.status === "queued",
    ).length,
    completed: batches.filter((b) => b.status === "completed").length,
    failed: batches.filter((b) => b.status === "failed").length,
    totalCost: batches.reduce((acc, b) => acc + b.cost, 0),
  };

  return (
    <DashboardLayout>
      <div className="boardPageView">
        <div className="boardMainContainer pt-[2.25rem]">
          {/* Header */}
          <Flex justify="space-between" align="center" className="mb-[2rem]">
            <div>
              <Title level={2} className="!text-bud-text-primary !mb-0">
                Batch Jobs
              </Title>
              <Text className="text-bud-text-muted text-[14px] mt-[0.5rem] block">
                Process large volumes of requests asynchronously
              </Text>
            </div>
            <Button
              type="primary"
              icon={<Icon icon="ph:plus" />}
              className="bg-bud-purple border-bud-purple hover:bg-bud-purple-hover h-[2.5rem] px-[1.5rem]"
              onClick={() => setShowCreateModal(true)}
            >
              Create Batch Job
            </Button>
          </Flex>

          {/* Stats Cards */}
          <Flex gap={16} className="mb-[2rem]">
            <div className="bg-bud-bg-secondary border border-bud-border rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon
                  icon="ph:spinner"
                  className="text-[#4077E6] text-[1.25rem]"
                />
                <Text className="text-bud-text-disabled text-[12px]">
                  Active Jobs
                </Text>
              </Flex>
              <Text className="text-bud-text-primary text-[24px] font-medium mt-[0.5rem] block">
                {stats.active}
              </Text>
            </div>
            <div className="bg-bud-bg-secondary border border-bud-border rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon
                  icon="ph:check-circle"
                  className="text-[#479D5F] text-[1.25rem]"
                />
                <Text className="text-bud-text-disabled text-[12px]">
                  Completed
                </Text>
              </Flex>
              <Text className="text-bud-text-primary text-[24px] font-medium mt-[0.5rem] block">
                {stats.completed}
              </Text>
            </div>
            <div className="bg-bud-bg-secondary border border-bud-border rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon
                  icon="ph:x-circle"
                  className="text-[#EC7575] text-[1.25rem]"
                />
                <Text className="text-bud-text-disabled text-[12px]">
                  Failed
                </Text>
              </Flex>
              <Text className="text-bud-text-primary text-[24px] font-medium mt-[0.5rem] block">
                {stats.failed}
              </Text>
            </div>
            <div className="bg-bud-bg-secondary border border-bud-border rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon
                  icon="ph:currency-dollar"
                  className="text-[#965CDE] text-[1.25rem]"
                />
                <Text className="text-bud-text-disabled text-[12px]">
                  Total Cost
                </Text>
              </Flex>
              <Text className="text-bud-text-primary text-[24px] font-medium mt-[0.5rem] block">
                ${stats.totalCost.toFixed(2)}
              </Text>
            </div>
          </Flex>

          {/* Batch Jobs Table */}
          <div className="bg-bud-bg-secondary border border-bud-border rounded-[12px] overflow-hidden">
            <Table
              dataSource={batches}
              columns={columns}
              rowKey="id"
              pagination={false}
              className={styles.batchesTable}
            />
          </div>

          {/* Create Batch Modal */}
          <Modal
            title={
              <Text className="text-bud-text-primary font-semibold text-[19px]">
                Create Batch Job
              </Text>
            }
            open={showCreateModal}
            onCancel={() => setShowCreateModal(false)}
            footer={[
              <Button key="cancel" onClick={() => setShowCreateModal(false)}>
                Cancel
              </Button>,
              <Button
                key="create"
                type="primary"
                className="bg-bud-purple border-bud-purple hover:bg-bud-purple-hover"
                onClick={() => setShowCreateModal(false)}
              >
                Create Job
              </Button>,
            ]}
            className={styles.modal}
            width={600}
          >
            <Text className="text-bud-text-muted text-[14px] mb-[1.5rem] block">
              Upload a JSONL file containing your batch requests
            </Text>

            <div className="space-y-[1rem]">
              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Job Name
                </Text>
                <Input
                  placeholder="e.g., Product Descriptions Generation"
                  className="bg-bud-bg-tertiary border-bud-border-secondary"
                />
              </div>

              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Select Model
                </Text>
                <select className="w-full bg-bud-bg-tertiary border border-bud-border-secondary text-bud-text-primary px-[0.75rem] py-[0.5rem] rounded-[6px]">
                  <option>GPT-4</option>
                  <option>GPT-3.5 Turbo</option>
                  <option>Claude 3 Opus</option>
                  <option>Claude 3 Sonnet</option>
                </select>
              </div>

              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Upload JSONL File
                </Text>
                <div className="border-2 border-dashed border-bud-border-secondary rounded-[8px] p-[2rem] text-center cursor-pointer hover:border-bud-purple transition-colors">
                  <Icon
                    icon="ph:upload-simple"
                    className="text-[2rem] text-bud-text-disabled mb-[0.5rem]"
                  />
                  <Text className="text-bud-text-muted text-[14px]">
                    Drag and drop your JSONL file here, or click to browse
                  </Text>
                  <Text className="mt-[0.25rem] text-bud-text-disabled text-[12px] block">
                    Maximum file size: 100MB
                  </Text>
                </div>
              </div>
            </div>
          </Modal>

          {/* Details Modal */}
          <Modal
            title={
              <Text className="text-bud-text-primary font-semibold text-[19px]">
                Batch Job Details
              </Text>
            }
            open={showDetailsModal}
            onCancel={() => {
              setShowDetailsModal(false);
              setSelectedBatch(null);
            }}
            footer={[
              <Button
                key="close"
                onClick={() => {
                  setShowDetailsModal(false);
                  setSelectedBatch(null);
                }}
              >
                Close
              </Button>,
            ]}
            className={styles.modal}
            width={700}
          >
            {selectedBatch && (
              <div className="space-y-[1.5rem]">
                <div className="grid grid-cols-2 gap-[1rem]">
                  <div>
                    <Text className="text-bud-text-disabled text-[12px]">
                      Batch ID
                    </Text>
                    <Text className="mt-[0.25rem] text-bud-text-primary text-[14px] block">
                      {selectedBatch.id}
                    </Text>
                  </div>
                  <div>
                    <Text className="text-bud-text-disabled text-[12px]">
                      Model
                    </Text>
                    <Text className="mt-[0.25rem] text-bud-text-primary text-[14px] block">
                      {selectedBatch.model}
                    </Text>
                  </div>
                  <div>
                    <Text className="text-bud-text-disabled text-[12px]">
                      Created At
                    </Text>
                    <Text className="mt-[0.25rem] text-bud-text-primary text-[14px] block">
                      {new Date(selectedBatch.createdAt).toLocaleString()}
                    </Text>
                  </div>
                  <div>
                    <Text className="text-bud-text-disabled text-[12px]">
                      Status
                    </Text>
                    <Tag
                      color={getStatusColor(selectedBatch.status)}
                      className="border-0 px-[0.75rem] py-[0.25rem] text-[0.75rem] uppercase mt-[0.25rem]"
                    >
                      {selectedBatch.status}
                    </Tag>
                  </div>
                </div>

                <div>
                  <Text className="text-bud-text-disabled text-[12px]">
                    Progress
                  </Text>
                  <Progress
                    percent={selectedBatch.progress}
                    strokeColor={getStatusColor(selectedBatch.status)}
                    trailColor="var(--bud-border-secondary)"
                    className="mt-[0.5rem]"
                  />
                  <Flex justify="space-between" className="mt-[0.5rem]">
                    <Text className="text-bud-text-muted text-[12px]">
                      {selectedBatch.completedRequests} of{" "}
                      {selectedBatch.totalRequests} requests
                    </Text>
                    <Text className="text-bud-text-muted text-[12px]">
                      {selectedBatch.failedRequests} failed
                    </Text>
                  </Flex>
                </div>

                <div className="bg-bud-bg-tertiary rounded-[8px] p-[1rem]">
                  <Text className="text-bud-text-disabled text-[12px]">
                    Request Summary
                  </Text>
                  <div className="mt-[0.75rem] space-y-[0.5rem]">
                    <Flex justify="space-between">
                      <Text className="text-bud-text-muted text-[12px]">
                        Total Requests
                      </Text>
                      <Text className="text-bud-text-primary text-[13px]">
                        {selectedBatch.totalRequests}
                      </Text>
                    </Flex>
                    <Flex justify="space-between">
                      <Text className="text-bud-text-muted text-[12px]">
                        Completed
                      </Text>
                      <Text className="text-green-500 text-[13px]">
                        {selectedBatch.completedRequests}
                      </Text>
                    </Flex>
                    <Flex justify="space-between">
                      <Text className="text-bud-text-muted text-[12px]">
                        Failed
                      </Text>
                      <Text className="text-red-500 text-[13px]">
                        {selectedBatch.failedRequests}
                      </Text>
                    </Flex>
                    <Flex
                      justify="space-between"
                      className="pt-[0.5rem] border-t border-bud-border-secondary"
                    >
                      <Text className="text-bud-text-muted text-[12px]">
                        Total Cost
                      </Text>
                      <Text className="text-bud-purple text-[14px] font-medium">
                        ${selectedBatch.cost.toFixed(2)}
                      </Text>
                    </Flex>
                  </div>
                </div>
              </div>
            )}
          </Modal>
        </div>
      </div>
    </DashboardLayout>
  );
}
