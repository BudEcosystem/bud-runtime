import React, { useEffect, useState } from 'react';
import { Table, Tooltip, Select, Button } from 'antd';
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
import ProjectTags from 'src/flows/components/ProjectTags';
import { capitalize } from '@/lib/utils';
import { endpointStatusMapping } from '@/lib/colorMapping';
import { errorToast, successToast } from '@/components/toast';
import { useConfirmAction } from '@/hooks/useConfirmAction';


interface GuardrailsListTableProps {
  projectId?: string;
}

const GuardrailsListTable: React.FC<GuardrailsListTableProps> = ({ projectId: propProjectId }) => {
  const router = useRouter();
  const { slug } = router.query;
  const projectId = propProjectId || (slug as string);
  const [searchValue, setSearchValue] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [selectedRow, setSelectedRow] = useState<any>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmVisible, setConfirmVisible] = useState(false);
  const { contextHolder, openConfirm } = useConfirmAction()

  const {
    guardrails,
    isLoading,
    fetchGuardrails,
    setFilters,
    deleteGuardrail,
    pagination,
    setPagination
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

  const confirmDelete = (record: GuardrailProfile) => {
    if (!record) {
      errorToast('No guardrail selected');
      return;
    }
    setSelectedRow(record);
    setConfirmVisible(true);
    openConfirm({
      message: `You're about to delete the ${record?.name}`,
      description: 'Once you delete the guardrail, it will not be recovered. If the deployment code is being used anywhere it wont function. Are you sure?',
      cancelAction: () => {
      },
      cancelText: 'Cancel',
      loading: confirmLoading,
      key: 'delete-guardrail',
      okAction: async () => {
        if (!record) {
          errorToast('No record selected');
          return;
        };
        setConfirmLoading(true);
        const result = await deleteGuardrail(record.id, projectId as string);
        if (result?.data) {
          await fetchGuardrails(projectId);
          successToast('Guardrail deleted successfully');
        }
        await fetchGuardrails(projectId);
        setConfirmLoading(false);
        setConfirmVisible(false);
      },
      okText: 'Delete',
      type: 'warining'
    });
  }

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
          <ProjectTags
            name={capitalize(config.label)}
            color={endpointStatusMapping[capitalize(config.label)]}
            textClass="text-[.75rem]"
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
    {
      title: '',
      dataIndex: '',
      key: 'actions',
      width: 200,
      render: (_, record) => (
        <div className=' w-[2rem] h-auto block'>
          <div
            className='bg-transparent border-none p-0 cursor-pointer group'
            onClick={(event) => {
              event.stopPropagation();
              confirmDelete(record)
            }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 14 15" fill="none">
              <path className="fill-[#B3B3B3] group-hover:fill-[#EEEEEE] transition-colors duration-200" fillRule="evenodd" clipRule="evenodd" d="M5.13327 1.28906C4.85713 1.28906 4.63327 1.51292 4.63327 1.78906C4.63327 2.0652 4.85713 2.28906 5.13327 2.28906H8.8666C9.14274 2.28906 9.3666 2.0652 9.3666 1.78906C9.3666 1.51292 9.14274 1.28906 8.8666 1.28906H5.13327ZM2.7666 3.65573C2.7666 3.37959 2.99046 3.15573 3.2666 3.15573H10.7333C11.0094 3.15573 11.2333 3.37959 11.2333 3.65573C11.2333 3.93187 11.0094 4.15573 10.7333 4.15573H10.2661C10.2664 4.1668 10.2666 4.17791 10.2666 4.18906V11.5224C10.2666 12.0747 9.81889 12.5224 9.2666 12.5224H4.73327C4.18098 12.5224 3.73327 12.0747 3.73327 11.5224V4.18906C3.73327 4.17791 3.73345 4.1668 3.73381 4.15573H3.2666C2.99046 4.15573 2.7666 3.93187 2.7666 3.65573ZM9.2666 4.18906L4.73327 4.18906V11.5224L9.2666 11.5224V4.18906Z" />
            </svg>
          </div>
        </div>
      ),
    },
  ];

  // Handle table change (pagination, sorting)
  const handleTableChange = (newPagination: any, _filters: any, sorter: any) => {
    // Handle pagination
    if (newPagination.current !== pagination.page || newPagination.pageSize !== pagination.limit) {
      setPagination({
        page: newPagination.current,
        limit: newPagination.pageSize
      });
      // We need to fetch again with new pagination
      // Since setPagination updates store state, we can just call fetchGuardrails
      // However, state update might be async, so ideally we pass overrides or wait for effect
      // But fetchGuardrails reads from get(), so it should be fine if we call it after setPagination
      // Actually, setPagination is synchronous in Zustand if not async
      setTimeout(() => fetchGuardrails(projectId as string), 0);
    }

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
    <div className="pb-[60px] pt-[.4rem] relative CommonCustomPagination">
      {contextHolder}
      <Table<GuardrailProfile>
        columns={columns}
        dataSource={guardrails}
        rowKey="id"
        onRow={(record) => {
          return {
            className: 'group cursor-pointer hover:bg-[#1F1F1F] transition-colors',
            onClick: () => {
              router.push(`/projects/${projectId}/guardrailDetails/${record.id}`);
            },
          };
        }}
        loading={false}
        pagination={{
          className: 'small-pagination',
          current: pagination.page,
          pageSize: pagination.limit,
          total: pagination.total_count,
          showSizeChanger: true,
          pageSizeOptions: ['5', '10', '20', '50'],
        }}
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
                    <path d="M6 2v8M2 6h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
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
