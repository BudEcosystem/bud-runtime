import React, { useEffect, useState, useCallback, useMemo } from "react";
import { Spin, Empty, Switch, Table, ConfigProvider, Drawer, Tooltip, Button, Space } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  Text_14_400_757575,
  Text_12_400_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_400_757575,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import { SecondaryButton } from "@/components/ui/bud/form/Buttons";
import { errorToast } from "@/components/toast";
import { useConfirmAction } from "@/hooks/useConfirmAction";
import {
  useGlobalConnectors,
  type ConfiguredConnector,
} from "@/stores/useGlobalConnectors";
import ProjectTags from "src/flows/components/ProjectTags";

const GLOBAL_OAUTH_STATE_KEY = "global_oauth_connector_state";

// Tag prefixes used for filtering display tags
const TAG_PREFIX_CLIENT = "client:";
const TAG_PREFIX_CONNECTOR_ID = "connector-id:";
const TAG_PREFIX_SOURCE = "source:";

// ---------------------------------------------------------------------------
// Inline Icons
// ---------------------------------------------------------------------------

const ToolsIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  </svg>
);

const EyeIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const TrashIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    <path d="M10 11v6" />
    <path d="M14 11v6" />
    <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
  </svg>
);

const ConnectorFallbackIcon = () => (
  <svg
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="#965CDE"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M12 2L2 7l10 5 10-5-10-5z" />
    <path d="M2 17l10 5 10-5" />
    <path d="M2 12l10 5 10-5" />
  </svg>
);

// ---------------------------------------------------------------------------
// Small helper components
// ---------------------------------------------------------------------------

const ConnectorIcon = ({ icon, name, size = "1.75rem" }: { icon?: string; name: string; size?: string }) => {
  if (icon) {
    return (
      <img
        src={icon}
        alt=""
        className="shrink-0 object-contain bg-[#1F1F1F] p-0.5 rounded"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <div
      className="flex items-center justify-center shrink-0 rounded bg-[#1F1F1F]"
      style={{ width: size, height: size }}
    >
      <ConnectorFallbackIcon />
    </div>
  );
};

/** OAuth status badge using ProjectTags */
const OAuthBadge = ({ connected }: { connected: boolean }) => {
  if (connected) {
    return <ProjectTags name="Active" color="#479D5F" textClass="text-[.75rem]" />;
  }
  return null;
};

// ---------------------------------------------------------------------------
// Detail Drawer — follows standard drawerBackground / form-layout pattern
// ---------------------------------------------------------------------------

interface DetailDrawerProps {
  open: boolean;
  onClose: () => void;
  connector: ConfiguredConnector | null;
  onDelete: (connector: ConfiguredConnector) => void;
}

/** Map of client tag values to display labels */
const CLIENT_LABELS: { key: string; label: string }[] = [
  { key: "dashboard", label: "Studio" },
  { key: "chat", label: "Prompt" },
];

const DetailDrawer: React.FC<DetailDrawerProps> = ({ open, onClose, connector, onDelete }) => {
  const { listToolsForGateway, updateClients } = useGlobalConnectors();
  const [tools, setTools] = useState<any[]>([]);
  const [toolsLoading, setToolsLoading] = useState(false);
  const [clientUpdating, setClientUpdating] = useState<string | null>(null);

  // Responsive drawer width (matches BudDrawer pattern)
  const [drawerWidth, setDrawerWidth] = useState(400);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleResize = () => {
      const sw = window.innerWidth;
      if (sw > 2560) setDrawerWidth(sw * 0.35);
      else if (sw > 1920) setDrawerWidth(sw * 0.4322);
      else if (sw > 1280) setDrawerWidth(sw * 0.433);
      else if (sw > 1024) setDrawerWidth(450);
      else setDrawerWidth(400);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (open && connector) {
      setToolsLoading(true);
      listToolsForGateway(connector.gateway_id)
        .then((t) => setTools(t || []))
        .finally(() => setToolsLoading(false));
    }
    if (!open) setTools([]);
  }, [open, connector, listToolsForGateway]);

  if (!connector) return null;

  // Parse active client tags from connector tags
  const activeClients = new Set(
    connector.tags
      .filter((t) => t.startsWith(TAG_PREFIX_CLIENT))
      .map((t) => t.slice(TAG_PREFIX_CLIENT.length))
  );

  // Extract non-client tags for display (e.g. category, source tags)
  const registryTags = connector.tags.filter(
    (t) => !t.startsWith(TAG_PREFIX_CLIENT) && !t.startsWith(TAG_PREFIX_CONNECTOR_ID) && !t.startsWith(TAG_PREFIX_SOURCE)
  );

  const handleClientToggle = async (clientKey: string, enabled: boolean) => {
    setClientUpdating(clientKey);
    const newClients = enabled
      ? [...Array.from(activeClients), clientKey]
      : Array.from(activeClients).filter((c) => c !== clientKey);
    await updateClients(connector.gateway_id, newClients);
    setClientUpdating(null);
  };

  const infoRows: { label: string; value: React.ReactNode }[] = [
    connector.auth_type ? { label: "Auth Type", value: connector.auth_type } : null,
    connector.category ? { label: "Category", value: connector.category } : null,
    { label: "OAuth", value: connector.oauth_connected ? <OAuthBadge connected /> : <Text_12_400_757575>Not connected</Text_12_400_757575> },
    { label: "Connector ID", value: <span className="font-mono text-[0.6875rem] text-[#B3B3B3]">{connector.connector_id}</span> },
    { label: "Gateway ID", value: <span className="font-mono text-[0.6875rem] text-[#B3B3B3] break-all">{connector.gateway_id}</span> },
  ].filter(Boolean) as { label: string; value: React.ReactNode }[];

  return (
    <Drawer
      title={null}
      placement="right"
      width={drawerWidth}
      open={open}
      onClose={onClose}
      closable={false}
      destroyOnClose
      styles={{ body: { padding: 0 }, header: { display: "none" } }}
      rootClassName="connections-detail-drawer"
    >
      {/* drawerBackground: the standard drawer shell */}
      <div className="drawerBackground flex flex-col h-full">
        {/* ── Header: ant-header-breadcrumb ── */}
        <div className="ant-header-breadcrumb">
          <div className="flex items-center gap-2">
            <button onClick={onClose}>
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" className="hover:text-[#FFFFFF]">
                <path fillRule="evenodd" clipRule="evenodd" d="M13.8103 5.09188C14.0601 4.8421 14.0601 4.43712 13.8103 4.18734C13.5606 3.93755 13.1556 3.93755 12.9058 4.18734L8.99884 8.0943L5.09188 4.18734C4.8421 3.93755 4.43712 3.93755 4.18734 4.18734C3.93755 4.43712 3.93755 4.8421 4.18734 5.09188L8.0943 8.99884L4.18734 12.9058C3.93755 13.1556 3.93755 13.5606 4.18734 13.8103C4.43712 14.0601 4.8421 14.0601 5.09188 13.8103L8.99884 9.90338L12.9058 13.8103C13.1556 14.0601 13.5606 14.0601 13.8103 13.8103C14.0601 13.5606 14.0601 13.1556 13.8103 12.9058L9.90338 8.99884L13.8103 5.09188Z" fill="#B3B3B3" />
              </svg>
            </button>
          </div>
        </div>

        {/* ── Scrollable content ── */}
        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="BudWraperBox scrollBox py-[20px] overflow-y-auto h-full">
            {/* Title card */}
            <div className="form-layout !mb-[1.1rem]">
              <div className="px-[1.4rem] rounded-ss-lg rounded-se-lg" style={{ paddingTop: "1.1rem", paddingBottom: ".9rem" }}>
                <div className="flex items-center gap-3">
                  <ConnectorIcon icon={connector.icon} name={connector.name} size="2.40125rem" />
                  <div className="flex flex-col gap-1">
                    <Text_14_400_EEEEEE className="p-0 m-0 text-[1.125rem]">
                      {connector.name}
                    </Text_14_400_EEEEEE>
                    {connector.description && (
                      <Text_12_400_757575 className="p-0 m-0 !leading-[1.4]">
                        {connector.description}
                      </Text_12_400_757575>
                    )}
                  </div>
                </div>
                {/* Registry tags */}
                {registryTags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {registryTags.map((tag) => (
                      <ProjectTags key={tag} name={tag} color="#757575" textClass="text-[.625rem]" />
                    ))}
                  </div>
                )}
                {connector.documentation_url && (
                  <a
                    href={connector.documentation_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 mt-3 text-[0.75rem] text-[#965CDE] hover:text-[#B07FEE] transition-colors"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></svg>
                    Documentation
                  </a>
                )}
              </div>
            </div>

            {/* Details card */}
            <div className="form-layout !mb-[1.1rem]">
              <div className="px-[1.4rem] rounded-ss-lg rounded-se-lg border-b-[.5px] border-b-[#1F1F1F]" style={{ paddingTop: "1.1rem", paddingBottom: ".9rem" }}>
                <Text_14_400_EEEEEE className="p-0 m-0">Details</Text_14_400_EEEEEE>
              </div>
              <div className="px-[1.4rem] py-[1rem]">
                <div className="flex flex-col gap-[1rem]">
                  {infoRows.map((row) => (
                    <div key={row.label} className="flex justify-between items-start gap-[.8rem]">
                      <Text_12_400_757575 className="text-nowrap min-w-[7rem]">{row.label}</Text_12_400_757575>
                      <div className="text-right">
                        {typeof row.value === "string" ? (
                          <Text_12_400_EEEEEE>{row.value}</Text_12_400_EEEEEE>
                        ) : (
                          row.value
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Clients card */}
            <div className="form-layout !mb-[1.1rem]">
              <div className="px-[1.4rem] rounded-ss-lg rounded-se-lg border-b-[.5px] border-b-[#1F1F1F]" style={{ paddingTop: "1.1rem", paddingBottom: ".9rem" }}>
                <Text_14_400_EEEEEE className="p-0 m-0">Clients</Text_14_400_EEEEEE>
              </div>
              <div className="px-[1.4rem] py-[1rem]">
                <div className="flex flex-col gap-[0.75rem]">
                  {CLIENT_LABELS.map(({ key, label }) => (
                    <div key={key} className="flex justify-between items-center">
                      <Text_12_400_EEEEEE>{label}</Text_12_400_EEEEEE>
                      <Switch
                        size="small"
                        checked={activeClients.has(key)}
                        loading={clientUpdating === key}
                        onChange={(checked) => handleClientToggle(key, checked)}
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Tools card */}
            <div className="form-layout !mb-[1.1rem]">
              <div className="px-[1.4rem] rounded-ss-lg rounded-se-lg border-b-[.5px] border-b-[#1F1F1F]" style={{ paddingTop: "1.1rem", paddingBottom: ".9rem" }}>
                <div className="flex items-center gap-2">
                  <span className="text-[#757575]"><ToolsIcon /></span>
                  <Text_14_400_EEEEEE>Tools ({toolsLoading ? "..." : tools.length})</Text_14_400_EEEEEE>
                </div>
              </div>
              <div className="px-[1.4rem] py-[1rem]">
                {toolsLoading ? (
                  <div className="flex justify-center items-center py-6"><Spin size="small" /></div>
                ) : tools.length === 0 ? (
                  <Text_12_400_757575>No tools found for this connector.</Text_12_400_757575>
                ) : (
                  <div className="space-y-2">
                    {tools.map((tool: any, idx: number) => (
                      <div key={tool.id || idx} className="p-3 rounded-lg border border-[#1F1F1F] bg-[rgba(255,255,255,0.02)] hover:border-[#2A2A2A] transition-colors">
                        <Text_12_400_EEEEEE className="!leading-[1.3]">{tool.name || tool.displayName || `Tool ${idx + 1}`}</Text_12_400_EEEEEE>
                        {tool.description && <Text_12_400_757575 className="mt-1 !leading-[1.4]">{tool.description}</Text_12_400_757575>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── Footer: drawerFooter ── */}
          <div className="drawerFooter z-[5000] min-[4.1875rem] flex flex-col justify-start">
            <div
              style={{ justifyContent: "space-between" }}
              className="h-[4rem] pt-[.1rem] flex items-center px-[2.7rem]"
            >
              <SecondaryButton onClick={onClose}>
                Close
              </SecondaryButton>
              <Button
                onClick={() => onDelete(connector)}
                className="flex justify-center items-center !border-[.5px] font-normal h-[1.75rem] min-w-[4rem] rounded-[0.3rem]"
                style={{
                  borderColor: "#E82E2E",
                  background: "transparent",
                  color: "#E82E2E",
                  fontSize: "0.75rem",
                  paddingLeft: "0.7rem",
                  paddingRight: "0.7rem",
                }}
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      </div>
    </Drawer>
  );
};

// ---------------------------------------------------------------------------
// Table dark theme config (matches BlockingRulesList)
// ---------------------------------------------------------------------------

const TABLE_THEME = {
  components: {
    Table: {
      headerBg: "transparent",
      headerColor: "#757575",
      rowHoverBg: "#1A1A1A",
      colorBgContainer: "transparent",
      colorText: "#EEEEEE",
      colorBorder: "#1F1F1F",
      colorBorderSecondary: "#1F1F1F",
      fixedHeaderSortActiveBg: "transparent",
      bodySortBg: "transparent",
      headerSortActiveBg: "transparent",
      headerSortHoverBg: "transparent",
      colorFillAlter: "transparent",
      colorFillContent: "transparent",
      headerFilterHoverBg: "transparent",
      headerSplitColor: "#1F1F1F",
      cellPaddingBlock: 12,
      cellPaddingInline: 16,
      fontSize: 12,
    },
    Pagination: {
      colorPrimary: "#965CDE",
      colorPrimaryHover: "#a873e5",
      colorBgContainer: "#101010",
      colorText: "#EEEEEE",
      colorTextDisabled: "#666666",
      colorBorder: "#1F1F1F",
      itemBg: "#101010",
      itemActiveBg: "#1E0C34",
      colorBgTextHover: "#1F1F1F",
      colorBgTextActive: "#1E0C34",
      borderRadius: 4,
    },
    Button: {
      colorBgTextHover: "transparent",
      colorBgTextActive: "transparent",
      colorBgContainer: "transparent",
      colorBorder: "transparent",
      colorText: "#EEEEEE",
      colorPrimary: "#965CDE",
      paddingInline: 4,
      defaultBg: "transparent",
      defaultHoverBg: "transparent",
      defaultActiveBg: "transparent",
    },
    Tooltip: {
      colorBgSpotlight: "#1A1A1A",
      colorTextLightSolid: "#EEEEEE",
    },
  },
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const Connections = () => {
  const {
    configuredConnectors,
    configuredTotal,
    configuredLoading,
    fetchConfigured,
    toggleConnector,
    deleteGateway,
    initiateOAuth,
  } = useGlobalConnectors();

  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // Detail drawer — derive connector from store so it stays in sync after updates
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailGatewayId, setDetailGatewayId] = useState<string | null>(null);
  const detailConnector = useMemo(
    () => configuredConnectors.find((c) => c.gateway_id === detailGatewayId) ?? null,
    [configuredConnectors, detailGatewayId]
  );

  // Delete confirmation (bottom-right notification pattern)
  const { contextHolder, openConfirm } = useConfirmAction();
  const [confirmLoading, setConfirmLoading] = useState(false);

  // Fetch configured connectors on mount
  useEffect(() => {
    fetchConfigured({ include_disabled: true });
  }, [fetchConfigured]);

  // Handlers
  const handleConnect = useCallback(
    async (connector: ConfiguredConnector) => {
      setConnectingId(connector.gateway_id);
      try {
        const result = await initiateOAuth(connector.gateway_id);
        if (result?.authorization_url) {
          localStorage.setItem(
            GLOBAL_OAUTH_STATE_KEY,
            JSON.stringify({
              gatewayId: connector.gateway_id,
              gatewayName: connector.name,
              oauthType: "global",
              timestamp: Date.now(),
            })
          );
          window.location.href = result.authorization_url;
        } else {
          errorToast("Failed to get authorization URL from the server");
        }
      } catch {
        errorToast("An error occurred while initiating the connection");
      } finally {
        setConnectingId(null);
      }
    },
    [initiateOAuth]
  );

  const handleToggle = useCallback(
    async (connector: ConfiguredConnector) => {
      setTogglingId(connector.gateway_id);
      await toggleConnector(connector.gateway_id, !connector.enabled);
      setTogglingId(null);
    },
    [toggleConnector]
  );

  const handleDetail = useCallback((connector: ConfiguredConnector) => {
    setDetailGatewayId(connector.gateway_id);
    setDetailOpen(true);
  }, []);

  const handleRequestDelete = useCallback((connector: ConfiguredConnector) => {
    setDetailOpen(false);
    setDetailGatewayId(null);
    openConfirm({
      message: `You're about to delete the ${connector.name} connector`,
      description:
        "Once you delete the connector, it will not be recovered. All associated tools and user connections will be removed. Are you sure?",
      cancelText: "Cancel",
      cancelAction: () => {},
      okText: "Delete",
      loading: confirmLoading,
      key: "delete-connector",
      type: "warning",
      okAction: async () => {
        setConfirmLoading(true);
        const success = await deleteGateway(connector.gateway_id);
        if (success) {
          fetchConfigured({ include_disabled: true });
        } else {
          errorToast("Failed to delete connector");
        }
        setConfirmLoading(false);
      },
    });
  }, [openConfirm, confirmLoading, deleteGateway, fetchConfigured]);

  // Table columns
  const columns = useMemo<ColumnsType<ConfiguredConnector>>(
    () => [
      {
        title: "Connector",
        dataIndex: "name",
        key: "name",
        width: 260,
        render: (_: any, record: ConfiguredConnector) => (
          <div className="flex items-center gap-3">
            <ConnectorIcon icon={record.icon} name={record.name} />
            <Text_12_400_EEEEEE className="truncate">{record.name}</Text_12_400_EEEEEE>
          </div>
        ),
      },
      {
        title: "Auth",
        dataIndex: "auth_type",
        key: "auth_type",
        width: 120,
        render: (authType: string) =>
          authType ? <Text_12_400_B3B3B3>{authType}</Text_12_400_B3B3B3> : <Text_12_400_757575>-</Text_12_400_757575>,
      },
      {
        title: "Tools",
        dataIndex: "tool_count",
        key: "tool_count",
        width: 80,
        align: "center" as const,
        render: (count: number) => (
          <Text_12_400_B3B3B3>{count ?? 0}</Text_12_400_B3B3B3>
        ),
      },
      {
        title: "OAuth",
        key: "oauth",
        width: 110,
        render: (_: any, record: ConfiguredConnector) => {
          if (!record.enabled) return <Text_12_400_757575>-</Text_12_400_757575>;
          if (record.oauth_connected) {
            return <OAuthBadge connected />;
          }
          return (
            <button
              onClick={(e) => { e.stopPropagation(); handleConnect(record); }}
              disabled={connectingId === record.gateway_id}
              className="text-[0.75rem] text-[#965CDE] hover:text-[#B07FEE] transition-colors disabled:opacity-50"
            >
              {connectingId === record.gateway_id ? "Connecting..." : "Connect"}
            </button>
          );
        },
      },
      {
        title: "Enabled",
        key: "enabled",
        width: 80,
        align: "center" as const,
        render: (_: any, record: ConfiguredConnector) => (
          <Switch
            size="small"
            checked={record.enabled}
            loading={togglingId === record.gateway_id}
            onChange={(_, e) => { e.stopPropagation(); handleToggle(record); }}
          />
        ),
      },
      {
        title: "",
        key: "actions",
        width: 90,
        align: "center" as const,
        render: (_: any, record: ConfiguredConnector) => (
          <Space size={4}>
            <Tooltip title="View Details" placement="top">
              <Button
                type="text"
                size="small"
                className="!p-1 text-[#757575] hover:!text-[#965CDE]"
                onClick={(e) => { e.stopPropagation(); handleDetail(record); }}
              >
                <EyeIcon />
              </Button>
            </Tooltip>
            <Tooltip title="Delete" placement="top">
              <Button
                type="text"
                size="small"
                className="!p-1 text-[#757575] hover:!text-[#E82E2E]"
                onClick={(e) => {
                  e.stopPropagation();
                  handleRequestDelete(record);
                }}
              >
                <TrashIcon />
              </Button>
            </Tooltip>
          </Space>
        ),
      },
    ],
    [connectingId, togglingId, handleConnect, handleToggle, handleDetail, handleRequestDelete]
  );

  // Empty state
  if (!configuredLoading && (!configuredConnectors || configuredConnectors.length === 0)) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ minHeight: "20rem" }}>
        <Empty description={false} image={Empty.PRESENTED_IMAGE_SIMPLE} />
        <Text_14_400_757575 className="mt-[1rem]">No connections configured</Text_14_400_757575>
        <Text_12_400_B3B3B3 className="mt-[0.4rem]">Configure connectors from the Connectors tab to see them here.</Text_12_400_B3B3B3>
      </div>
    );
  }

  return (
    <div className="pb-[60px] pt-[0.5rem] relative">
      {/* Table */}
      <ConfigProvider theme={TABLE_THEME}>
        <Table
          columns={columns}
          dataSource={configuredConnectors}
          rowKey="gateway_id"
          loading={configuredLoading}
          pagination={
            configuredTotal > 20
              ? { defaultPageSize: 20, showSizeChanger: true, showTotal: (total) => `${total} connectors` }
              : false
          }
          onRow={(record) => ({
            onClick: () => handleDetail(record),
            className: "cursor-pointer",
          })}
          scroll={{ y: "calc(100vh - 320px)" }}
          size="middle"
        />
      </ConfigProvider>

      {/* Detail Drawer */}
      <DetailDrawer
        open={detailOpen}
        onClose={() => { setDetailOpen(false); setDetailGatewayId(null); }}
        connector={detailConnector}
        onDelete={handleRequestDelete}
      />

      {/* Confirm action notification (bottom-right) */}
      {contextHolder}

      {/* Scoped styles */}
      <style jsx global>{`
        .connections-detail-drawer .ant-drawer-content { background: transparent !important; }
        .connections-detail-drawer .ant-drawer-body { background: transparent !important; }
      `}</style>
    </div>
  );
};

export default Connections;
