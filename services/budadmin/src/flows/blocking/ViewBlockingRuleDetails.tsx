import React, { useState } from "react";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_12_300_EEEEEE,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import { useDrawer } from "@/hooks/useDrawer";
import { Image, Modal, Tag, Space, Tooltip } from "antd";
import { formatDistanceToNow } from "date-fns";
import {
  useBlockingRules,
  BlockingRule,
  BlockingRuleType,
  BlockingRuleStatus,
} from "@/stores/useBlockingRules";
import CustomDropDown from "src/flows/components/CustomDropDown";
import { getRuleTypeColor, RULE_TYPE_LABELS } from "@/constants/blockingRules";
import { useLoader } from "src/context/appContext";
import { useConfirmAction } from "src/hooks/useConfirmAction";
import ProjectTags from "src/flows/components/ProjectTags";
import { endpointStatusMapping } from "@/lib/colorMapping";

interface ViewBlockingRuleDetailsProps {
  rule?: BlockingRule;
}

export default function ViewBlockingRuleDetails({
  rule,
}: ViewBlockingRuleDetailsProps) {
  const { closeDrawer, drawerProps, openDrawerWithStep } = useDrawer();
  const { deleteRule, updateRule, fetchRules } = useBlockingRules();
  const { showLoader, hideLoader } = useLoader();
  const { contextHolder, openConfirm } = useConfirmAction();
  const [loading, setLoading] = useState(false);

  // Get rule from props or drawerProps
  const ruleData = rule || drawerProps?.rule;

  // Status color mapping to match the listing
  const getStatusColorMapping = (status: BlockingRuleStatus) => {
    // Normalize to uppercase for consistent mapping
    const normalizedStatus = status?.toUpperCase();
    const statusColorMap = {
      ACTIVE: endpointStatusMapping["Active"], // Green #479D5F
      INACTIVE: "#B3B3B3", // Gray - disabled but not error
      EXPIRED: endpointStatusMapping["Failed"], // Red #EC7575
    };
    return statusColorMap[normalizedStatus] || endpointStatusMapping["Active"]; // Default to green
  };

  if (!ruleData) {
    return (
      <BudForm data={{}}>
        <BudWraperBox classNames="mt-[1.9375rem]">
          <BudDrawerLayout>
            <div className="px-[1.4rem] py-[2rem]">
              <Text_14_400_EEEEEE>Rule not found</Text_14_400_EEEEEE>
            </div>
          </BudDrawerLayout>
        </BudWraperBox>
      </BudForm>
    );
  }

  const formatRuleConfig = (config: any, type: BlockingRuleType) => {
    switch (type) {
      case "ip_blocking":
        return config.ip_addresses ? (
          <div className="space-y-1">
            {config.ip_addresses.map((ip: string, index: number) => (
              <div
                key={index}
                className="text-[#EEEEEE] font-mono text-sm bg-[#1F1F1F] px-2 py-1 rounded"
              >
                {ip}
              </div>
            ))}
          </div>
        ) : (
          "No IP addresses configured"
        );

      case "country_blocking":
        return config.countries ? (
          <div className="flex flex-wrap gap-1">
            {config.countries.map((country: string, index: number) => (
              <Tag key={index} color="blue">
                {country}
              </Tag>
            ))}
          </div>
        ) : (
          "No countries configured"
        );

      case "user_agent_blocking":
        return config.patterns ? (
          <div className="space-y-1">
            {config.patterns.map((pattern: string, index: number) => (
              <div
                key={index}
                className="text-[#EEEEEE] font-mono text-sm bg-[#1F1F1F] px-2 py-1 rounded"
              >
                {pattern}
              </div>
            ))}
          </div>
        ) : (
          "No patterns configured"
        );

      case "rate_based_blocking":
        return (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Text_12_400_B3B3B3>Threshold:</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE>
                {config.threshold || "Not set"}
              </Text_12_400_EEEEEE>
            </div>
            <div className="flex items-center gap-2">
              <Text_12_400_B3B3B3>Window:</Text_12_400_B3B3B3>
              <Text_12_400_EEEEEE>
                {config.window_seconds || "Not set"} seconds
              </Text_12_400_EEEEEE>
            </div>
          </div>
        );

      default:
        return JSON.stringify(config, null, 2);
    }
  };

  const handleDelete = async () => {
    try {
      setLoading(true);
      showLoader();
      const success = await deleteRule(ruleData.id);
      if (success) {
        await fetchRules();
        closeDrawer();
      }
    } finally {
      hideLoader();
      setLoading(false);
    }
  };

  const handleEditClick = () => {
    // Navigate to create flow in edit mode with the current rule data
    openDrawerWithStep("create-blocking-rule", {
      editMode: true,
      rule: ruleData,
      ruleId: ruleData.id,
    });
  };

  const handleToggleStatus = async () => {
    // Normalize status to uppercase for comparison, but use lowercase for API
    const isActive = ruleData.status?.toLowerCase() === "active";
    const newStatus = isActive ? "inactive" : "active"; // Backend expects lowercase
    const actionText = isActive ? "disable" : "enable";

    openConfirm({
      message: `You're about to ${actionText} the ${ruleData.name} blocking rule`,
      description: `Are you sure you want to ${actionText} this rule?`,
      cancelAction: () => {},
      cancelText: "Cancel",
      okAction: async () => {
        try {
          setLoading(true);
          showLoader();
          const success = await updateRule(ruleData.id, { status: newStatus });
          if (success) {
            await fetchRules();
            // Update the current view by closing and reopening the drawer with fresh data
            closeDrawer();
          }
        } finally {
          hideLoader();
          setLoading(false);
        }
      },
      okText: `${actionText.charAt(0).toUpperCase() + actionText.slice(1)} Rule`,
      type: "warning",
      loading: loading,
      key: "toggle-rule-status",
    });
  };

  const handleDeleteClick = () => {
    openConfirm({
      message: `You're about to delete the ${ruleData.name} blocking rule`,
      description:
        "Once you delete the rule, it will not be recovered. Are you sure?",
      cancelAction: () => {},
      cancelText: "Cancel",
      okAction: handleDelete,
      okText: "Delete Rule",
      type: "warning",
      loading: loading,
      key: "delete-rule",
    });
  };

  return (
    <BudForm data={{}}>
      {contextHolder}
      <BudWraperBox classNames="mt-[1.9375rem]">
        <BudDrawerLayout>
          {/* Header */}
          <div className="px-[1.4rem] pt-[1.4rem] border-b-[1px] border-b-[#1F1F1F]">
            <div className="w-full flex justify-between items-start">
              <Text_14_400_EEEEEE>{ruleData.name}</Text_14_400_EEEEEE>
              <div>
                <CustomDropDown
                  parentClassNames="oneDrop"
                  buttonContent={
                    <div className="px-[.3rem] my-[0] py-[0.02rem]">
                      <Image
                        preview={false}
                        src="/images/drawer/threeDots.png"
                        alt="info"
                        style={{ width: "0.1125rem", height: ".6rem" }}
                      />
                    </div>
                  }
                  items={[
                    {
                      key: "1",
                      label: <Text_12_400_EEEEEE>Edit</Text_12_400_EEEEEE>,
                      onClick: handleEditClick,
                    },
                    {
                      key: "2",
                      label: (
                        <Text_12_400_EEEEEE>
                          {ruleData.status?.toLowerCase() === "active"
                            ? "Disable"
                            : "Enable"}
                        </Text_12_400_EEEEEE>
                      ),
                      onClick: handleToggleStatus,
                    },
                    {
                      key: "3",
                      label: <Text_12_400_EEEEEE>Delete</Text_12_400_EEEEEE>,
                      onClick: handleDeleteClick,
                    },
                  ]}
                />
              </div>
            </div>

            {/* Details in key-value format like API key view */}
            <div className="flex justify-between pt-[.7rem] flex-wrap items-center pb-[1rem] gap-[.9rem]">
              <div className="flex justify-between items-center w-full gap-[.5rem]">
                <div className="width-120">
                  <Text_12_400_B3B3B3>Type</Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-start w-full">
                  <Text_12_400_EEEEEE className="leading-[100%] !leading-[0.875rem]">
                    {RULE_TYPE_LABELS[ruleData.rule_type]}
                  </Text_12_400_EEEEEE>
                </div>
              </div>

              <div className="flex justify-between items-center w-full gap-[.5rem]">
                <div className="width-120">
                  <Text_12_400_B3B3B3>Status</Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-start w-full">
                  <ProjectTags
                    name={
                      ruleData.status.charAt(0).toUpperCase() +
                      ruleData.status.slice(1).toLowerCase()
                    }
                    color={getStatusColorMapping(ruleData.status)}
                    textClass="text-[.75rem]"
                  />
                </div>
              </div>

              <div className="flex justify-between items-center w-full gap-[.5rem]">
                <div className="width-120">
                  <Text_12_400_B3B3B3>Priority</Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-start w-full">
                  <Text_12_400_EEEEEE>{ruleData.priority}</Text_12_400_EEEEEE>
                </div>
              </div>

              <div className="flex justify-between items-center w-full gap-[.5rem]">
                <div className="width-120">
                  <Text_12_400_B3B3B3>Reason</Text_12_400_B3B3B3>
                </div>
                <div className="flex items-center justify-start w-full">
                  <Text_12_400_EEEEEE className="leading-[100%] !leading-[0.875rem] max-w-[300px]">
                    {ruleData.reason}
                  </Text_12_400_EEEEEE>
                </div>
              </div>
            </div>
          </div>

          {/* Details */}
          <div className="pb-[1.8rem] pt-[.4rem] px-[1.4rem] space-y-6">
            {/* Configuration */}
            <div>
              <Text_14_400_EEEEEE className="mb-3">
                Configuration
              </Text_14_400_EEEEEE>
              <div className="bg-[#0F0F0F] rounded-lg p-4">
                {formatRuleConfig(ruleData.rule_config, ruleData.rule_type)}
              </div>
            </div>

            {/* Statistics */}
            <div>
              <Text_14_400_EEEEEE className="mb-3">
                Statistics
              </Text_14_400_EEEEEE>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-[#0F0F0F] rounded-lg p-4">
                  <Text_12_400_B3B3B3 className="mb-1">
                    Total Matches
                  </Text_12_400_B3B3B3>
                  <Text_14_400_EEEEEE>
                    {ruleData.match_count.toLocaleString()}
                  </Text_14_400_EEEEEE>
                </div>
                <div className="bg-[#0F0F0F] rounded-lg p-4">
                  <Text_12_400_B3B3B3 className="mb-1">
                    Last Matched
                  </Text_12_400_B3B3B3>
                  <Text_14_400_EEEEEE>
                    {ruleData.last_matched_at
                      ? formatDistanceToNow(
                          new Date(ruleData.last_matched_at),
                        ) + " ago"
                      : "Never"}
                  </Text_14_400_EEEEEE>
                </div>
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
