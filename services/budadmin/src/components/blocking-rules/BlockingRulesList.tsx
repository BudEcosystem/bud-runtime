import React from 'react';
import { Table, Tag, Button, Space, Tooltip, Badge } from 'antd';
import { EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { BlockingRule, BlockingRuleType, BlockingRuleStatus } from '@/stores/useBlockingRules';
import { Text_12_400_EEEEEE, Text_12_300_EEEEEE } from '@/components/ui/text';
import { ClientTimestamp } from '@/components/ui/ClientTimestamp';
import NoDataFount from '@/components/ui/noDataFount';

interface BlockingRulesListProps {
  rules: BlockingRule[];
  isLoading: boolean;
  onEdit: (rule: BlockingRule) => void;
  onDelete: (ruleId: string) => void;
  getRuleTypeIcon: (type: BlockingRuleType) => React.ReactNode;
  getRuleTypeColor: (type: BlockingRuleType) => string;
}

const BlockingRulesList: React.FC<BlockingRulesListProps> = ({
  rules,
  isLoading,
  onEdit,
  onDelete,
  getRuleTypeIcon,
  getRuleTypeColor,
}) => {
  const getStatusColor = (status: BlockingRuleStatus) => {
    switch (status) {
      case 'ACTIVE':
        return 'success';
      case 'INACTIVE':
        return 'default';
      case 'EXPIRED':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getRuleConfigDisplay = (type: BlockingRuleType, config: any) => {
    switch (type) {
      case 'IP_BLOCKING':
        return (
          <Tooltip title="Blocked IPs">
            <Text_12_300_EEEEEE className="truncate max-w-[200px]">
              {config.ip_addresses?.join(', ') || 'No IPs configured'}
            </Text_12_300_EEEEEE>
          </Tooltip>
        );
      case 'COUNTRY_BLOCKING':
        return (
          <Tooltip title="Blocked Countries">
            <Text_12_300_EEEEEE className="truncate max-w-[200px]">
              {config.countries?.join(', ') || 'No countries configured'}
            </Text_12_300_EEEEEE>
          </Tooltip>
        );
      case 'USER_AGENT_BLOCKING':
        return (
          <Tooltip title="Blocked Patterns">
            <Text_12_300_EEEEEE className="truncate max-w-[200px]">
              {config.patterns?.join(', ') || 'No patterns configured'}
            </Text_12_300_EEEEEE>
          </Tooltip>
        );
      case 'RATE_BASED_BLOCKING':
        return (
          <Text_12_300_EEEEEE>
            {config.threshold || 0} req/{config.window_seconds || 60}s
          </Text_12_300_EEEEEE>
        );
      default:
        return <Text_12_300_EEEEEE>-</Text_12_300_EEEEEE>;
    }
  };

  const columns: ColumnsType<BlockingRule> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string, record) => (
        <Space>
          <span style={{ color: getRuleTypeColor(record.rule_type) }}>
            {getRuleTypeIcon(record.rule_type)}
          </span>
          <Tooltip title={record.description || name}>
            <Text_12_400_EEEEEE className="truncate max-w-[150px]">
              {name}
            </Text_12_400_EEEEEE>
          </Tooltip>
        </Space>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'rule_type',
      key: 'rule_type',
      width: 150,
      render: (type: BlockingRuleType) => {
        const typeLabels = {
          IP_BLOCKING: 'IP Blocking',
          COUNTRY_BLOCKING: 'Country Blocking',
          USER_AGENT_BLOCKING: 'User Agent',
          RATE_BASED_BLOCKING: 'Rate Limiting',
        };
        return (
          <Tag color={getRuleTypeColor(type)} style={{ margin: 0 }}>
            {typeLabels[type]}
          </Tag>
        );
      },
    },
    {
      title: 'Configuration',
      dataIndex: 'rule_config',
      key: 'rule_config',
      width: 250,
      render: (config: any, record) => getRuleConfigDisplay(record.rule_type, config),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: BlockingRuleStatus) => (
        <Tag color={getStatusColor(status)} style={{ margin: 0 }}>
          {status}
        </Tag>
      ),
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      render: (priority: number) => (
        <Badge
          count={priority}
          style={{
            backgroundColor: priority <= 10 ? '#52c41a' : priority <= 50 ? '#faad14' : '#1890ff',
          }}
        />
      ),
    },
    {
      title: 'Project',
      dataIndex: 'project_name',
      key: 'project_name',
      width: 150,
      render: (name: string) => (
        <Tooltip title={name || 'Global'}>
          <Text_12_400_EEEEEE className="truncate max-w-[130px]">
            {name || 'Global'}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: 'Matches',
      dataIndex: 'match_count',
      key: 'match_count',
      width: 100,
      render: (count: number, record) => (
        <Tooltip
          title={record.last_matched_at ? `Last matched: ${new Date(record.last_matched_at).toLocaleString()}` : 'Never matched'}
        >
          <Text_12_400_EEEEEE>
            {count.toLocaleString()}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (timestamp: string) => (
        <Text_12_400_EEEEEE>
          <ClientTimestamp timestamp={timestamp} />
        </Text_12_400_EEEEEE>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 120,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="Edit">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => onEdit(record)}
            />
          </Tooltip>
          <Tooltip title="Delete">
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => onDelete(record.id)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <Table<BlockingRule>
      columns={columns}
      dataSource={rules}
      rowKey="id"
      loading={isLoading}
      pagination={{
        pageSize: 20,
        showSizeChanger: true,
        showTotal: (total) => `Total ${total} rules`,
      }}
      scroll={{ x: 1400 }}
      className="blockingRulesTable"
      locale={{
        emptyText: (
          <NoDataFount
            classNames="h-[20vh]"
            textMessage="No blocking rules found"
          />
        ),
      }}
    />
  );
};

export default BlockingRulesList;
