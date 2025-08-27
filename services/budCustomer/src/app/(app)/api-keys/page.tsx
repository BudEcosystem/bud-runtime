"use client";
import React, { useState, useEffect, useCallback } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Table, Button, Flex } from "antd";
import { useDrawer } from "@/hooks/useDrawer";
import { AppRequest } from "@/services/api/requests";
import { errorToast, successToast } from "@/components/toast";
import BudDrawer from "@/components/ui/bud/drawer/BudDrawer";
import {
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_14_400_B3B3B3,
  Text_14_500_EEEEEE,
  Text_24_500_EEEEEE,
} from "@/components/ui/text";
import { Icon } from "@iconify/react/dist/iconify.js";
import { formatDate } from "@/utils/formatDate";
import styles from "./api-keys.module.scss";

interface ApiKey {
  id: string;
  name: string;
  project: {
    id: string;
    name: string;
  };
  expiry: string;
  created_at: string;
  last_used_at: string;
  is_active: boolean;
  status: "active" | "revoked" | "expired";
}

function SortIcon({ sortOrder }: { sortOrder: any }) {
  return sortOrder ? sortOrder === 'descend' ?
    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 12 13" fill="none">
      <path fillRule="evenodd" clipRule="evenodd" d="M6.00078 2.10938C6.27692 2.10938 6.50078 2.33324 6.50078 2.60938L6.50078 9.40223L8.84723 7.05578C9.04249 6.86052 9.35907 6.86052 9.55433 7.05578C9.7496 7.25104 9.7496 7.56763 9.55433 7.76289L6.35433 10.9629C6.15907 11.1582 5.84249 11.1582 5.64723 10.9629L2.44723 7.76289C2.25197 7.56763 2.25197 7.25104 2.44723 7.05578C2.64249 6.86052 2.95907 6.86052 3.15433 7.05578L5.50078 9.40223L5.50078 2.60938C5.50078 2.33324 5.72464 2.10938 6.00078 2.10938Z" fill="#B3B3B3" />
    </svg>
    : <svg xmlns="http://www.w3.org/2000/svg" width="12" height="13" viewBox="0 0 12 13" fill="none">
      <path fillRule="evenodd" clipRule="evenodd" d="M6.00078 10.8906C6.27692 10.8906 6.50078 10.6668 6.50078 10.3906L6.50078 3.59773L8.84723 5.94418C9.04249 6.13944 9.35907 6.13944 9.55433 5.94418C9.7496 5.74892 9.7496 5.43233 9.55433 5.23707L6.35433 2.03707C6.15907 1.84181 5.84249 1.84181 5.64723 2.03707L2.44723 5.23707C2.25197 5.43233 2.25197 5.74892 2.44723 5.94418C2.64249 6.13944 2.95907 6.13944 3.15433 5.94418L5.50078 3.59773L5.50078 10.3906C5.50078 10.6668 5.72464 10.8906 6.00078 10.8906Z" fill="#B3B3B3" />
    </svg>
    : null;
}

export default function ApiKeysPage() {
  const { openDrawer, isDrawerOpen } = useDrawer();
  const [loading, setLoading] = useState(false);
  const [prevDrawerOpen, setPrevDrawerOpen] = useState(false);
  const [order, setOrder] = useState<'-' | ''>('-');
  const [orderBy, setOrderBy] = useState<string>('last_used_at');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalKeys, setTotalKeys] = useState(0);

  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);


  // Fetch API keys from the backend
  const fetchApiKeys = useCallback(async () => {
    try {
      setLoading(true);
      const params: any = {
        credential_type: "client_app",
        page: currentPage,
        limit: pageSize,
        order_by: `${order}${orderBy}`,
      };


      const response = await AppRequest.Get("/credentials/", { params });

      if (response?.data) {
        setTotalKeys(response.data.total || 0);
        const keys = (response.data.credentials || []).map((cred: any) => ({
          id: cred.id,
          name: cred.name,
          project: cred.project || { id: '', name: 'N/A' },
          expiry: cred.expiry,
          created_at: cred.created_at,
          last_used_at: cred.last_used_at,
          is_active: cred.is_active,
          status: !cred.is_active ? "revoked" :
                  (cred.expiry && new Date(cred.expiry) < new Date() ? "expired" : "active"),
          key: cred.key,
        }));
        setApiKeys(keys);
      }
    } catch (error) {
      console.error("Failed to fetch API keys:", error);
      errorToast("Failed to fetch API keys");
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, order, orderBy]);

  // Fetch data with debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchApiKeys();
    }, 500);
    return () => clearTimeout(timer);
  }, [fetchApiKeys]);

  // Refresh when drawer closes
  useEffect(() => {
    if (prevDrawerOpen && !isDrawerOpen) {
      fetchApiKeys();
    }
    setPrevDrawerOpen(isDrawerOpen);
  }, [isDrawerOpen, prevDrawerOpen, fetchApiKeys]);

  const handlePageChange = (page: number, size: number) => {
    setCurrentPage(page);
    setPageSize(size);
  };

  const handleRevokeKey = async (id: string) => {
    try {
      await AppRequest.Delete(`/credentials/${id}`);
      successToast("API key revoked successfully");
      fetchApiKeys();
    } catch (error) {
      errorToast("Failed to revoke API key");
    }
  };


  const columns = [
    {
      title: 'Credential name',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (text: string) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
      sorter: (a: ApiKey, b: ApiKey) => a.name.localeCompare(b.name),
      sortIcon: SortIcon,
    },
    {
      title: 'Project Name',
      dataIndex: 'project',
      key: 'project',
      width: 200,
      render: (project: any) => <Text_12_400_EEEEEE>{project?.name || 'N/A'}</Text_12_400_EEEEEE>,
      sorter: (a: ApiKey, b: ApiKey) => (a.project?.name || '').localeCompare(b.project?.name || ''),
      sortIcon: SortIcon,
    },
    {
      title: 'Date of Expiry',
      dataIndex: 'expiry',
      key: 'expiry',
      width: 150,
      render: (text: string) => <Text_12_400_EEEEEE>{text ? formatDate(text) : 'Never'}</Text_12_400_EEEEEE>,
      sorter: (a: ApiKey, b: ApiKey) => {
        if (!a.expiry) return 1;
        if (!b.expiry) return -1;
        return new Date(a.expiry).getTime() - new Date(b.expiry).getTime();
      },
      sortIcon: SortIcon,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (text: string) => <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>,
      sorter: (a: ApiKey, b: ApiKey) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      sortIcon: SortIcon,
    },
    {
      title: 'Last Used',
      dataIndex: 'last_used_at',
      key: 'last_used_at',
      width: 150,
      render: (text: string) => <Text_12_400_EEEEEE>{text ? formatDate(text) : '-'}</Text_12_400_EEEEEE>,
      sorter: (a: ApiKey, b: ApiKey) => {
        if (!a.last_used_at) return 1;
        if (!b.last_used_at) return -1;
        return new Date(a.last_used_at).getTime() - new Date(b.last_used_at).getTime();
      },
      sortIcon: SortIcon,
      defaultSortOrder: 'descend' as const
    },
    {
      title: '',
      key: 'actions',
      width: 80,
      render: (_: any, record: ApiKey) =>
        record.is_active ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleRevokeKey(record.id);
            }}
            className="text-[#EC7575] hover:text-[#FF6B6B] text-[12px] font-normal"
          >
            Revoke
          </button>
        ) : null,
    },
  ];

  return (
    <DashboardLayout>
      <div className="boardPageView">
        <div className="boardMainContainer pt-[2.25rem]">
          {/* Header */}
          <Flex justify="space-between" align="center" className="mb-[2rem]">
            <div>
              <Text_24_500_EEEEEE>API Keys</Text_24_500_EEEEEE>
              <Text_14_400_B3B3B3 className="mt-[0.5rem]">
                Manage your API keys for programmatic access
              </Text_14_400_B3B3B3>
            </div>
            <Button
              type="primary"
              icon={<Icon icon="ph:key" />}
              className="bg-[#965CDE] border-[#965CDE] h-[2.5rem] px-[1.5rem]"
              onClick={() => openDrawer("add-new-key")}
            >
              Create New Key
            </Button>
          </Flex>

          {/* Security Notice */}
          <div className="bg-[#5C9CDE1A] border border-[#5C9CDE33] rounded-[8px] p-[1rem]  flex gap-[1rem]">
            <Icon
              icon="ph:info"
              className="text-[#5C9CDE] text-[1.25rem] flex-shrink-0"
            />
            <div>
              <Text_14_500_EEEEEE className="mb-[0.25rem]">
                Keep your API keys secure
              </Text_14_500_EEEEEE>
              <Text_12_400_B3B3B3>
                Do not share your secret API keys in publicly accessible areas
                such as GitHub, client-side code, etc.
              </Text_12_400_B3B3B3>
            </div>
          </div>

          {/* API Keys Table */}
          <div className='pb-[60px] pt-[.4rem] CommonCustomPagination'>
            <Table<ApiKey>
              onChange={(_pagination, _filters, sorter: any) => {
                if (sorter && sorter.field) {
                  setOrder(sorter.order === 'ascend' ? '' : '-');
                  setOrderBy(sorter.field);
                }
              }}
              columns={columns}
              pagination={{
                className: 'small-pagination',
                current: currentPage,
                pageSize: pageSize,
                total: totalKeys,
                onChange: handlePageChange,
                showSizeChanger: true,
                pageSizeOptions: ['5', '10', '20', '50'],
              }}
              dataSource={apiKeys}
              bordered={false}
              loading={loading}
              rowKey="id"
              showSorterTooltip={false}
              className={styles.apiKeysTable}
              style={{
                background: "transparent"
              }}
              onRow={(record) => ({
                onClick: () => {
                  // Store the selected API key in localStorage for the drawer to access
                  localStorage.setItem('selected_api_key', JSON.stringify(record));
                  openDrawer("view-api-key");
                },
                style: { cursor: 'pointer' }
              })}
            />
          </div>
        </div>
      </div>
      <BudDrawer />
    </DashboardLayout>
  );
}
