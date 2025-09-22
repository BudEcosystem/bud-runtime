import React, { useEffect, useState } from 'react';
import { Table, Tooltip, Select } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useRouter } from 'next/router';
import { useGuardrails, GuardrailProfile } from '@/stores/useGuardrails';
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE, Text_16_600_FFFFFF } from '../../text';
import SearchHeaderInput from 'src/flows/components/SearchHeaderInput';
import NoDataFount from '../../noDataFount';
import { PrimaryButton, SecondaryButton } from '../form/Buttons';
import Tags from 'src/flows/components/DrawerTags';
import { SortIcon } from './SortIcon';
import { useLoaderOnLoding } from 'src/hooks/useLoaderOnLoading';
import { ClientTimestamp } from '../../ClientTimestamp';


interface GuardrailsListTableProps {
  projectId?: string;
}

const GuardrailsListTable: React.FC<GuardrailsListTableProps> = ({ projectId: propProjectId }) => {
  const router = useRouter();
  const { slug } = router.query;
  const projectId = propProjectId || (slug as string);
  const [searchValue, setSearchValue] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');

  const {
    guardrails,
    isLoading,
    fetchGuardrails,
    setFilters,
  } = useGuardrails();

  useLoaderOnLoding(isLoading);

  // Fetch guardrails when component mounts or projectId changes
  useEffect(() => {
    if (projectId && typeof projectId === 'string') {
      console.log('Fetching guardrails for project:', projectId);
      fetchGuardrails(projectId);
    }
  }, [projectId]); // Remove fetchGuardrails from deps to avoid infinite loop

  // Handle search with debounce
  useEffect(() => {
    if (!projectId || searchValue === '') return;

    const timer = setTimeout(() => {
      setFilters({
        name: searchValue || undefined,
        search: searchValue ? true : false
      });
      fetchGuardrails(projectId);
    }, 500);
    return () => clearTimeout(timer);
  }, [searchValue, projectId]); // Remove function deps

  useEffect(() => {
    console.log("guardrails", guardrails)
  }, [guardrails]); // Remove function deps

  // Handle status filter change
  useEffect(() => {
    if (!projectId) return;

    // Only fetch when status filter actually changes
    const timer = setTimeout(() => {
      setFilters({
        status: statusFilter || undefined
      });
      fetchGuardrails(projectId);
    }, 100);

    return () => clearTimeout(timer);
  }, [statusFilter, projectId]); // Remove function deps

  // Get status color and label
  const getStatusConfig = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'active':
        return { color: '#479d5f', label: 'Active' };
      case 'inactive':
        return { color: '#F59E0B', label: 'Inactive' };
      case 'draft':
        return { color: '#6B7280', label: 'Draft' };
      default:
        return { color: '#6B7280', label: status || 'Unknown' };
    }
  };

  // Get guard type color
  const getGuardTypeColor = (type: string) => {
    // You can customize colors based on guard types
    const colors = [
      '#3B82F6', // blue
      '#8B5CF6', // purple
      '#EC4899', // pink
      '#14B8A6', // teal
      '#F59E0B', // amber
    ];
    const index = type.length % colors.length;
    return colors[index];
  };

  // Table columns definition
  const columns: ColumnsType<GuardrailProfile> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 300,
      render: (name: string) => (
        <Tooltip title={name}>
          <Text_12_400_EEEEEE className="truncate max-w-[280px]">
            {name}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
      sorter: true,
      sortIcon: SortIcon,
    },
    {
      title: 'Guard Types',
      dataIndex: 'guard_types',
      key: 'guard_types',
      width: 350,
      render: (guard_types: string[]) => (
        <div className="flex flex-wrap gap-1">
          {guard_types && guard_types.length > 0 ? (
            guard_types.map((type, index) => (
              <Tags
                key={index}
                name={type}
                color={getGuardTypeColor(type)}
              />
            ))
          ) : (
            <Text_12_300_EEEEEE>No guard types</Text_12_300_EEEEEE>
          )}
        </div>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => {
        const config = getStatusConfig(status);
        return (
          <Tags
            name={config.label}
            color={config.color}
          />
        );
      },
      sorter: true,
      sortIcon: SortIcon,
    },
    {
      title: 'Created At',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 200,
      render: (created_at: string) => (
        <Text_12_400_EEEEEE>
          <ClientTimestamp timestamp={created_at} />
        </Text_12_400_EEEEEE>
      ),
      sorter: true,
      sortIcon: SortIcon,
    },
  ];

  // Handle table change (pagination, sorting)
  const handleTableChange = (_newPagination: any, _filters: any, sorter: any) => {
    // Handle sorting
    if (sorter.field) {
      const sortOrder = sorter.order === 'ascend' ? 'asc' : 'desc';
      const orderBy = `${sorter.field}:${sortOrder}`;

      setFilters({
        order_by: orderBy,
      });
      fetchGuardrails(projectId as string);
    }
  };


  return (
    <div className="pb-[60px] pt-[.4rem]">
      <Table<GuardrailProfile>
        columns={columns}
        dataSource={guardrails}
        rowKey="id"
        loading={false}
        pagination={false}
        virtual
        bordered={false}
        footer={null}
        onChange={handleTableChange}
        scroll={{ x: 970 }}
        showSorterTooltip={true}
        title={() => (
          <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
            <Text_16_600_FFFFFF className="text-[#EEEEEE]">
              Guardrail Profiles
            </Text_16_600_FFFFFF>
            <div className="flex items-center justify-between gap-x-[.8rem] hidden">
              <SearchHeaderInput
                placeholder="Search by name"
                searchValue={searchValue}
                setSearchValue={setSearchValue}
              />
              <Select
                placeholder="All Status"
                value={statusFilter || undefined}
                onChange={(value) => setStatusFilter(value)}
                style={{ width: 140 }}
                allowClear
              >
                <Select.Option value="">All Status</Select.Option>
                <Select.Option value="active">Active</Select.Option>
                <Select.Option value="inactive">Inactive</Select.Option>
                <Select.Option value="draft">Draft</Select.Option>
              </Select>
              <PrimaryButton
                onClick={() => fetchGuardrails(projectId as string)}
              >
                <ReloadOutlined />
                <span className="ml-2">Refresh</span>
              </PrimaryButton>
              <PrimaryButton
                onClick={() => router.push(`/home/projects/${projectId}/guardrails/create`)}
              >
                <span style={{ display: 'flex', alignItems: 'center' }}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M6 2v8M2 6h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                  <span className="ml-2">Add Guardrail</span>
                </span>
              </PrimaryButton>
            </div>
          </div>
        )}
        locale={{
          emptyText: (
            <NoDataFount
              classNames="h-[20vh]"
              textMessage="No guardrail profiles found"
            />
          ),
        }}
      />
    </div>
  );
};

export default GuardrailsListTable;
