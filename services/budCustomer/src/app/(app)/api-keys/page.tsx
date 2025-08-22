"use client";
import React, { useState, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Flex, Table, Button } from "antd";
import { useDrawer } from "@/hooks/useDrawer";
import { AppRequest } from "@/services/api/requests";
import { errorToast, successToast } from "@/components/toast";
import BudDrawer from "@/components/ui/bud/drawer/BudDrawer";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_13_400_EEEEEE,
  Text_14_400_B3B3B3,
  Text_14_500_EEEEEE,
  Text_24_500_EEEEEE,
} from "@/components/ui/text";
import { Icon } from "@iconify/react/dist/iconify.js";
import styles from "./api-keys.module.scss";

interface ApiKey {
  id: string;
  label: string;
  key: string;
  createdAt: string;
  lastUsedAt: string;
  usage: number;
  status: "active" | "revoked";
}

export default function ApiKeysPage() {
  const { openDrawer, isDrawerOpen } = useDrawer();
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [prevDrawerOpen, setPrevDrawerOpen] = useState(false);

  // Mock data
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([
    {
      id: "1",
      label: "Production API",
      key: "sk-...AbCd",
      createdAt: "2024-01-15",
      lastUsedAt: "2024-01-20",
      usage: 15420,
      status: "active",
    },
    {
      id: "2",
      label: "Development API",
      key: "sk-...XyZw",
      createdAt: "2024-01-10",
      lastUsedAt: "2024-01-19",
      usage: 8350,
      status: "active",
    },
    {
      id: "3",
      label: "Testing Environment",
      key: "sk-...9876",
      createdAt: "2023-12-20",
      lastUsedAt: "2024-01-05",
      usage: 2100,
      status: "revoked",
    },
  ]);

  // Fetch API keys from the backend
  const fetchApiKeys = async () => {
    try {
      setLoading(true);
      const response = await AppRequest.Get("/credentials/", {
        params: {
          credential_type: "client_app",
          page: 1,
          limit: 100,
        },
      });
      if (response?.data?.credentials) {
        const keys = response.data.credentials.map((cred: any) => ({
          id: cred.id,
          label: cred.name,
          key: cred.key || `sk-...${cred.id.slice(-4)}`,
          createdAt: new Date(cred.created_at).toLocaleDateString(),
          lastUsedAt: cred.last_used_at
            ? new Date(cred.last_used_at).toLocaleDateString()
            : "-",
          usage: 0,
          status: cred.is_active ? "active" : "revoked",
        }));
        setApiKeys(keys);
      }
    } catch (error) {
      console.error("Failed to fetch API keys:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApiKeys();
  }, []);

  // Refresh when drawer closes
  useEffect(() => {
    if (prevDrawerOpen && !isDrawerOpen) {
      fetchApiKeys();
    }
    setPrevDrawerOpen(isDrawerOpen);
  }, [isDrawerOpen, prevDrawerOpen]);

  const handleRevokeKey = async (id: string) => {
    try {
      await AppRequest.Delete(`/credentials/${id}`);
      successToast("API key revoked successfully");
      fetchApiKeys();
    } catch (error) {
      errorToast("Failed to revoke API key");
    }
  };

  const handleCopyKey = (key: string, id: string) => {
    navigator.clipboard.writeText(key);
    setCopiedKeyId(id);
    setTimeout(() => setCopiedKeyId(null), 2000);
  };

  const maskKey = (key: string) => {
    return `${key.substring(0, 7)}...${key.substring(key.length - 4)}`;
  };

  const columns = [
    {
      title: <Text_12_400_757575>NAME</Text_12_400_757575>,
      dataIndex: "label",
      key: "label",
      render: (text: string) => <Text_14_500_EEEEEE>{text}</Text_14_500_EEEEEE>,
    },
    {
      title: <Text_12_400_757575>KEY</Text_12_400_757575>,
      dataIndex: "key",
      key: "key",
      render: (text: string, record: ApiKey) => (
        <Flex align="center" gap={12}>
          <code className="bg-[var(--border-color)] px-[0.75rem] py-[0.25rem] rounded text-[var(--text-primary)] text-[0.813rem]">
            {maskKey(text)}
          </code>
          <Button
            type="text"
            icon={
              <Icon icon={copiedKeyId === record.id ? "ph:check" : "ph:copy"} />
            }
            onClick={() => handleCopyKey(text, record.id)}
            className="text-[#757575] hover:text-[#EEEEEE]"
            style={{ background: "transparent", border: "none" }}
          />
        </Flex>
      ),
    },
    {
      title: <Text_12_400_757575>CREATED</Text_12_400_757575>,
      dataIndex: "createdAt",
      key: "createdAt",
      render: (text: string) => <Text_13_400_EEEEEE>{text}</Text_13_400_EEEEEE>,
    },
    {
      title: <Text_12_400_757575>LAST USED</Text_12_400_757575>,
      dataIndex: "lastUsedAt",
      key: "lastUsedAt",
      render: (text: string) => <Text_13_400_EEEEEE>{text}</Text_13_400_EEEEEE>,
    },
    {
      title: <Text_12_400_757575>USAGE</Text_12_400_757575>,
      dataIndex: "usage",
      key: "usage",
      render: (text: number) => (
        <Text_13_400_EEEEEE>
          {text.toLocaleString()} requests
        </Text_13_400_EEEEEE>
      ),
    },
    {
      title: <Text_12_400_757575>STATUS</Text_12_400_757575>,
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Text_13_400_EEEEEE
          style={{
            color: status === "active" ? "#479D5F" : "#EC7575",
          }}
        >
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </Text_13_400_EEEEEE>
      ),
    },
    {
      title: "",
      key: "actions",
      width: 100,
      render: (_: any, record: ApiKey) =>
        record.status === "active" ? (
          <Button
            type="text"
            onClick={() => handleRevokeKey(record.id)}
            className="text-[#EC7575] hover:text-[#FF6B6B] hover:bg-[#EC757510]"
            style={{ background: "transparent", border: "none" }}
          >
            Revoke
          </Button>
        ) : (
          <Text_12_400_757575>Revoked</Text_12_400_757575>
        ),
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
          <div className="bg-[#5C9CDE1A] border border-[#5C9CDE33] rounded-[8px] p-[1rem] mb-[2rem] flex gap-[1rem]">
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
          <div>
            <Table
              dataSource={apiKeys}
              columns={columns}
              rowKey="id"
              loading={loading}
              pagination={false}
              className={styles.apiKeysTable}
              style={{ background: "transparent" }}
            />
          </div>
        </div>
      </div>
      <BudDrawer />
    </DashboardLayout>
  );
}
