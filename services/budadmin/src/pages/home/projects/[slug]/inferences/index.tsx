import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { Table, Space, Button, Tag, Tooltip, Typography, Spin, Empty } from 'antd';
import { EyeOutlined, DownloadOutlined, CopyOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { format } from 'date-fns';
import { useInferences, InferenceListItem } from '@/stores/useInferences';
import InferenceDetailModal from '@/components/inferences/InferenceDetailModal';
import InferenceFilters from '@/components/inferences/InferenceFilters';
import { message } from 'antd';

const { Text, Title } = Typography;

const InferenceListView: React.FC = () => {
  const router = useRouter();
  const { slug: projectId } = router.query;
  const [selectedInferenceId, setSelectedInferenceId] = useState<string | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  
  const {
    inferences,
    pagination,
    isLoading,
    fetchInferences,
    setPagination,
    exportInferences,
  } = useInferences();
  
  // Fetch inferences when component mounts or projectId changes
  useEffect(() => {
    if (projectId && typeof projectId === 'string') {
      fetchInferences(projectId);
    }
  }, [projectId]);
  
  // Copy inference ID to clipboard
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    message.success('Copied to clipboard');
  };
  
  // Format tokens display
  const formatTokens = (input: number, output: number) => {
    const total = input + output;
    return `${total.toLocaleString()} (${input.toLocaleString()} / ${output.toLocaleString()})`;
  };
  
  // Table columns definition
  const columns: ColumnsType<InferenceListItem> = [
    {
      title: 'Timestamp',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (timestamp: string) => (
        <Text style={{ fontSize: 12 }}>
          {format(new Date(timestamp), 'MMM dd, yyyy HH:mm:ss')}
        </Text>
      ),
      sorter: true,
    },
    {
      title: 'Model',
      dataIndex: 'model_name',
      key: 'model_name',
      width: 200,
      render: (model_name: string, record: InferenceListItem) => (
        <Tooltip title={record.model_display_name || model_name}>
          <Text ellipsis style={{ maxWidth: 180 }}>
            {record.model_display_name || model_name}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: 'Prompt Preview',
      dataIndex: 'prompt_preview',
      key: 'prompt_preview',
      width: 300,
      render: (prompt: string) => (
        <Tooltip title={prompt}>
          <Text ellipsis style={{ maxWidth: 280 }}>
            {prompt}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: 'Response Preview',
      dataIndex: 'response_preview',
      key: 'response_preview',
      width: 300,
      render: (response: string) => (
        <Tooltip title={response}>
          <Text ellipsis style={{ maxWidth: 280 }}>
            {response}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: 'Tokens',
      key: 'tokens',
      width: 150,
      align: 'right',
      render: (_, record: InferenceListItem) => (
        <Tooltip title={`Input: ${record.input_tokens.toLocaleString()}, Output: ${record.output_tokens.toLocaleString()}`}>
          <Text style={{ fontSize: 12 }}>
            {formatTokens(record.input_tokens, record.output_tokens)}
          </Text>
        </Tooltip>
      ),
      sorter: true,
    },
    {
      title: 'Latency',
      dataIndex: 'response_time_ms',
      key: 'response_time_ms',
      width: 100,
      align: 'right',
      render: (latency: number) => (
        <Text style={{ fontSize: 12 }}>{latency.toLocaleString()} ms</Text>
      ),
      sorter: true,
    },
    {
      title: 'Cost',
      dataIndex: 'cost',
      key: 'cost',
      width: 80,
      align: 'right',
      render: (cost?: number) => (
        <Text style={{ fontSize: 12 }}>
          {cost ? `$${cost.toFixed(4)}` : '-'}
        </Text>
      ),
      sorter: true,
    },
    {
      title: 'Status',
      key: 'status',
      width: 120,
      render: (_, record: InferenceListItem) => (
        <Space size={4}>
          <Tag color={record.is_success ? 'success' : 'error'} style={{ margin: 0 }}>
            {record.is_success ? 'Success' : 'Failed'}
          </Tag>
          {record.cached && (
            <Tag color="blue" style={{ margin: 0 }}>
              Cached
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 120,
      fixed: 'right',
      render: (_, record: InferenceListItem) => (
        <Space size="small">
          <Tooltip title="View Details">
            <Button
              type="text"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => {
                setSelectedInferenceId(record.inference_id);
                setShowDetailModal(true);
              }}
            />
          </Tooltip>
          <Tooltip title="Copy ID">
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={() => copyToClipboard(record.inference_id)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];
  
  // Handle table change (pagination, sorting)
  const handleTableChange = (newPagination: any, filters: any, sorter: any) => {
    // Update pagination
    if (newPagination.current !== pagination.offset / pagination.limit + 1) {
      setPagination({
        offset: (newPagination.current - 1) * pagination.limit,
      });
      fetchInferences(projectId as string);
    }
    
    // Handle sorting
    if (sorter.order) {
      const sortMap: Record<string, string> = {
        timestamp: 'timestamp',
        tokens: 'tokens',
        response_time_ms: 'latency',
        cost: 'cost',
      };
      
      const sortBy = sortMap[sorter.field] || 'timestamp';
      const sortOrder = sorter.order === 'ascend' ? 'asc' : 'desc';
      
      useInferences.getState().setFilters({
        sort_by: sortBy as any,
        sort_order: sortOrder as any,
      });
      fetchInferences(projectId as string);
    }
  };
  
  // Export actions
  const exportMenu = [
    {
      key: 'csv',
      label: 'Export as CSV',
      onClick: () => exportInferences('csv'),
    },
    {
      key: 'json',
      label: 'Export as JSON',
      onClick: () => exportInferences('json'),
    },
  ];
  
  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Title level={4} style={{ margin: 0 }}>Inference Requests</Title>
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => fetchInferences(projectId as string)}
              loading={isLoading}
            >
              Refresh
            </Button>
            <Button.Group>
              <Button icon={<DownloadOutlined />} onClick={() => exportInferences('csv')}>
                Export CSV
              </Button>
              <Button onClick={() => exportInferences('json')}>
                Export JSON
              </Button>
            </Button.Group>
          </Space>
        </div>
        
        <InferenceFilters
          projectId={projectId as string}
          onFiltersChange={() => fetchInferences(projectId as string)}
        />
      </div>
      
      <Table
        columns={columns}
        dataSource={inferences}
        rowKey="inference_id"
        loading={isLoading}
        pagination={{
          current: Math.floor(pagination.offset / pagination.limit) + 1,
          pageSize: pagination.limit,
          total: pagination.total_count,
          showSizeChanger: true,
          showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} inferences`,
          pageSizeOptions: ['20', '50', '100'],
        }}
        onChange={handleTableChange}
        scroll={{ x: 1500 }}
        locale={{
          emptyText: (
            <Empty
              description={
                <span>
                  No inference requests found.
                  <br />
                  Try adjusting your filters or time range.
                </span>
              }
            />
          ),
        }}
      />
      
      {showDetailModal && selectedInferenceId && (
        <InferenceDetailModal
          inferenceId={selectedInferenceId}
          visible={showDetailModal}
          onClose={() => {
            setShowDetailModal(false);
            setSelectedInferenceId(null);
          }}
        />
      )}
    </div>
  );
};

export default InferenceListView;