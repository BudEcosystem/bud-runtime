import React, { useEffect, useState } from 'react';
import { Button, Table, Tag, Tooltip, Typography, message } from 'antd';
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { format } from 'date-fns';
import { useRouter } from 'next/router';
import { useInferences, InferenceListItem } from '@/stores/useInferences';
import InferenceFilters from '@/components/inferences/InferenceFilters';
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE, Text_16_600_FFFFFF } from '@/components/ui/text';
import SearchHeaderInput from 'src/flows/components/SearchHeaderInput';
import NoDataFount from '@/components/ui/noDataFount';
import { PrimaryButton, SecondaryButton } from '@/components/ui/bud/form/Buttons';
import ProjectTags from 'src/flows/components/ProjectTags';
import { SortIcon } from '@/components/ui/bud/table/SortIcon';
import { formatDate } from 'src/utils/formatDate';
import { useLoaderOnLoding } from 'src/hooks/useLoaderOnLoading';
import DashBoardLayout from '../layout';
import PageHeader from '@/components/ui/pageHeader';

const { Text } = Typography;

const ObservabilityPage: React.FC = () => {
  const router = useRouter();
  const [searchValue, setSearchValue] = useState('');

  const {
    inferences,
    pagination,
    isLoading,
    fetchInferences,
    setPagination,
    exportInferences,
    setFilters,
    filters,
  } = useInferences();

  useLoaderOnLoding(isLoading);

  // Fetch all inferences on mount (without project filter)
  useEffect(() => {
    fetchInferences(); // No project ID means fetch all
  }, []);

  // Handle search with debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchInferences(); // Fetch all with current filters
    }, 500);
    return () => clearTimeout(timer);
  }, [searchValue, fetchInferences]);

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

  // Format cost display
  const formatCost = (cost?: number) => {
    if (!cost) return '-';
    return `$${cost.toFixed(4)}`;
  };

  // Table columns definition
  const columns: ColumnsType<InferenceListItem> = [
    {
      title: 'Timestamp',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (timestamp: string) => (
        <Text_12_400_EEEEEE>{format(new Date(timestamp), 'MMM dd, HH:mm:ss')}</Text_12_400_EEEEEE>
      ),
      sorter: true,
      sortIcon: SortIcon,
    },
    {
      title: 'Project',
      dataIndex: 'project_name',
      key: 'project_name',
      width: 150,
      render: (project_name: string) => (
        <Tooltip title={project_name || 'N/A'}>
          <Text_12_400_EEEEEE className="truncate max-w-[130px]">
            {project_name || '-'}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: 'Deployment',
      dataIndex: 'endpoint_name',
      key: 'endpoint_name',
      width: 200,
      render: (endpoint_name: string) => (
        <Tooltip title={endpoint_name || 'N/A'}>
          <Text_12_400_EEEEEE className="truncate max-w-[180px]">
            {endpoint_name || '-'}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: 'Prompt Preview',
      dataIndex: 'prompt_preview',
      key: 'prompt_preview',
      width: 350,
      render: (prompt: string) => (
        <Tooltip title={prompt}>
          <Text_12_300_EEEEEE className="truncate max-w-[330px]">
            {prompt}
          </Text_12_300_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: 'Tokens',
      key: 'tokens',
      width: 120,
      render: (_, record) => (
        <Text_12_400_EEEEEE>
          {record.total_tokens.toLocaleString()}
        </Text_12_400_EEEEEE>
      ),
      sorter: true,
      sortIcon: SortIcon,
    },
    {
      title: 'Status',
      key: 'status',
      width: 100,
      render: (_, record) => (
        <ProjectTags
          name={record.is_success ? 'Success' : 'Failed'}
          color={record.is_success ? '#22c55e' : '#ef4444'}
          textClass="text-[.75rem]"
        />
      ),
    },
  ];

  // Handle table change (pagination, sorting)
  const handleTableChange = (newPagination: any, _filters: any, sorter: any) => {
    // Handle sorting
    if (sorter.field) {
      const sortMap: Record<string, string> = {
        timestamp: 'timestamp',
        tokens: 'tokens',
        response_time_ms: 'latency',
        cost: 'cost',
      };

      const sortBy = sortMap[sorter.field] || 'timestamp';
      const sortOrder = sorter.order === 'ascend' ? 'asc' : 'desc';

      setFilters({
        sort_by: sortBy as any,
        sort_order: sortOrder as any,
      });
      fetchInferences(); // Fetch all with new sorting
    }
  };

  // Export menu items
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
    <DashBoardLayout>
      <div className="boardPageView">
        <div className="boardPageTop">
          <PageHeader
            headding="Observability"
          />
        </div>

        <div className="boardMainContainer listingContainer pt-8">
          <div className="mb-4">
            <InferenceFilters
              projectId={'all'} // Pass a dummy ID for global view
              onFiltersChange={() => fetchInferences()}
            />
          </div>

          <Table<InferenceListItem>
                columns={columns}
                dataSource={inferences}
                rowKey="inference_id"
                loading={isLoading}
                pagination={false}
                virtual
                bordered={false}
                footer={null}
                onChange={handleTableChange}
                scroll={{ x: 1200 }}
                showSorterTooltip={true}
            onRow={(record) => ({
              onClick: (e) => {
                e.preventDefault();
                router.push(`/observability/${record.inference_id}`);
              },
              className: 'cursor-pointer hover:bg-gray-900',
            })}
                title={() => (
                  <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
                    <Text_16_600_FFFFFF className="text-[#EEEEEE]">
                      Inference Requests
                    </Text_16_600_FFFFFF>
                    <div className="flex items-center justify-between gap-x-[.8rem]">
                      <SearchHeaderInput
                        placeholder="Search by prompt or response"
                        searchValue={searchValue}
                        setSearchValue={setSearchValue}
                      />
                  <PrimaryButton
                    onClick={() => fetchInferences()}
                  >
                    <ReloadOutlined />
                    <span className="ml-2">Refresh</span>
                  </PrimaryButton>
                      <SecondaryButton
                        onClick={() => exportInferences('csv')}
                      >
                        <DownloadOutlined />
                        <span className="ml-2">Export</span>
                      </SecondaryButton>
                    </div>
                  </div>
                )}
            locale={{
              emptyText: (
                <NoDataFount
                  classNames="h-[20vh]"
                  textMessage="No observability data found"
                />
              ),
            }}
          />
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default ObservabilityPage;
