import React, { useEffect, useState, useMemo } from "react";
import {
  Button,
  Card,
  Row,
  Col,
  Statistic,
  Select,
  Tooltip,
  message,
  Modal,
  Tag,
  Space,
  ConfigProvider,
} from "antd";
import { useDrawer } from "@/hooks/useDrawer";
import {
  PlusOutlined,
  SecurityScanOutlined,
  StopOutlined,
  GlobalOutlined,
  UserOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import {
  useBlockingRules,
  BlockingRuleType,
  BlockingRuleStatus,
  BlockingRule,
} from "@/stores/useBlockingRules";
import { BlockingRulesList } from "@/components/blocking/BlockingRulesList";
import { RULE_TYPE_VALUES, RULE_TYPE_LABELS } from "@/constants/blockingRules";
import {
  Text_12_400_808080,
  Text_14_600_EEEEEE,
  Text_12_400_EEEEEE,
  Text_12_500_FFFFFF,
  Text_22_700_EEEEEE,
} from "@/components/ui/text";
import { useEndPoints } from "@/hooks/useEndPoint";
import { useLoader } from "../../../context/appContext";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useConfirmAction } from "src/hooks/useConfirmAction";
import dayjs from "dayjs";

interface RulesTabProps {
  timeRange: [dayjs.Dayjs, dayjs.Dayjs];
  isActive: boolean;
}

const RulesTab: React.FC<RulesTabProps> = ({ timeRange, isActive }) => {
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<any>(null);
  const [localFilters, setLocalFilters] = useState<any>({});

  const {
    rules,
    stats,
    isLoading,
    isCreating,
    isUpdating,
    fetchRules,
    fetchStats,
    createRule,
    updateRule,
    deleteRule,
    setFilters,
    clearFilters,
  } = useBlockingRules();

  const { endPoints, getEndPoints } = useEndPoints();
  const { showLoader, hideLoader } = useLoader();
  const { contextHolder, openConfirm } = useConfirmAction();
  const [deletingRuleId, setDeletingRuleId] = useState<string | null>(null);

  // Fetch deployments on mount
  useEffect(() => {
    const loadInitialData = async () => {
      if (isActive) {
        showLoader();
        try {
          await getEndPoints();
        } finally {
          hideLoader();
        }
      }
    };
    loadInitialData();
  }, [isActive]);

  // Fetch rules and stats when tab is active
  useEffect(() => {
    const loadRulesAndStats = async () => {
      if (isActive) {
        showLoader();
        try {
          // Fetch rules first, then stats (since stats calculation depends on rules)
          await fetchRules();
          await fetchStats(
            timeRange[0].toISOString(),
            timeRange[1].toISOString(),
          );
        } finally {
          hideLoader();
        }
      }
    };
    loadRulesAndStats();
  }, [isActive, timeRange]);

  // Filter rules based on filter criteria
  const filteredRules = useMemo(() => {
    let result = [...rules];

    // Filter by rule type
    if (localFilters.rule_type) {
      result = result.filter(
        (rule) => rule.rule_type === localFilters.rule_type,
      );
    }

    // Filter by status
    if (localFilters.status) {
      result = result.filter((rule) => rule.status === localFilters.status);
    }

    return result;
  }, [rules, localFilters]);

  const handleRuleTypeChange = (value: string) => {
    const newFilters = { ...localFilters };
    if (value) {
      newFilters.rule_type = value;
    } else {
      delete newFilters.rule_type;
    }
    setLocalFilters(newFilters);
  };

  const handleStatusChange = (value: string) => {
    const newFilters = { ...localFilters };
    if (value) {
      newFilters.status = value;
    } else {
      delete newFilters.status;
    }
    setLocalFilters(newFilters);
  };

  const { openDrawer } = useDrawer();

  const handleCreateRule = () => {
    openDrawer("create-blocking-rule", {});
  };

  const handleViewRule = (rule: any) => {
    openDrawer("view-blocking-rule", { rule });
  };

  const handleEditRule = (rule: any) => {
    openDrawer("create-blocking-rule", {
      editMode: true,
      rule: rule,
      ruleId: rule.id,
    });
  };

  const handleDeleteRule = (ruleId: string) => {
    const rule = rules.find((r) => r.id === ruleId);
    const ruleName = rule?.name || "this rule";

    openConfirm({
      message: `You're about to delete the ${ruleName} blocking rule`,
      description:
        "Once you delete the rule, it will not be recovered. Are you sure?",
      cancelAction: () => {
        setDeletingRuleId(null);
      },
      cancelText: "Cancel",
      okAction: async () => {
        try {
          setDeletingRuleId(ruleId);
          showLoader();
          await deleteRule(ruleId);
          await fetchRules();
        } finally {
          hideLoader();
          setDeletingRuleId(null);
        }
      },
      okText: "Delete Rule",
      type: "warning",
      loading: deletingRuleId === ruleId,
      key: "delete-rule",
    });
  };

  const handleFormSubmit = async (values: any) => {
    showLoader();
    try {
      if (editingRule) {
        const success = await updateRule(editingRule.id, values);
        if (success) {
          setIsFormModalOpen(false);
        }
      } else {
        const success = await createRule(values);
        if (success) {
          setIsFormModalOpen(false);
        }
      }
    } finally {
      hideLoader();
    }
  };

  const getRuleTypeIcon = (type: BlockingRuleType) => {
    switch (type) {
      case "ip_blocking":
        return <StopOutlined />;
      case "country_blocking":
        return <GlobalOutlined />;
      case "user_agent_blocking":
        return <UserOutlined />;
      case "rate_based_blocking":
        return <ThunderboltOutlined />;
      default:
        return <SecurityScanOutlined />;
    }
  };

  const getRuleTypeColor = (type: BlockingRuleType) => {
    switch (type) {
      case "ip_blocking":
        return "#ef4444";
      case "country_blocking":
        return "#3b82f6";
      case "user_agent_blocking":
        return "#f59e0b";
      case "rate_based_blocking":
        return "#10b981";
      default:
        return "#6b7280";
    }
  };

  return (
    <div className="rulesTabContainer bg-[#0A0A0A] min-h-screen text-white">
      {contextHolder}
      {/* Statistics Cards */}
      <Row gutter={16} className="mb-6">
        <Col span={6}>
          <div className="bg-[#101010] p-[1.45rem] pb-[1.2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] min-h-[7.8125rem] flex flex-col items-start justify-between">
            <div className="flex items-center gap-2 mb-3">
              <SecurityScanOutlined
                style={{ fontSize: "1.25rem", color: "#3F8EF7" }}
              />
              <Text_12_500_FFFFFF>Total Rules</Text_12_500_FFFFFF>
            </div>
            <div className="flex flex-col w-full">
              <Text_22_700_EEEEEE style={{ color: "#EEEEEE" }}>
                {stats?.total_rules || 0}
              </Text_22_700_EEEEEE>
            </div>
          </div>
        </Col>
        <Col span={6}>
          <div className="bg-[#101010] p-[1.45rem] pb-[1.2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] min-h-[7.8125rem] flex flex-col items-start justify-between">
            <div className="flex items-center gap-2 mb-3">
              <ThunderboltOutlined
                style={{ fontSize: "1.25rem", color: "#22c55e" }}
              />
              <Text_12_500_FFFFFF>Active Rules</Text_12_500_FFFFFF>
            </div>
            <div className="flex flex-col w-full">
              <Text_22_700_EEEEEE style={{ color: "#52c41a" }}>
                {stats?.active_rules || 0}
              </Text_22_700_EEEEEE>
            </div>
          </div>
        </Col>
        <Col span={6}>
          <div className="bg-[#101010] p-[1.45rem] pb-[1.2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] min-h-[7.8125rem] flex flex-col items-start justify-between">
            <div className="flex items-center gap-2 mb-3">
              <StopOutlined style={{ fontSize: "1.25rem", color: "#ef4444" }} />
              <Text_12_500_FFFFFF>Blocks Today</Text_12_500_FFFFFF>
            </div>
            <div className="flex flex-col w-full">
              <Text_22_700_EEEEEE style={{ color: "#ff4d4f" }}>
                {stats?.total_blocks_today || 0}
              </Text_22_700_EEEEEE>
            </div>
          </div>
        </Col>
        <Col span={6}>
          <div className="bg-[#101010] p-[1.45rem] pb-[1.2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] min-h-[7.8125rem] flex flex-col items-start justify-between">
            <div className="flex items-center gap-2 mb-3">
              <ClockCircleOutlined
                style={{ fontSize: "1.25rem", color: "#FFC442" }}
              />
              <Text_12_500_FFFFFF>Blocks This Week</Text_12_500_FFFFFF>
            </div>
            <div className="flex flex-col w-full">
              <Text_22_700_EEEEEE style={{ color: "#EEEEEE" }}>
                {stats?.total_blocks_week || 0}
              </Text_22_700_EEEEEE>
            </div>
          </div>
        </Col>
      </Row>

      {/* Filters and Actions Bar */}
      <div className="mt-6 mb-4 flex justify-between items-center gap-4">
        <span className="text-[#B3B3B3]">
          Showing {filteredRules.length} of {rules.length} rules
        </span>
        <div className="flex items-center gap-3">
          <ConfigProvider
            theme={{
              components: {
                Select: {
                  colorBgContainer: "#1A1A1A",
                  colorBorder: "#1F1F1F",
                  colorText: "#EEEEEE",
                  colorTextPlaceholder: "#666666",
                  colorBgElevated: "#1A1A1A",
                  controlItemBgHover: "#2F2F2F",
                  optionSelectedBg: "#2A1F3D",
                },
              },
            }}
          >
            <Select
              style={{ width: 160 }}
              placeholder="Rule Type"
              allowClear
              value={localFilters.rule_type}
              onChange={handleRuleTypeChange}
              className="bg-[#1A1A1A]"
              dropdownStyle={{ backgroundColor: "#1A1A1A" }}
            >
              {Object.entries(RULE_TYPE_VALUES).map(([key, value]) => (
                <Select.Option key={value} value={value}>
                  {RULE_TYPE_LABELS[value]}
                </Select.Option>
              ))}
            </Select>
            <Select
              style={{ width: 100 }}
              placeholder="Status"
              allowClear
              value={localFilters.status}
              onChange={handleStatusChange}
              className="bg-[#1A1A1A]"
              dropdownStyle={{ backgroundColor: "#1A1A1A" }}
            >
              <Select.Option value="ACTIVE">Active</Select.Option>
              <Select.Option value="INACTIVE">Inactive</Select.Option>
            </Select>
          </ConfigProvider>
          <PrimaryButton onClick={handleCreateRule}>
            <PlusOutlined />
            <span className="ml-2">Create Rule</span>
          </PrimaryButton>
        </div>
      </div>

      {/* Rules List */}
      <BlockingRulesList
        rules={filteredRules}
        loading={isLoading}
        onView={handleViewRule}
        onEdit={handleEditRule}
        onDelete={handleDeleteRule}
      />

      {/* Edit Form Modal */}
      {/* Edit Modal - Currently using drawer for create, can add edit later */}
    </div>
  );
};

export default RulesTab;
