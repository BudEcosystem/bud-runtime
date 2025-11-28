import React, { useEffect, useState } from 'react';
import { Table, Tooltip, Popover, Spin } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { ChevronRight } from 'lucide-react';
import type { ColumnsType } from 'antd/es/table';
import { useRouter } from 'next/router';
import { useGuardrails, Probe, ProbeRule } from '@/stores/useGuardrails';
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE, Text_16_600_FFFFFF, Text_14_600_EEEEEE } from '@/components/ui/text';
import SearchHeaderInput from 'src/flows/components/SearchHeaderInput';
import NoDataFount from '@/components/ui/noDataFount';
import { PrimaryButton } from '@/components/ui/bud/form/Buttons';
import Tags from 'src/flows/components/DrawerTags';
import { SortIcon } from '@/components/ui/bud/table/SortIcon';
import { useLoaderOnLoding } from 'src/hooks/useLoaderOnLoading';
import { ClientTimestamp } from '@/components/ui/ClientTimestamp';
import ProjectTags from 'src/flows/components/ProjectTags';
import { capitalize } from '@/lib/utils';

const ProbesTab: React.FC = () => {
  const router = useRouter();
  const { guardrailId } = router.query;
  const [searchValue, setSearchValue] = useState('');
  const [expandedRowKeys, setExpandedRowKeys] = useState<string[]>([]);
  const [loadingRules, setLoadingRules] = useState<Record<string, boolean>>({});
  const [probeRulesCache, setProbeRulesCache] = useState<Record<string, ProbeRule[]>>({});
  const [rulesPagination, setRulesPagination] = useState<Record<string, { page: number; limit: number; total_count: number; total_pages: number; has_more: boolean }>>({});

  const {
    probes,
    isLoadingProbes,
    fetchProbes,
    fetchProbeRules,
    setProbeFilters,
    probePagination,
    setProbePagination,
  } = useGuardrails();

  useLoaderOnLoding(isLoadingProbes);

  // Fetch probes when component mounts or guardrailId changes
  useEffect(() => {
    if (guardrailId && typeof guardrailId === 'string') {
      fetchProbes(guardrailId);
    }
  }, [guardrailId]);

  // Handle search with debounce
  useEffect(() => {
    if (!guardrailId) return;

    const timer = setTimeout(() => {
      if (searchValue) {
        setProbeFilters({
          name: searchValue,
          search: true
        });
        fetchProbes(guardrailId as string);
      } else {
        setProbeFilters({
          name: undefined,
          search: false
        });
        fetchProbes(guardrailId as string);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [searchValue, guardrailId]);

  // Handle row expansion to load rules
  const handleExpand = async (expanded: boolean, record: Probe) => {
    if (expanded && !probeRulesCache[record.id]) {
      // Load first page of rules for this probe
      setLoadingRules(prev => ({ ...prev, [record.id]: true }));
      const { rules, pagination } = await fetchProbeRules(guardrailId as string, record.id, 1, 10);
      setProbeRulesCache(prev => ({ ...prev, [record.id]: rules }));
      setRulesPagination(prev => ({ ...prev, [record.id]: pagination }));
      setLoadingRules(prev => ({ ...prev, [record.id]: false }));
    }
  };

  // Handle pagination change for rules
  const handleRulesPaginationChange = async (probeId: string, page: number, pageSize: number) => {
    setLoadingRules(prev => ({ ...prev, [probeId]: true }));
    const { rules, pagination } = await fetchProbeRules(guardrailId as string, probeId, page, pageSize);
    setProbeRulesCache(prev => ({ ...prev, [probeId]: rules }));
    setRulesPagination(prev => ({ ...prev, [probeId]: pagination }));
    setLoadingRules(prev => ({ ...prev, [probeId]: false }));
  };

  // Get status color for rules
  const getRuleStatusConfig = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'enabled':
      case 'active':
        return { color: '#479d5f', label: 'Active' };
      case 'disabled':
        return { color: '#F59E0B', label: 'Disabled' };
      case 'deleted':
        return { color: '#EF4444', label: 'Deleted' };
      default:
        return { color: '#6B7280', label: status || 'Unknown' };
    }
  };

  // Nested table for rules
  const expandedRowRender = (record: Probe) => {
    const rules = probeRulesCache[record.id] || [];
    const isLoading = loadingRules[record.id];

    if (isLoading) {
      return (
        <div className="flex justify-center items-center py-8">
          <Spin size="default" />
          <span className="ml-3 text-[#B3B3B3]">Loading rules...</span>
        </div>
      );
    }

    if (!rules || rules.length === 0) {
      return (
        <div className="py-6 text-center text-[#757575]">
          No rules found for this probe
        </div>
      );
    }

    const rulesColumns: ColumnsType<ProbeRule> = [
      {
        title: 'Rule Name',
        dataIndex: 'name',
        key: 'name',
        width: 180,
        render: (name: string) => (
          <Text_12_400_EEEEEE className="truncate max-w-[160px]">{name}</Text_12_400_EEEEEE>
        ),
      },
      {
        title: 'Description',
        dataIndex: 'description',
        key: 'description',
        width: 250,
        render: (description: string) => (
          <Popover
            content={
              <div className="max-w-[400px] break-words p-[.8rem]">
                <Text_12_400_EEEEEE>{description || 'No description'}</Text_12_400_EEEEEE>
              </div>
            }
            placement="top"
            rootClassName="traits-popover"
          >
            <div className="cursor-pointer" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <Text_12_300_EEEEEE className="truncate max-w-[230px]">
                {description || '-'}
              </Text_12_300_EEEEEE>
            </div>
          </Popover>
        ),
      },
      {
        title: 'Guardrail Type',
        dataIndex: 'guard_types',
        key: 'guard_types',
        width: 200,
        render: (guard_types: string[]) => (
          <div className="flex flex-wrap gap-1">
            {guard_types && guard_types.length > 0 ? (
              guard_types.slice(0, 2).map((type, index) => (
                <Tags
                  key={index}
                  name={capitalize(type?.replace(/_/g, ' ') || '')}
                  color="#D1B854"
                  textClass="text-[.65rem]"
                />
              ))
            ) : (
              <Text_12_300_EEEEEE>-</Text_12_300_EEEEEE>
            )}
            {guard_types && guard_types.length > 2 && (
              <span className="text-[.65rem] text-[#757575]">+{guard_types.length - 2}</span>
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
          const config = getRuleStatusConfig(status);
          return (
            <ProjectTags
              name={capitalize(config.label)}
              color={config.color}
              textClass="text-[.65rem]"
            />
          );
        },
      },
    ];

    const pagination = rulesPagination[record.id];

    return (
      <div className="bg-[transparent] px-4 py-2">
        <Text_14_600_EEEEEE className="mb-3 block">
          Rules ({pagination?.total_count ?? rules.length})
        </Text_14_600_EEEEEE>
        <Table
          columns={rulesColumns}
          dataSource={rules}
          rowKey="id"
          pagination={{
            className: 'small-pagination',
            current: pagination?.page || 1,
            pageSize: pagination?.limit || 10,
            total: pagination?.total_count || rules.length,
            showSizeChanger: true,
            pageSizeOptions: ['5', '10', '20'],
            onChange: (page, pageSize) => handleRulesPaginationChange(record.id, page, pageSize),
          }}
          size="small"
          bordered={false}
          className="nested-rules-table"
        />
      </div>
    );
  };

  // Get status color and label
  const getStatusConfig = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'active':
        return { color: '#479d5f', label: 'Active' };
      case 'disabled':
        return { color: '#F59E0B', label: 'Disabled' };
      case 'deleted':
        return { color: '#EF4444', label: 'Deleted' };
      default:
        return { color: '#6B7280', label: status || 'Unknown' };
    }
  };

  // Get tag color
  const getTagColor = (tag: string) => {
    const colors = [
      '#3B82F6', // blue
      '#8B5CF6', // purple
      '#EC4899', // pink
      '#14B8A6', // teal
      '#F59E0B', // amber
    ];
    const index = tag.length % colors.length;
    return colors[index];
  };

  // Table columns definition
  const columns: ColumnsType<Probe> = [
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
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      width: 250,
      render: (description: string) => (
        <Popover
          content={
            <div className="max-w-[400px] break-words p-[.8rem]">
              <Text_12_400_EEEEEE>{description || 'No description'}</Text_12_400_EEEEEE>
            </div>
          }
          placement="top"
          rootClassName="traits-popover"
        >
          <div className="cursor-pointer" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            <Text_12_300_EEEEEE className="truncate max-w-[230px]">
              {description || '-'}
            </Text_12_300_EEEEEE>
          </div>
        </Popover>
      ),
    },
    {
      title: 'Provider',
      dataIndex: 'provider_name',
      key: 'provider_name',
      width: 150,
      render: (provider_name: string, record) => (
        <Tooltip title={provider_name || record.provider_type || 'N/A'}>
          <Text_12_400_EEEEEE className="truncate max-w-[130px] capitalize">
            {provider_name || record.provider_type?.replace(/_/g, ' ') || '-'}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: 'Tags',
      dataIndex: 'tags',
      key: 'tags',
      width: 250,
      render: (tags: Array<{ name: string; color: string }>) => (
        <div className="flex flex-wrap gap-1">
          {tags && tags.length > 0 ? (
            tags.slice(0, 3).map((tag, index) => (
              <Tags
                key={index}
                name={tag.name}
                color={tag.color || getTagColor(tag.name)}
                textClass="text-[.65rem]"
              />
            ))
          ) : (
            <Text_12_300_EEEEEE>-</Text_12_300_EEEEEE>
          )}
          {tags && tags.length > 3 && (
            <span className="text-[.65rem] text-[#757575]">+{tags.length - 3}</span>
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
    // Handle pagination
    if (newPagination.current !== probePagination.page || newPagination.pageSize !== probePagination.limit) {
      setProbePagination({
        page: newPagination.current,
        limit: newPagination.pageSize
      });
      // Zustand state updates are synchronous, so we can fetch immediately
      fetchProbes(guardrailId as string);
    }

    // Handle sorting
    if (sorter.field) {
      const sortOrder = sorter.order === 'ascend' ? 'asc' : 'desc';
      const orderBy = `${sorter.field}:${sortOrder}`;

      setProbeFilters({
        order_by: orderBy,
      });
      fetchProbes(guardrailId as string);
    }
  };

  return (
    <div className="pb-[60px] pt-[.4rem] relative CommonCustomPagination">
      <Table<Probe>
        columns={columns}
        dataSource={probes}
        rowKey="id"
        loading={false}
        pagination={{
          className: 'small-pagination',
          current: probePagination.page,
          pageSize: probePagination.limit,
          total: probePagination.total_count,
          showSizeChanger: true,
          pageSizeOptions: ['5', '10', '20', '50'],
        }}
        expandable={{
          expandedRowRender,
          expandedRowKeys,
          onExpand: handleExpand,
          onExpandedRowsChange: (keys) => setExpandedRowKeys(keys as string[]),
          expandIcon: ({ expanded, onExpand, record }) => (
            <div
              className={`
                w-6 h-6 flex items-center justify-center
                rounded-md cursor-pointer
                bg-[transparent] hover:bg-[#252525]
                border border-[#2A2A2A] hover:border-[#3A3A3A]
                transition-all duration-200 ease-in-out
                group
              `}
              onClick={(e) => onExpand(record, e)}
            >
              <ChevronRight
                className={`
                  w-4 h-4 text-[#808080] group-hover:text-[#EEEEEE]
                  transition-transform duration-200 ease-in-out
                  ${expanded ? 'rotate-90' : 'rotate-0'}
                `}
              />
            </div>
          ),
        }}
        virtual
        bordered={false}
        footer={null}
        onChange={handleTableChange}
        scroll={{ x: 1100 }}
        showSorterTooltip={true}
        title={() => (
          <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
            <Text_16_600_FFFFFF className="text-[#EEEEEE]">
              Probes
            </Text_16_600_FFFFFF>
            <div className="flex items-center justify-between gap-x-[.8rem]">
              <SearchHeaderInput
                placeholder="Search by name"
                searchValue={searchValue}
                setSearchValue={setSearchValue}
              />
              <PrimaryButton
                onClick={() => fetchProbes(guardrailId as string)}
              >
                <ReloadOutlined />
                <span className="ml-2">Refresh</span>
              </PrimaryButton>
            </div>
          </div>
        )}
        locale={{
          emptyText: (
            <NoDataFount
              classNames="h-[20vh]"
              textMessage="No probes found for this guardrail profile"
            />
          ),
        }}
      />
    </div>
  );
};

export default ProbesTab;
