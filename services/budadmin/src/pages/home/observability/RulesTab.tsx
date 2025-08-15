import React, { useEffect, useState } from 'react';
import { Button, Card, Row, Col, Statistic, Select, Space, Tooltip, message, Modal, Tag } from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  SyncOutlined,
  SecurityScanOutlined,
  StopOutlined,
  GlobalOutlined,
  UserOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';
import { useBlockingRules, BlockingRuleType, BlockingRuleStatus } from '@/stores/useBlockingRules';
import BlockingRulesList from '@/components/blocking-rules/BlockingRulesList';
import BlockingRuleForm from '@/components/blocking-rules/BlockingRuleForm';
import BlockingRuleStats from '@/components/blocking-rules/BlockingRuleStats';
import { PrimaryButton, SecondaryButton } from '@/components/ui/bud/form/Buttons';
import { Text_12_400_808080, Text_14_600_EEEEEE } from '@/components/ui/text';
import { useProjects } from '@/hooks/useProjects';
import dayjs from 'dayjs';

interface RulesTabProps {
  timeRange: [dayjs.Dayjs, dayjs.Dayjs];
  isActive: boolean;
}

const RulesTab: React.FC<RulesTabProps> = ({ timeRange, isActive }) => {
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<any>(null);
  const [selectedProject, setSelectedProject] = useState<string | undefined>(undefined);
  const [selectedRuleType, setSelectedRuleType] = useState<BlockingRuleType | undefined>(undefined);
  const [selectedStatus, setSelectedStatus] = useState<BlockingRuleStatus | undefined>(undefined);

  const {
    rules,
    stats,
    isLoading,
    isCreating,
    isUpdating,
    isSyncing,
    fetchRules,
    fetchStats,
    createRule,
    updateRule,
    deleteRule,
    syncRules,
    setFilters,
    clearFilters,
  } = useBlockingRules();

  const { projects, getProjects } = useProjects();

  // Fetch projects on mount
  useEffect(() => {
    if (isActive) {
      getProjects();
    }
  }, [isActive]);

  // Fetch rules and stats when tab is active
  useEffect(() => {
    if (isActive) {
      fetchRules(selectedProject);
      fetchStats(
        selectedProject,
        timeRange[0].toISOString(),
        timeRange[1].toISOString()
      );
    }
  }, [isActive, selectedProject, timeRange]);

  // Apply filters
  useEffect(() => {
    setFilters({
      project_id: selectedProject,
      rule_type: selectedRuleType,
      status: selectedStatus,
    });
    if (isActive) {
      fetchRules(selectedProject);
    }
  }, [selectedProject, selectedRuleType, selectedStatus]);

  const handleCreateRule = () => {
    setEditingRule(null);
    setIsFormModalOpen(true);
  };

  const handleEditRule = (rule: any) => {
    setEditingRule(rule);
    setIsFormModalOpen(true);
  };

  const handleDeleteRule = (ruleId: string) => {
    Modal.confirm({
      title: 'Delete Blocking Rule',
      content: 'Are you sure you want to delete this rule? This action cannot be undone.',
      okText: 'Delete',
      okType: 'danger',
      onOk: async () => {
        await deleteRule(ruleId);
      },
    });
  };

  const handleSyncRules = async () => {
    const projectIds = selectedProject ? [selectedProject] : undefined;
    await syncRules(projectIds);
  };

  const handleFormSubmit = async (values: any) => {
    if (editingRule) {
      const success = await updateRule(editingRule.id, values);
      if (success) {
        setIsFormModalOpen(false);
      }
    } else {
      if (!selectedProject) {
        message.error('Please select a project first');
        return;
      }
      const success = await createRule(selectedProject, values);
      if (success) {
        setIsFormModalOpen(false);
      }
    }
  };

  const getRuleTypeIcon = (type: BlockingRuleType) => {
    switch (type) {
      case 'IP_BLOCKING':
        return <StopOutlined />;
      case 'COUNTRY_BLOCKING':
        return <GlobalOutlined />;
      case 'USER_AGENT_BLOCKING':
        return <UserOutlined />;
      case 'RATE_BASED_BLOCKING':
        return <ThunderboltOutlined />;
      default:
        return <SecurityScanOutlined />;
    }
  };

  const getRuleTypeColor = (type: BlockingRuleType) => {
    switch (type) {
      case 'IP_BLOCKING':
        return '#ef4444';
      case 'COUNTRY_BLOCKING':
        return '#3b82f6';
      case 'USER_AGENT_BLOCKING':
        return '#f59e0b';
      case 'RATE_BASED_BLOCKING':
        return '#10b981';
      default:
        return '#6b7280';
    }
  };

  return (
    <div className="rulesTabContainer">
      {/* Statistics Cards */}
      <BlockingRuleStats stats={stats} isLoading={isLoading} />

      {/* Filters and Actions */}
      <div className="mb-6 mt-6">
        <Row gutter={[16, 16]} align="middle">
          <Col flex="auto">
            <Space size="middle">
              <div>
                <Text_12_400_808080 className="mb-1 block">Project</Text_12_400_808080>
                <Select
                  placeholder="All Projects"
                  allowClear
                  value={selectedProject}
                  onChange={setSelectedProject}
                  style={{ width: 200 }}
                  options={projects.map(p => ({
                    label: p.name,
                    value: p.id,
                  }))}
                />
              </div>

              <div>
                <Text_12_400_808080 className="mb-1 block">Rule Type</Text_12_400_808080>
                <Select
                  placeholder="All Types"
                  allowClear
                  value={selectedRuleType}
                  onChange={setSelectedRuleType}
                  style={{ width: 180 }}
                  options={[
                    {
                      label: (
                        <span className="flex items-center gap-2">
                          <StopOutlined style={{ color: '#ef4444' }} />
                          IP Blocking
                        </span>
                      ),
                      value: 'IP_BLOCKING'
                    },
                    {
                      label: (
                        <span className="flex items-center gap-2">
                          <GlobalOutlined style={{ color: '#3b82f6' }} />
                          Country Blocking
                        </span>
                      ),
                      value: 'COUNTRY_BLOCKING'
                    },
                    {
                      label: (
                        <span className="flex items-center gap-2">
                          <UserOutlined style={{ color: '#f59e0b' }} />
                          User Agent
                        </span>
                      ),
                      value: 'USER_AGENT_BLOCKING'
                    },
                    {
                      label: (
                        <span className="flex items-center gap-2">
                          <ThunderboltOutlined style={{ color: '#10b981' }} />
                          Rate Limiting
                        </span>
                      ),
                      value: 'RATE_BASED_BLOCKING'
                    },
                  ]}
                />
              </div>

              <div>
                <Text_12_400_808080 className="mb-1 block">Status</Text_12_400_808080>
                <Select
                  placeholder="All Status"
                  allowClear
                  value={selectedStatus}
                  onChange={setSelectedStatus}
                  style={{ width: 150 }}
                  options={[
                    { label: <Tag color="success">Active</Tag>, value: 'ACTIVE' },
                    { label: <Tag color="default">Inactive</Tag>, value: 'INACTIVE' },
                    { label: <Tag color="warning">Expired</Tag>, value: 'EXPIRED' },
                  ]}
                />
              </div>

              <div className="flex items-end">
                <Button
                  icon={<ReloadOutlined />}
                  onClick={clearFilters}
                  className="mt-auto"
                >
                  Clear Filters
                </Button>
              </div>
            </Space>
          </Col>

          <Col>
            <Space>
              <SecondaryButton
                icon={<SyncOutlined />}
                onClick={handleSyncRules}
                loading={isSyncing}
              >
                Sync to Gateway
              </SecondaryButton>

              <SecondaryButton
                icon={<ReloadOutlined />}
                onClick={() => fetchRules(selectedProject)}
                loading={isLoading}
              >
                Refresh
              </SecondaryButton>

              <PrimaryButton
                icon={<PlusOutlined />}
                onClick={handleCreateRule}
                disabled={!selectedProject}
              >
                Create Rule
              </PrimaryButton>
            </Space>
          </Col>
        </Row>
      </div>

      {/* Rules List */}
      <BlockingRulesList
        rules={rules}
        isLoading={isLoading}
        onEdit={handleEditRule}
        onDelete={handleDeleteRule}
        getRuleTypeIcon={getRuleTypeIcon}
        getRuleTypeColor={getRuleTypeColor}
      />

      {/* Create/Edit Form Modal */}
      <Modal
        title={editingRule ? 'Edit Blocking Rule' : 'Create Blocking Rule'}
        open={isFormModalOpen}
        onCancel={() => setIsFormModalOpen(false)}
        footer={null}
        width={700}
        destroyOnClose
      >
        <BlockingRuleForm
          initialValues={editingRule}
          onSubmit={handleFormSubmit}
          onCancel={() => setIsFormModalOpen(false)}
          isLoading={isCreating || isUpdating}
        />
      </Modal>
    </div>
  );
};

export default RulesTab;
