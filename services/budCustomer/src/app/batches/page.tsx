"use client";
import React, { useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Flex, Table, Button, Modal, Input, Tag, Progress, Tooltip } from "antd";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_13_400_EEEEEE,
  Text_14_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_500_EEEEEE,
  Text_15_600_EEEEEE,
  Text_19_600_EEEEEE,
  Text_24_500_EEEEEE
} from "@/components/ui/text";
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
      cost: 12.50
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
      cost: 8.75
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
      cost: 0
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
      cost: 2.10
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
      cost: 5.40
    }
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case "queued": return "#757575";
      case "processing": return "#4077E6";
      case "completed": return "#479D5F";
      case "failed": return "#EC7575";
      case "cancelled": return "#DE9C5C";
      default: return "#B3B3B3";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "queued": return "ph:clock";
      case "processing": return "ph:spinner";
      case "completed": return "ph:check-circle";
      case "failed": return "ph:x-circle";
      case "cancelled": return "ph:minus-circle";
      default: return "ph:circle";
    }
  };

  const columns = [
    {
      title: <Text_12_400_757575>BATCH NAME</Text_12_400_757575>,
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: BatchJob) => (
        <div>
          <Text_14_500_EEEEEE>{text}</Text_14_500_EEEEEE>
          <Text_12_400_757575 className="mt-[0.25rem]">{record.id}</Text_12_400_757575>
        </div>
      )
    },
    {
      title: <Text_12_400_757575>MODEL</Text_12_400_757575>,
      dataIndex: 'model',
      key: 'model',
      render: (text: string) => <Text_13_400_EEEEEE>{text}</Text_13_400_EEEEEE>
    },
    {
      title: <Text_12_400_757575>STATUS</Text_12_400_757575>,
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Flex align="center" gap={8}>
          <Icon
            icon={getStatusIcon(status)}
            className={`text-[1rem] ${status === 'processing' ? 'animate-spin' : ''}`}
            style={{ color: getStatusColor(status) }}
          />
          <Tag
            color={getStatusColor(status)}
            className="border-0 px-[0.75rem] py-[0.25rem] text-[0.75rem] uppercase"
          >
            {status}
          </Tag>
        </Flex>
      )
    },
    {
      title: <Text_12_400_757575>PROGRESS</Text_12_400_757575>,
      key: 'progress',
      width: 200,
      render: (_: any, record: BatchJob) => (
        <div>
          <Flex justify="space-between" className="mb-[0.5rem]">
            <Text_12_400_B3B3B3>{record.completedRequests}/{record.totalRequests}</Text_12_400_B3B3B3>
            <Text_12_400_B3B3B3>{record.progress}%</Text_12_400_B3B3B3>
          </Flex>
          <Progress
            percent={record.progress}
            strokeColor={getStatusColor(record.status)}
            trailColor="#2F2F2F"
            showInfo={false}
            size="small"
          />
        </div>
      )
    },
    {
      title: <Text_12_400_757575>REQUESTS</Text_12_400_757575>,
      key: 'requests',
      render: (_: any, record: BatchJob) => (
        <Flex gap={16}>
          <Tooltip title="Completed">
            <Flex align="center" gap={4}>
              <Icon icon="ph:check" className="text-[#479D5F]" />
              <Text_13_400_EEEEEE>{record.completedRequests}</Text_13_400_EEEEEE>
            </Flex>
          </Tooltip>
          <Tooltip title="Failed">
            <Flex align="center" gap={4}>
              <Icon icon="ph:x" className="text-[#EC7575]" />
              <Text_13_400_EEEEEE>{record.failedRequests}</Text_13_400_EEEEEE>
            </Flex>
          </Tooltip>
        </Flex>
      )
    },
    {
      title: <Text_12_400_757575>COST</Text_12_400_757575>,
      dataIndex: 'cost',
      key: 'cost',
      render: (cost: number) => (
        <Text_13_400_EEEEEE className="text-[#965CDE]">${cost.toFixed(2)}</Text_13_400_EEEEEE>
      )
    },
    {
      title: <Text_12_400_757575>TIME</Text_12_400_757575>,
      key: 'time',
      render: (_: any, record: BatchJob) => (
        <div>
          {record.status === 'queued' && record.estimatedTime && (
            <Text_12_400_B3B3B3>Est. {record.estimatedTime}</Text_12_400_B3B3B3>
          )}
          {record.status === 'processing' && record.estimatedTime && (
            <Text_12_400_B3B3B3>~{record.estimatedTime} left</Text_12_400_B3B3B3>
          )}
          {record.completedAt && (
            <Text_12_400_B3B3B3>
              {new Date(record.completedAt).toLocaleString()}
            </Text_12_400_B3B3B3>
          )}
        </div>
      )
    },
    {
      title: <Text_12_400_757575>ACTIONS</Text_12_400_757575>,
      key: 'actions',
      render: (_: any, record: BatchJob) => (
        <Flex gap={8}>
          <Button
            type="text"
            icon={<Icon icon="ph:eye" />}
            onClick={() => {
              setSelectedBatch(record);
              setShowDetailsModal(true);
            }}
            className="text-[#757575] hover:text-[#EEEEEE]"
          />
          {record.status === 'processing' && (
            <Button
              type="text"
              icon={<Icon icon="ph:pause" />}
              className="text-[#DE9C5C] hover:text-[#EEEEEE]"
            />
          )}
          {(record.status === 'queued' || record.status === 'processing') && (
            <Button
              type="text"
              icon={<Icon icon="ph:x" />}
              className="text-[#EC7575] hover:text-[#EEEEEE]"
            />
          )}
          {record.status === 'completed' && (
            <Button
              type="text"
              icon={<Icon icon="ph:download-simple" />}
              className="text-[#479D5F] hover:text-[#EEEEEE]"
            />
          )}
        </Flex>
      )
    }
  ];

  // Calculate stats
  const stats = {
    active: batches.filter(b => b.status === 'processing' || b.status === 'queued').length,
    completed: batches.filter(b => b.status === 'completed').length,
    failed: batches.filter(b => b.status === 'failed').length,
    totalCost: batches.reduce((acc, b) => acc + b.cost, 0)
  };

  return (
    <DashboardLayout>
      <div className="boardPageView">
        <div className="boardMainContainer pt-[2.25rem]">
          {/* Header */}
          <Flex justify="space-between" align="center" className="mb-[2rem]">
            <div>
              <Text_24_500_EEEEEE>Batch Jobs</Text_24_500_EEEEEE>
              <Text_14_400_B3B3B3 className="mt-[0.5rem]">
                Process large volumes of requests asynchronously
              </Text_14_400_B3B3B3>
            </div>
            <Button
              type="primary"
              icon={<Icon icon="ph:plus" />}
              className="bg-[#965CDE] border-[#965CDE] h-[2.5rem] px-[1.5rem]"
              onClick={() => setShowCreateModal(true)}
            >
              Create Batch Job
            </Button>
          </Flex>

          {/* Stats Cards */}
          <Flex gap={16} className="mb-[2rem]">
            <div className="cardBG border border-[#1F1F1F] rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon icon="ph:spinner" className="text-[#4077E6] text-[1.25rem]" />
                <Text_12_400_757575>Active Jobs</Text_12_400_757575>
              </Flex>
              <Text_24_500_EEEEEE className="mt-[0.5rem]">{stats.active}</Text_24_500_EEEEEE>
            </div>
            <div className="cardBG border border-[#1F1F1F] rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon icon="ph:check-circle" className="text-[#479D5F] text-[1.25rem]" />
                <Text_12_400_757575>Completed</Text_12_400_757575>
              </Flex>
              <Text_24_500_EEEEEE className="mt-[0.5rem]">{stats.completed}</Text_24_500_EEEEEE>
            </div>
            <div className="cardBG border border-[#1F1F1F] rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon icon="ph:x-circle" className="text-[#EC7575] text-[1.25rem]" />
                <Text_12_400_757575>Failed</Text_12_400_757575>
              </Flex>
              <Text_24_500_EEEEEE className="mt-[0.5rem]">{stats.failed}</Text_24_500_EEEEEE>
            </div>
            <div className="cardBG border border-[#1F1F1F] rounded-[8px] px-[1.5rem] py-[1rem] flex-1">
              <Flex align="center" gap={8}>
                <Icon icon="ph:currency-dollar" className="text-[#965CDE] text-[1.25rem]" />
                <Text_12_400_757575>Total Cost</Text_12_400_757575>
              </Flex>
              <Text_24_500_EEEEEE className="mt-[0.5rem]">${stats.totalCost.toFixed(2)}</Text_24_500_EEEEEE>
            </div>
          </Flex>

          {/* Batch Jobs Table */}
          <div className="cardBG border border-[#1F1F1F] rounded-[12px] overflow-hidden">
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
            title={<Text_19_600_EEEEEE>Create Batch Job</Text_19_600_EEEEEE>}
            open={showCreateModal}
            onCancel={() => setShowCreateModal(false)}
            footer={[
              <Button key="cancel" onClick={() => setShowCreateModal(false)}>
                Cancel
              </Button>,
              <Button
                key="create"
                type="primary"
                className="bg-[#965CDE] border-[#965CDE]"
                onClick={() => setShowCreateModal(false)}
              >
                Create Job
              </Button>
            ]}
            className={styles.modal}
            width={600}
          >
            <Text_14_400_B3B3B3 className="mb-[1.5rem]">
              Upload a JSONL file containing your batch requests
            </Text_14_400_B3B3B3>

            <div className="space-y-[1rem]">
              <div>
                <Text_12_400_B3B3B3 className="mb-[0.5rem]">Job Name</Text_12_400_B3B3B3>
                <Input
                  placeholder="e.g., Product Descriptions Generation"
                  className="bg-[#1F1F1F] border-[#2F2F2F]"
                />
              </div>

              <div>
                <Text_12_400_B3B3B3 className="mb-[0.5rem]">Select Model</Text_12_400_B3B3B3>
                <select className="w-full bg-[#1F1F1F] border border-[#2F2F2F] text-[#EEEEEE] px-[0.75rem] py-[0.5rem] rounded-[6px]">
                  <option>GPT-4</option>
                  <option>GPT-3.5 Turbo</option>
                  <option>Claude 3 Opus</option>
                  <option>Claude 3 Sonnet</option>
                </select>
              </div>

              <div>
                <Text_12_400_B3B3B3 className="mb-[0.5rem]">Upload JSONL File</Text_12_400_B3B3B3>
                <div className="border-2 border-dashed border-[#2F2F2F] rounded-[8px] p-[2rem] text-center cursor-pointer hover:border-[#965CDE] transition-colors">
                  <Icon icon="ph:upload-simple" className="text-[2rem] text-[#757575] mb-[0.5rem]" />
                  <Text_14_400_B3B3B3>
                    Drag and drop your JSONL file here, or click to browse
                  </Text_14_400_B3B3B3>
                  <Text_12_400_757575 className="mt-[0.25rem]">
                    Maximum file size: 100MB
                  </Text_12_400_757575>
                </div>
              </div>
            </div>
          </Modal>

          {/* Details Modal */}
          <Modal
            title={<Text_19_600_EEEEEE>Batch Job Details</Text_19_600_EEEEEE>}
            open={showDetailsModal}
            onCancel={() => {
              setShowDetailsModal(false);
              setSelectedBatch(null);
            }}
            footer={[
              <Button key="close" onClick={() => {
                setShowDetailsModal(false);
                setSelectedBatch(null);
              }}>
                Close
              </Button>
            ]}
            className={styles.modal}
            width={700}
          >
            {selectedBatch && (
              <div className="space-y-[1.5rem]">
                <div className="grid grid-cols-2 gap-[1rem]">
                  <div>
                    <Text_12_400_757575>Batch ID</Text_12_400_757575>
                    <Text_14_400_EEEEEE className="mt-[0.25rem]">{selectedBatch.id}</Text_14_400_EEEEEE>
                  </div>
                  <div>
                    <Text_12_400_757575>Model</Text_12_400_757575>
                    <Text_14_400_EEEEEE className="mt-[0.25rem]">{selectedBatch.model}</Text_14_400_EEEEEE>
                  </div>
                  <div>
                    <Text_12_400_757575>Created At</Text_12_400_757575>
                    <Text_14_400_EEEEEE className="mt-[0.25rem]">
                      {new Date(selectedBatch.createdAt).toLocaleString()}
                    </Text_14_400_EEEEEE>
                  </div>
                  <div>
                    <Text_12_400_757575>Status</Text_12_400_757575>
                    <Tag
                      color={getStatusColor(selectedBatch.status)}
                      className="border-0 px-[0.75rem] py-[0.25rem] text-[0.75rem] uppercase mt-[0.25rem]"
                    >
                      {selectedBatch.status}
                    </Tag>
                  </div>
                </div>

                <div>
                  <Text_12_400_757575>Progress</Text_12_400_757575>
                  <Progress
                    percent={selectedBatch.progress}
                    strokeColor={getStatusColor(selectedBatch.status)}
                    trailColor="#2F2F2F"
                    className="mt-[0.5rem]"
                  />
                  <Flex justify="space-between" className="mt-[0.5rem]">
                    <Text_12_400_B3B3B3>
                      {selectedBatch.completedRequests} of {selectedBatch.totalRequests} requests
                    </Text_12_400_B3B3B3>
                    <Text_12_400_B3B3B3>
                      {selectedBatch.failedRequests} failed
                    </Text_12_400_B3B3B3>
                  </Flex>
                </div>

                <div className="bg-[#1F1F1F] rounded-[8px] p-[1rem]">
                  <Text_12_400_757575>Request Summary</Text_12_400_757575>
                  <div className="mt-[0.75rem] space-y-[0.5rem]">
                    <Flex justify="space-between">
                      <Text_12_400_B3B3B3>Total Requests</Text_12_400_B3B3B3>
                      <Text_13_400_EEEEEE>{selectedBatch.totalRequests}</Text_13_400_EEEEEE>
                    </Flex>
                    <Flex justify="space-between">
                      <Text_12_400_B3B3B3>Completed</Text_12_400_B3B3B3>
                      <Text_13_400_EEEEEE className="text-[#479D5F]">
                        {selectedBatch.completedRequests}
                      </Text_13_400_EEEEEE>
                    </Flex>
                    <Flex justify="space-between">
                      <Text_12_400_B3B3B3>Failed</Text_12_400_B3B3B3>
                      <Text_13_400_EEEEEE className="text-[#EC7575]">
                        {selectedBatch.failedRequests}
                      </Text_13_400_EEEEEE>
                    </Flex>
                    <Flex justify="space-between" className="pt-[0.5rem] border-t border-[#2F2F2F]">
                      <Text_12_400_B3B3B3>Total Cost</Text_12_400_B3B3B3>
                      <Text_14_500_EEEEEE className="text-[#965CDE]">
                        ${selectedBatch.cost.toFixed(2)}
                      </Text_14_500_EEEEEE>
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
