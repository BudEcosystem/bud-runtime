"use client";
import React, { useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Flex, Table, Button, Modal, Input } from "antd";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_13_400_EEEEEE,
  Text_14_400_B3B3B3,
  Text_14_500_EEEEEE,
  Text_15_600_EEEEEE,
  Text_19_600_EEEEEE,
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
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [newKeyLabel, setNewKeyLabel] = useState("");
  const [newKey, setNewKey] = useState("");
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);

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

  const handleCreateKey = () => {
    if (!newKeyLabel.trim()) return;

    const mockKey = `sk-proj-${Math.random().toString(36).substring(2, 15)}${Math.random().toString(36).substring(2, 15)}`;

    const newApiKey: ApiKey = {
      id: Date.now().toString(),
      label: newKeyLabel,
      key: mockKey,
      createdAt: new Date().toISOString().split("T")[0],
      lastUsedAt: "-",
      usage: 0,
      status: "active",
    };

    setApiKeys([newApiKey, ...apiKeys]);
    setNewKey(mockKey);
    setNewKeyLabel("");
    setShowCreateModal(false);
    setShowKeyModal(true);
  };

  const handleRevokeKey = (id: string) => {
    setApiKeys(
      apiKeys.map((key) =>
        key.id === id ? { ...key, status: "revoked" as const } : key,
      ),
    );
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
          <code className="bg-[#1F1F1F] px-[0.75rem] py-[0.25rem] rounded text-[#B3B3B3] text-[0.813rem]">
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
              onClick={() => setShowCreateModal(true)}
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
              pagination={false}
              className={styles.apiKeysTable}
              style={{ background: "transparent" }}
            />
          </div>

          {/* Create Key Modal */}
          <Modal
            title={<Text_19_600_EEEEEE>Create New API Key</Text_19_600_EEEEEE>}
            open={showCreateModal}
            onCancel={() => {
              setShowCreateModal(false);
              setNewKeyLabel("");
            }}
            footer={[
              <Button
                key="cancel"
                onClick={() => {
                  setShowCreateModal(false);
                  setNewKeyLabel("");
                }}
              >
                Cancel
              </Button>,
              <Button
                key="create"
                type="primary"
                disabled={!newKeyLabel.trim()}
                onClick={handleCreateKey}
                className="bg-[#965CDE] border-[#965CDE]"
              >
                Create Key
              </Button>,
            ]}
            className={styles.modal}
          >
            <Text_14_400_B3B3B3 className="mb-[1rem]">
              Enter a label for your new API key
            </Text_14_400_B3B3B3>
            <Input
              placeholder="e.g., Production API"
              value={newKeyLabel}
              onChange={(e) => setNewKeyLabel(e.target.value)}
              className="bg-[#1F1F1F] border-[#2F2F2F]"
            />
          </Modal>

          {/* Show New Key Modal */}
          <Modal
            title={<Text_19_600_EEEEEE>API Key Created</Text_19_600_EEEEEE>}
            open={showKeyModal}
            onCancel={() => {
              setShowKeyModal(false);
              setNewKey("");
            }}
            footer={[
              <Button
                key="done"
                type="primary"
                onClick={() => {
                  setShowKeyModal(false);
                  setNewKey("");
                }}
                className="bg-[#965CDE] border-[#965CDE]"
              >
                I&apos;ve saved this key
              </Button>,
            ]}
            className={styles.modal}
          >
            <div className="bg-[#DE9C5C1A] border border-[#DE9C5C33] rounded-[8px] p-[1rem] mb-[1.5rem] flex gap-[0.75rem]">
              <Icon
                icon="ph:warning"
                className="text-[#DE9C5C] text-[1.25rem]"
              />
              <Text_13_400_EEEEEE>
                Save this key now. You won&apos;t be able to see it again!
              </Text_13_400_EEEEEE>
            </div>

            <div className="bg-[#1F1F1F] border border-[#2F2F2F] rounded-[8px] p-[1rem] flex items-center justify-between">
              <code className="text-[#EEEEEE] text-[0.875rem] break-all">
                {newKey}
              </code>
              <Button
                type="text"
                icon={<Icon icon="ph:copy" />}
                onClick={() => {
                  navigator.clipboard.writeText(newKey);
                  alert("Key copied to clipboard!");
                }}
                className="text-[#757575] hover:text-[#EEEEEE] ml-[1rem]"
              />
            </div>
          </Modal>
        </div>
      </div>
    </DashboardLayout>
  );
}
