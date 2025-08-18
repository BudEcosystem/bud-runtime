import React from 'react';
import { Table, Tag, Button, Space, Tooltip, ConfigProvider } from 'antd';
import { EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import { BlockingRule, BlockingRuleType, BlockingRuleStatus } from '@/stores/useBlockingRules';
import { RULE_TYPE_LABELS, RULE_STATUS_COLORS } from '@/constants/blockingRules';
import { formatDistanceToNow } from 'date-fns';
import ProjectTags from 'src/flows/components/ProjectTags';
import { endpointStatusMapping } from '@/lib/colorMapping';

interface BlockingRulesListProps {
  rules: BlockingRule[];
  loading: boolean;
  onView: (rule: BlockingRule) => void;
  onEdit: (rule: BlockingRule) => void;
  onDelete: (ruleId: string) => void;
}

export const BlockingRulesList: React.FC<BlockingRulesListProps> = ({
  rules,
  loading,
  onView,
  onEdit,
  onDelete,
}) => {

  const getStatusColor = (status: BlockingRuleStatus) => {
    return RULE_STATUS_COLORS[status] || 'default';
  };


  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <strong>{text}</strong>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'rule_type',
      key: 'rule_type',
      render: (type: BlockingRuleType) => (
        <span className="text-[#EEEEEE]">
          {RULE_TYPE_LABELS[type] || type}
        </span>
      ),
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      sorter: (a, b) => a.priority - b.priority,
    },
    {
      title: 'Blocks',
      dataIndex: 'match_count',
      key: 'match_count',
      sorter: (a, b) => (a.match_count || 0) - (b.match_count || 0),
      render: (count: number) => (
        <span className="text-[#EEEEEE]">
          {count || 0}
        </span>
      ),
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string, record: BlockingRule) => (
        <Tooltip title={`By: ${record.created_by_name || record.created_by}`}>
          {formatDistanceToNow(new Date(date))} ago
        </Tooltip>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: BlockingRuleStatus) => {
        // Map blocking rule status to deployment status colors
        // Normalize to uppercase for consistent mapping
        const normalizedStatus = status?.toUpperCase();
        const statusColorMap = {
          'ACTIVE': endpointStatusMapping['Active'],       // Green #479D5F
          'INACTIVE': '#B3B3B3',                          // Gray - disabled but not error
          'EXPIRED': endpointStatusMapping['Failed']       // Red #EC7575
        };

        return (
          <ProjectTags
            name={status.charAt(0).toUpperCase() + status.slice(1).toLowerCase()}
            color={statusColorMap[normalizedStatus] || endpointStatusMapping['Active']} // Default to green
            textClass="text-[.75rem]"
          />
        );
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: BlockingRule) => (
        <Space>
          <Tooltip title="Edit rule">
            <Button
              className='bg-transparent border-none p-0'
              onClick={(event) => {
                event.stopPropagation();
                onEdit(record);
              }}
            >
              <EditOutlined style={{ fontSize: '.875rem', color: '#B3B3B3' }} />
            </Button>
          </Tooltip>
          <Tooltip title="Delete rule">
            <Button
              className='bg-transparent border-none p-0'
              onClick={(event) => {
                event.stopPropagation();
                onDelete(record.id);
              }}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 14 15" fill="none">
                <path fillRule="evenodd" clipRule="evenodd" d="M5.13327 1.28906C4.85713 1.28906 4.63327 1.51292 4.63327 1.78906C4.63327 2.0652 4.85713 2.28906 5.13327 2.28906H8.8666C9.14274 2.28906 9.3666 2.0652 9.3666 1.78906C9.3666 1.51292 9.14274 1.28906 8.8666 1.28906H5.13327ZM2.7666 3.65573C2.7666 3.37959 2.99046 3.15573 3.2666 3.15573H10.7333C11.0094 3.15573 11.2333 3.37959 11.2333 3.65573C11.2333 3.93187 11.0094 4.15573 10.7333 4.15573H10.2661C10.2664 4.1668 10.2666 4.17791 10.2666 4.18906V11.5224C10.2666 12.0747 9.81889 12.5224 9.2666 12.5224H4.73327C4.18098 12.5224 3.73327 12.0747 3.73327 11.5224V4.18906C3.73327 4.17791 3.73345 4.1668 3.73381 4.15573H3.2666C2.99046 4.15573 2.7666 3.93187 2.7666 3.65573ZM9.2666 4.18906L4.73327 4.18906V11.5224L9.2666 11.5224V4.18906Z" fill="#B3B3B3" />
              </svg>
            </Button>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <ConfigProvider
      theme={{
        components: {
          Table: {
            headerBg: 'transparent',
            headerColor: '#EEEEEE',
            rowHoverBg: '#1F1F1F',
            colorBgContainer: 'transparent',
            colorText: '#EEEEEE',
            colorBorder: '#1F1F1F',
            colorBorderSecondary: '#1F1F1F',
            fixedHeaderSortActiveBg: 'transparent',
            bodySortBg: 'transparent',
            headerSortActiveBg: 'transparent',
            headerSortHoverBg: 'transparent',
            colorFillAlter: 'transparent',
            colorFillContent: 'transparent',
          },
          Pagination: {
            colorPrimary: '#965CDE',
            colorPrimaryHover: '#a873e5',
            colorBgContainer: '#101010',
            colorText: '#EEEEEE',
            colorTextDisabled: '#666666',
            colorBorder: '#1F1F1F',
            itemBg: '#101010',
            itemActiveBg: '#1E0C34',
            itemActiveColorDisabled: '#EEEEEE',
            itemInputBg: '#101010',
            itemLinkBg: '#101010',
            itemActiveBgDisabled: '#101010',
            colorBgTextHover: '#1F1F1F',
            colorBgTextActive: '#1E0C34',
            borderRadius: 4,
          },
          Select: {
            colorBgContainer: '#101010',
            colorBorder: '#1F1F1F',
            colorText: '#EEEEEE',
            colorBgElevated: '#101010',
            optionSelectedBg: '#965CDE',
            controlItemBgHover: '#1F1F1F',
          },
          Button: {
            // Text button specific styles
            colorBgTextHover: 'transparent',
            colorBgTextActive: 'transparent',
            colorBgContainer: 'transparent',
            colorBorder: 'transparent',
            colorText: '#EEEEEE',
            colorPrimary: '#965CDE',
            colorPrimaryHover: '#a873e5',
            colorBgContainerDisabled: 'transparent',
            colorTextDisabled: '#666666',
            paddingInline: 4,
            // Ensure no background on any state
            defaultBg: 'transparent',
            defaultHoverBg: 'transparent',
            defaultActiveBg: 'transparent',
          },
          Tooltip: {
            colorBgSpotlight: '#1A1A1A',
            colorTextLightSolid: '#EEEEEE',
          },
        },
      }}
    >
      <Table
        columns={columns}
        dataSource={rules}
        rowKey="id"
        loading={loading}
        pagination={{
          defaultPageSize: 20,
          showSizeChanger: true,
          showTotal: (total) => `Total ${total} rules`,
        }}
        onRow={(record) => ({
          onClick: () => onView(record),
          className: 'cursor-pointer hover:bg-gray-900',
          title: 'Click to view rule details',
        })}
        virtual
        bordered={false}
      />
    </ConfigProvider>
  );
};
