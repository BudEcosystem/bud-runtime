'use client';

/**
 * Workflow Triggers Panel
 *
 * Manages schedules, webhooks, and event triggers for a workflow.
 */

import React, { useEffect, useState } from 'react';
import {
  Tabs,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  Tag,
  Tooltip,
  Empty,
  Popconfirm,
  Space,
  Typography,
} from 'antd';
import {
  ClockCircleOutlined,
  ApiOutlined,
  ThunderboltOutlined,
  PlusOutlined,
  DeleteOutlined,
  PauseOutlined,
  PlayCircleOutlined,
  CopyOutlined,
  ReloadOutlined,
  KeyOutlined,
} from '@ant-design/icons';
import { formatDistanceToNow } from 'date-fns';
import {
  useBudPipeline,
  PipelineSchedule,
  PipelineWebhook,
  PipelineEventTrigger,
  SUPPORTED_EVENT_TYPES,
} from '@/stores/useBudPipeline';
import { useDrawer } from "src/hooks/useDrawer";
import { successToast, errorToast, infoToast } from "@/components/toast";

const { Text } = Typography;

interface PipelineTriggersPanelProps {
  workflowId: string;
}

// ============================================================================
// Schedule Tab
// ============================================================================

const ScheduleTab: React.FC<{ workflowId: string }> = ({ workflowId }) => {
  const {
    schedules,
    triggersLoading,
    getSchedules,
    deleteSchedule,
    pauseSchedule,
    resumeSchedule,
    triggerSchedule,
  } = useBudPipeline();
  const { openDrawer } = useDrawer();

  useEffect(() => {
    getSchedules(workflowId);
  }, [workflowId]);

  const handlePauseResume = async (schedule: PipelineSchedule) => {
    if (schedule.enabled) {
      const success = await pauseSchedule(schedule.id);
      if (success) successToast('Schedule paused');
    } else {
      const success = await resumeSchedule(schedule.id);
      if (success) successToast('Schedule resumed');
    }
  };

  const handleTriggerNow = async (id: string) => {
    const success = await triggerSchedule(id);
    if (success) {
      successToast('Workflow triggered');
    } else {
      errorToast('Failed to trigger workflow');
    }
  };

  const handleDelete = async (id: string) => {
    const success = await deleteSchedule(id);
    if (success) {
      successToast('Schedule deleted');
    } else {
      errorToast('Failed to delete schedule');
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <span className="text-white">{name}</span>
      ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_: any, record: PipelineSchedule) => {
        const statusClass =
          record.status === "active"
            ? "bg-green-500/20 text-green-500"
            : record.status === "paused"
            ? "bg-yellow-500/20 text-yellow-500"
            : record.status === "expired"
            ? "bg-gray-500/20 text-gray-500"
            : "bg-gray-500/20 text-gray-500";
        return (
          <Tag className={`border-0 text-[10px] capitalize ${statusClass}`}>
            {record.status}
          </Tag>
        );
      },
    },
    {
      title: 'Schedule',
      key: 'schedule',
      render: (_: any, record: PipelineSchedule) => {
        const scheduleValue =
          record.schedule.type === "one_time"
            ? record.schedule.run_at
            : record.schedule.expression;

        return (
          <div className="flex items-center gap-2 flex-wrap">
            <Tag color="blue">{record.schedule.type}</Tag>
            {scheduleValue ? (
              <Tag className="bg-white/10 text-white text-[0.65rem] border-none">
                {scheduleValue}
              </Tag>
            ) : (
              <Text className="text-xs text-gray-500">-</Text>
            )}
          </div>
        );
      },
    },
    {
      title: 'Next Run',
      dataIndex: 'next_run_at',
      key: 'next_run_at',
      render: (date: string) =>
        date ? (
          <Tooltip title={new Date(date).toLocaleString()}>
            {formatDistanceToNow(new Date(date), { addSuffix: true })}
          </Tooltip>
        ) : (
          '-'
        ),
    },
    {
      title: 'Runs',
      dataIndex: 'run_count',
      key: 'run_count',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: PipelineSchedule) => (
        <Space>
          <Tooltip title={record.enabled ? 'Pause' : 'Resume'}>
            <Button
              type="text"
              size="small"
              className="text-white"
              icon={record.enabled ? <PauseOutlined /> : <PlayCircleOutlined />}
              onClick={() => handlePauseResume(record)}
            />
          </Tooltip>
          <Tooltip title="Trigger Now">
            <Button
              type="text"
              size="small"
              className="text-white"
              icon={<ThunderboltOutlined />}
              onClick={() => handleTriggerNow(record.id)}
            />
          </Tooltip>
          <Popconfirm
            title="Delete this schedule?"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button
              type="text"
              size="small"
              danger
              className="text-white hover:!bg-red-500/20"
              icon={<DeleteOutlined />}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const filteredSchedules = schedules.filter((s) => s.workflow_id === workflowId);

  return (
    <div>
      <div className="flex justify-between items-start mb-4">
        <div>
          <div className="text-[#EEEEEE] font-semibold text-base">Schedules</div>
          <div className="text-[#808080] text-xs mt-1">
            Run this pipeline automatically at specified times
          </div>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => openDrawer("pipeline-create-schedule", { workflowId })}
        >
          Add Schedule
        </Button>
      </div>

      {filteredSchedules.length > 0 ? (
        <Table
          dataSource={filteredSchedules}
          columns={columns}
          rowKey="id"
          loading={triggersLoading}
          pagination={false}
          className="workflow-executions-table"
          bordered={false}
        />
      ) : (
        <div className="flex items-center justify-center h-[300px] bg-[#0D0D0D] rounded-lg border border-[#1F1F1F]">
          <Empty
            description="No schedules configured"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Webhook Tab
// ============================================================================

const WebhookTab: React.FC<{ workflowId: string }> = ({ workflowId }) => {
  const {
    webhooks,
    triggersLoading,
    getWebhooks,
    createWebhook,
    deleteWebhook,
    rotateWebhookSecret,
  } = useBudPipeline();

  const [modalOpen, setModalOpen] = useState(false);
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    getWebhooks(workflowId);
  }, [workflowId]);

  const handleCreate = async (values: any) => {
    const result = await createWebhook({
      workflow_id: workflowId,
      name: values.name,
      require_secret: values.require_secret ?? true,
      params: {},
    });

    if (result) {
      successToast('Webhook created');
      if (result.secret) {
        setNewSecret(result.secret);
      }
      setModalOpen(false);
      form.resetFields();
    } else {
      errorToast('Failed to create webhook');
    }
  };

  const handleDelete = async (id: string) => {
    const success = await deleteWebhook(id);
    if (success) {
      successToast('Webhook deleted');
    }
  };

  const handleRotateSecret = async (id: string) => {
    const secret = await rotateWebhookSecret(id);
    if (secret) {
      setNewSecret(secret);
      successToast('Secret rotated');
    } else {
      errorToast('Failed to rotate secret');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    successToast('Copied to clipboard');
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: PipelineWebhook) => (
        <Space>
          <span className="text-white">{name}</span>
          <Tag color={record.enabled ? 'green' : 'default'}>
            {record.enabled ? 'Active' : 'Disabled'}
          </Tag>
        </Space>
      ),
    },
    {
      title: 'Endpoint',
      dataIndex: 'endpoint_url',
      key: 'endpoint_url',
      render: (url: string) => (
        <Space>
          <Text code className="text-xs">{url}</Text>
          <Button
            type="text"
            size="small"
            icon={<CopyOutlined />}
            onClick={() => copyToClipboard(url)}
          />
        </Space>
      ),
    },
    {
      title: 'Trigger Count',
      dataIndex: 'trigger_count',
      key: 'trigger_count',
    },
    {
      title: 'Last Triggered',
      dataIndex: 'last_triggered_at',
      key: 'last_triggered_at',
      render: (date: string) =>
        date ? formatDistanceToNow(new Date(date), { addSuffix: true }) : 'Never',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: PipelineWebhook) => (
        <Space>
          <Tooltip title="Rotate Secret">
            <Button
              type="text"
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => handleRotateSecret(record.id)}
            />
          </Tooltip>
          <Popconfirm
            title="Delete this webhook?"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="p-4">
      <div className="flex justify-between items-center mb-4">
        <Text className="text-gray-400">
          Webhooks allow external systems to trigger this workflow via HTTP.
        </Text>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalOpen(true)}
        >
          Add Webhook
        </Button>
      </div>

      {webhooks.length > 0 ? (
        <Table
          dataSource={webhooks.filter((w) => w.workflow_id === workflowId)}
          columns={columns}
          rowKey="id"
          loading={triggersLoading}
          pagination={false}
          className="dark-table"
        />
      ) : (
        <Empty
          description="No webhooks configured"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" onClick={() => setModalOpen(true)}>
            Create First Webhook
          </Button>
        </Empty>
      )}

      {/* Create Modal */}
      <Modal
        title="Create Webhook"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        className="dark-modal"
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{ require_secret: true }}
        >
          <Form.Item
            name="name"
            label="Webhook Name"
            rules={[{ required: true, message: 'Name is required' }]}
          >
            <Input placeholder="CI/CD Trigger" />
          </Form.Item>

          <Form.Item
            name="require_secret"
            valuePropName="checked"
            label="Require Secret"
            extra="When enabled, requests must include X-Webhook-Secret header"
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* Secret Display Modal */}
      <Modal
        title={
          <Space>
            <KeyOutlined />
            Webhook Secret
          </Space>
        }
        open={!!newSecret}
        onCancel={() => setNewSecret(null)}
        footer={
          <Button type="primary" onClick={() => setNewSecret(null)}>
            Done
          </Button>
        }
        className="dark-modal"
      >
        <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded mb-4">
          <Text className="text-yellow-500">
            Save this secret now! It will not be shown again.
          </Text>
        </div>
        <div className="flex items-center gap-2">
          <Input.Password value={newSecret || ''} readOnly />
          <Button
            icon={<CopyOutlined />}
            onClick={() => newSecret && copyToClipboard(newSecret)}
          >
            Copy
          </Button>
        </div>
        <div className="mt-4 text-gray-400 text-sm">
          Use this header when calling the webhook:
          <pre className="mt-2 p-2 bg-[#0d0d0d] rounded text-xs">
            X-Webhook-Secret: {newSecret}
          </pre>
        </div>
      </Modal>
    </div>
  );
};

// ============================================================================
// Event Trigger Tab
// ============================================================================

const EventTriggerTab: React.FC<{ workflowId: string }> = ({ workflowId }) => {
  const {
    eventTriggers,
    triggersLoading,
    getEventTriggers,
    createEventTrigger,
    deleteEventTrigger,
  } = useBudPipeline();

  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    getEventTriggers(workflowId);
  }, [workflowId]);

  const handleCreate = async (values: any) => {
    const result = await createEventTrigger({
      workflow_id: workflowId,
      name: values.name,
      event_type: values.event_type,
      filters: {},
      params: {},
    });

    if (result) {
      successToast('Event trigger created');
      setModalOpen(false);
      form.resetFields();
    } else {
      errorToast('Failed to create event trigger');
    }
  };

  const handleDelete = async (id: string) => {
    const success = await deleteEventTrigger(id);
    if (success) {
      successToast('Event trigger deleted');
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: PipelineEventTrigger) => (
        <Space>
          <span className="text-white">{name}</span>
          <Tag color={record.enabled ? 'green' : 'default'}>
            {record.enabled ? 'Active' : 'Disabled'}
          </Tag>
        </Space>
      ),
    },
    {
      title: 'Event Type',
      key: 'event_type',
      render: (_: any, record: PipelineEventTrigger) => {
        const eventInfo = SUPPORTED_EVENT_TYPES.find(
          (e) => e.value === record.config.event_type
        );
        return (
          <Tooltip title={eventInfo?.description}>
            <Tag color="purple">{eventInfo?.label || record.config.event_type}</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: 'Trigger Count',
      dataIndex: 'trigger_count',
      key: 'trigger_count',
    },
    {
      title: 'Last Triggered',
      dataIndex: 'last_triggered_at',
      key: 'last_triggered_at',
      render: (date: string) =>
        date ? formatDistanceToNow(new Date(date), { addSuffix: true }) : 'Never',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: PipelineEventTrigger) => (
        <Popconfirm
          title="Delete this event trigger?"
          onConfirm={() => handleDelete(record.id)}
        >
          <Button type="text" size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div className="p-4">
      <div className="flex justify-between items-center mb-4">
        <Text className="text-gray-400">
          Event triggers run this workflow when platform events occur.
        </Text>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalOpen(true)}
        >
          Add Event Trigger
        </Button>
      </div>

      {eventTriggers.length > 0 ? (
        <Table
          dataSource={eventTriggers.filter((t) => t.workflow_id === workflowId)}
          columns={columns}
          rowKey="id"
          loading={triggersLoading}
          pagination={false}
          className="dark-table"
        />
      ) : (
        <Empty
          description="No event triggers configured"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" onClick={() => setModalOpen(true)}>
            Create First Event Trigger
          </Button>
        </Empty>
      )}

      <Modal
        title="Create Event Trigger"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        className="dark-modal"
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="name"
            label="Trigger Name"
            rules={[{ required: true, message: 'Name is required' }]}
          >
            <Input placeholder="Auto-benchmark on model add" />
          </Form.Item>

          <Form.Item
            name="event_type"
            label="Event Type"
            rules={[{ required: true, message: 'Event type is required' }]}
          >
            <Select placeholder="Select event type">
              {SUPPORTED_EVENT_TYPES.map((event) => (
                <Select.Option key={event.value} value={event.value}>
                  <div>
                    <div>{event.label}</div>
                    <div className="text-xs text-gray-400">{event.description}</div>
                  </div>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

export const PipelineTriggersPanel: React.FC<PipelineTriggersPanelProps> = ({
  workflowId,
}) => {
  // Only show schedules for now (webhooks and event triggers hidden)
  return <ScheduleTab workflowId={workflowId} />;
};

export default PipelineTriggersPanel;
