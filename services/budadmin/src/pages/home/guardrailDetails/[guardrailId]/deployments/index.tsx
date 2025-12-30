import React, { useEffect, useState } from 'react';
import { Table, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useRouter } from 'next/router';
import { useGuardrails, Deployment } from '@/stores/useGuardrails';
import { Text_12_400_EEEEEE, Text_16_600_FFFFFF } from '@/components/ui/text';
import SearchHeaderInput from 'src/flows/components/SearchHeaderInput';
import NoDataFount from '@/components/ui/noDataFount';
import { SortIcon } from '@/components/ui/bud/table/SortIcon';
import { useLoaderOnLoding } from 'src/hooks/useLoaderOnLoading';
import { ClientTimestamp } from '@/components/ui/ClientTimestamp';
import ProjectTags from 'src/flows/components/ProjectTags';
import { capitalize } from '@/lib/utils';

const DeploymentsTab: React.FC = () => {
  const router = useRouter();
  const { guardrailId } = router.query;
  const [searchValue, setSearchValue] = useState('');

  const {
    deployments,
    isLoadingDeployments,
    fetchDeployments,
    deploymentFilters,
    setDeploymentFilters,
    deploymentPagination,
    setDeploymentPagination,
  } = useGuardrails();

  useLoaderOnLoding(isLoadingDeployments);

  // Fetch deployments when component mounts or guardrailId changes
  useEffect(() => {
    if (guardrailId && typeof guardrailId === 'string') {
      fetchDeployments(guardrailId);
    }
  }, [guardrailId]);

  // Handle search with debounce
  useEffect(() => {
    if (typeof guardrailId !== 'string') return;

    const timer = setTimeout(() => {
      if (searchValue) {
        setDeploymentFilters({
          name: searchValue,
          search: true
        });
        fetchDeployments(guardrailId);
      } else {
        setDeploymentFilters({
          name: undefined,
          search: false
        });
        fetchDeployments(guardrailId);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [searchValue, guardrailId]);

  // Get status color and label
  const getStatusConfig = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'enabled':
      case 'active':
        return { color: '#479d5f', label: 'Active' };
      case 'running':
        return { color: '#479d5f', label: 'running' };
      case 'disabled':
        return { color: '#F59E0B', label: 'Disabled' };
      case 'deleted':
        return { color: '#EF4444', label: 'Deleted' };
      case 'pending':
        return { color: '#3B82F6', label: 'Pending' };
      default:
        return { color: '#6B7280', label: status || 'Unknown' };
    }
  };

  // Table columns definition
  const columns: ColumnsType<Deployment> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (name: string) => (
        <Tooltip title={name}>
          <Text_12_400_EEEEEE className="truncate max-w-[160px]">
            {name}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
      sorter: true,
      sortIcon: SortIcon,
    },
    {
      title: 'Endpoint',
      dataIndex: 'endpoint_name',
      key: 'endpoint_name',
      width: 180,
      render: (endpoint_name: string) => (
        <Tooltip title={endpoint_name || 'N/A'}>
          <Text_12_400_EEEEEE className="truncate max-w-[160px]">
            {endpoint_name || '-'}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: 'Project',
      dataIndex: 'project_id',
      key: 'project_id',
      width: 180,
      render: (project_id: string) => (
        <Tooltip title={project_id || 'N/A'}>
          <Text_12_400_EEEEEE className="truncate max-w-[160px]">
            {project_id || '-'}
          </Text_12_400_EEEEEE>
        </Tooltip>
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
            color={config.color}
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
      width: 180,
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
  const handleTableChange = (newPagination: any, _filters: any, sorter: any) => {
    if (typeof guardrailId !== 'string') return;
    const paginationChanged = newPagination.current !== deploymentPagination.page || newPagination.pageSize !== deploymentPagination.limit;
    const newOrderBy = sorter.field && sorter.order ? `${sorter.field}:${sorter.order === 'ascend' ? 'asc' : 'desc'}` : undefined;
    const sortChanged = newOrderBy !== deploymentFilters.order_by;

    if (sortChanged && newOrderBy) {
      // When sorting changes, reset to page 1
      setDeploymentFilters({
        order_by: newOrderBy,
      });
      fetchDeployments(guardrailId);
    } else if (paginationChanged) {
      setDeploymentPagination({
        page: newPagination.current,
        limit: newPagination.pageSize
      });
      fetchDeployments(guardrailId);
    }
  };

  return (
    <div className="pb-[60px] pt-[.4rem] relative CommonCustomPagination">
      <Table<Deployment>
        columns={columns}
        dataSource={deployments}
        rowKey="id"
        loading={isLoadingDeployments}
        pagination={{
          className: 'small-pagination',
          current: deploymentPagination.page,
          pageSize: deploymentPagination.limit,
          total: deploymentPagination.total_count,
          showSizeChanger: true,
          pageSizeOptions: ['5', '10', '20', '50'],
        }}
        tableLayout="fixed"
        virtual
        bordered={false}
        footer={null}
        onChange={handleTableChange}
        showSorterTooltip={true}
        title={() => (
          <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
            <Text_16_600_FFFFFF className="text-[#EEEEEE]">
              Deployments
            </Text_16_600_FFFFFF>
            <SearchHeaderInput
              placeholder="Search by name"
              searchValue={searchValue}
              setSearchValue={setSearchValue}
            />
          </div>
        )}
        locale={{
          emptyText: (
            <NoDataFount
              classNames="h-[20vh]"
              textMessage="No deployments found for this guardrail profile"
            />
          ),
        }}
      />
    </div>
  );
};

export default DeploymentsTab;
