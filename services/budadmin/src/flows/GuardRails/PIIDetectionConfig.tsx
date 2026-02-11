import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Spin, Tag } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import CustomPopover from "src/flows/components/customPopover";
import { successToast } from "@/components/toast";
import useGuardrails from "src/hooks/useGuardrails";
import { AppRequest } from "src/pages/api/requests";
import {
  Text_10_400_757575,
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";
import Tags from "../components/DrawerTags";

interface ProbeRuleWithProbe {
  rule: any; // ProbeRule type from useGuardrails
  probeId: string;
  probeName: string;
}

export default function PIIDetectionConfig() {
  const { openDrawerWithStep } = useDrawer();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedRules, setSelectedRules] = useState<{ probeId: string; ruleId: string }[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [hoveredRule, setHoveredRule] = useState<string | null>(null);
  const [allRules, setAllRules] = useState<ProbeRuleWithProbe[]>([]);
  const [isLoadingRules, setIsLoadingRules] = useState(false);

  // Use the guardrails hook
  const {
    selectedProbe,
    selectedProbes,
    probeRules,
    rulesLoading,
    fetchProbeRules,
    clearProbeRules,
    updateWorkflow,
    workflowLoading,
    currentWorkflow,
    selectedProvider,
  } = useGuardrails();

  // Fetch rules for all selected probes
  useEffect(() => {
    const fetchAllRules = async () => {
      const probesArray = selectedProbes?.length > 0 ? selectedProbes : (selectedProbe ? [selectedProbe] : []);
      setAllRules([]); // Clear existing rules
      setIsLoadingRules(true);

      if (probesArray.length > 0) {
        // Fetch rules for each selected probe in parallel
        const fetchPromises = probesArray.map(async (probe) => {
          if (!probe?.id) return [];

          try {
            // Directly call the API to fetch rules for this probe
            const response = await AppRequest.Get(
              `/guardrails/probe/${probe.id}/rules`,
              {
                params: {
                  page: 1,
                  limit: 100, // Get all rules
                },
              },
            );

            if (response.data?.rules) {
              // Map each rule with its probe information
              return response.data.rules.map((rule: any) => ({
                rule,
                probeId: probe.id,
                probeName: probe.name
              }));
            }
            return [];
          } catch (error) {
            console.error(`Failed to fetch rules for probe ${probe.name}:`, error);
            return [];
          }
        });

        // Wait for all fetches to complete
        const results = await Promise.all(fetchPromises);

        // Flatten the results and set all rules
        const combinedRules = results.flat();
        setAllRules(combinedRules);
      }

      setIsLoadingRules(false);
    };

    fetchAllRules();

    // Clear rules when component unmounts
    return () => {
      setAllRules([]);
    };
  }, [selectedProbes?.length, selectedProbe?.id]);

  const getRuleIcon = (ruleName: string) => {
    const name = ruleName.toLowerCase();
    if (name.includes("email")) return "📧";
    if (name.includes("phone")) return "📱";
    if (name.includes("social security") || name.includes("ssn")) return "🔢";
    if (name.includes("credit") || name.includes("card")) return "💳";
    if (name.includes("passport")) return "📘";
    if (name.includes("driver") || name.includes("license")) return "🚗";
    if (name.includes("ip address")) return "🌐";
    if (name.includes("mac address")) return "🖥️";
    if (name.includes("iban") || name.includes("bank")) return "🏦";
    if (name.includes("swift") || name.includes("bic")) return "💸";
    if (name.includes("date")) return "📅";
    if (name.includes("address")) return "🏠";
    if (name.includes("medical") || name.includes("medicare")) return "🏥";
    if (name.includes("tax") || name.includes("tfn") || name.includes("pan"))
      return "📋";
    if (name.includes("aadhaar")) return "🆔";
    if (name.includes("crypto") || name.includes("wallet")) return "₿";
    if (name.includes("routing")) return "🏛️";
    if (
      name.includes("abn") ||
      name.includes("acn") ||
      name.includes("business")
    )
      return "🏢";
    if (name.includes("vehicle") || name.includes("registration")) return "🚙";
    if (name.includes("voter")) return "🗳️";
    if (name.includes("fiscal") || name.includes("vat")) return "📊";
    return "🔒";
  };

  // Configuration data from selected probes
  const probesArray = selectedProbes?.length > 0 ? selectedProbes : (selectedProbe ? [selectedProbe] : []);
  const probeTypes = Array.from(new Set(
    probesArray.flatMap(probe => probe?.tags?.map(tag => tag.name) || [])
  )).filter(Boolean);
  const guardTypes = ["Input", "Output", "Retrieval", "Agent"];

  const handleBack = () => {
    openDrawerWithStep("bud-sentinel-probes");
  };

  const handleNext = async () => {
    if (selectedRules.length === 0) {
      return;
    }

    try {
      // Group selected rules by probe ID
      const rulesByProbe = selectedRules.reduce((acc, selection) => {
        if (!acc[selection.probeId]) {
          acc[selection.probeId] = [];
        }
        acc[selection.probeId].push(selection.ruleId);
        return acc;
      }, {} as Record<string, string[]>);

      // Build probe_selections array with rules for each probe
      // Include all probes, even those without selected rules
      const probesArray = selectedProbes?.length > 0 ? selectedProbes : (selectedProbe ? [selectedProbe] : []);
      const probeSelections = probesArray.map(probe => {
        const selectedRuleIds = rulesByProbe[probe.id] || [];

        // Get all rules for this probe from allRules
        const probeRules = allRules.filter(r => r.probeId === probe.id);

        if (probeRules.length > 0 && selectedRuleIds.length > 0) {
          // Include all rules with their status (active if selected, disabled if not)
          const rulesWithStatus = probeRules.map(ruleWithProbe => ({
            id: ruleWithProbe.rule.id,
            status: selectedRuleIds.includes(ruleWithProbe.rule.id) ? "active" : "disabled"
          }));

          return {
            id: probe.id,
            rules: rulesWithStatus
          };
        } else if (selectedRuleIds.length > 0) {
          // Fallback: if we don't have all rules, just include selected ones as active
          return {
            id: probe.id,
            rules: selectedRuleIds.map(ruleId => ({
              id: ruleId,
              status: "active"
            }))
          };
        } else {
          // Probe without selected rules
          return {
            id: probe.id
          };
        }
      });

      // Build the update payload
      const updatePayload: any = {
        step_number: 2,
        probe_selections: probeSelections,
        trigger_workflow: false,
      };

      // Include workflow_id if available
      if (currentWorkflow?.workflow_id) {
        updatePayload.workflow_id = currentWorkflow.workflow_id;
      }

      // Include provider data from previous step
      if (selectedProvider?.id) {
        updatePayload.provider_id = selectedProvider.id;
      }
      if (selectedProvider?.provider_type) {
        updatePayload.provider_type = selectedProvider.provider_type;
      }

      // Update workflow with selected rules
      await updateWorkflow(updatePayload);

      // Move to project selection
      openDrawerWithStep("select-project");
    } catch (error) {
      console.error("Failed to update workflow:", error);
    }
  };

  const toggleRuleSelection = (ruleId: string, probeId: string) => {
    setSelectedRules((prev) => {
      const exists = prev.some(s => s.probeId === probeId && s.ruleId === ruleId);
      if (exists) {
        return prev.filter(s => !(s.probeId === probeId && s.ruleId === ruleId));
      } else {
        return [...prev, { probeId, ruleId }];
      }
    });
  };

  const handleSelectAll = (checked: boolean) => {
    setSelectAll(checked);
    if (checked) {
      const allRuleSelections = getFilteredRules().map((ruleWithProbe) => ({
        probeId: ruleWithProbe.probeId,
        ruleId: ruleWithProbe.rule.id
      }));
      setSelectedRules(allRuleSelections);
    } else {
      setSelectedRules([]);
    }
  };

  const getFilteredRules = () => {
    if (!searchTerm) return allRules;

    return allRules.filter(
      (ruleWithProbe) =>
        ruleWithProbe.rule.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        ruleWithProbe.rule.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        ruleWithProbe.probeName.toLowerCase().includes(searchTerm.toLowerCase()),
    );
  };

  const filteredRules = getFilteredRules();

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Next"
      disableNext={selectedRules.length === 0 || workflowLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={
              probesArray.length > 1
                ? `Configure ${probesArray.length} Probes`
                : (probesArray[0]?.name || "PII Detection")
            }
            description={
              probesArray.length > 1
                ? `Configure detection rules for ${probesArray.map(p => p?.name).join(", ")}`
                : (probesArray[0]?.description || "Configure PII detection rules to identify and protect sensitive personal information")
            }
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="pb-[1.35rem]">
            {/* Probe Type and Guard Type */}
            <div className="mb-[2rem] grid grid-cols-2 gap-[1rem] px-[1.35rem]">
              <div>
                <Text_12_400_757575 className="mb-[0.5rem]">
                  Probe type:
                </Text_12_400_757575>
                <div className="flex gap-[5px]">
                  {probeTypes.map((type) => (
                    <Tags
                      name={type}
                      color="#d1b854"
                      key={type}></Tags>
                  ))}
                </div>
              </div>
              <div>
                <Text_12_400_757575 className="mb-[0.5rem]">
                  Guard type:
                </Text_12_400_757575>
                <div className="flex gap-[5px] flex-wrap">
                  {guardTypes.map((type) => (
                    <Tags
                      name={type}
                      color="#d1b854"
                      key={type}></Tags>
                  ))}
                </div>
              </div>
            </div>

            {/* Supported Rules Section */}
            <div>
              <Text_14_600_FFFFFF className="mb-[1rem] px-[1.35rem]">
                Supported Rules
              </Text_14_600_FFFFFF>

              {/* Search Bar */}
              <div className="mb-[1rem] px-[1.35rem]">
                <Input
                  placeholder="Search"
                  prefix={<SearchOutlined className="text-[#757575]" />}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="bg-transparent text-[#EEEEEE] border-[#757575] hover:border-[#EEEEEE] focus:border-[#EEEEEE]"
                  style={{
                    backgroundColor: "transparent",
                    color: "#EEEEEE",
                  }}
                />
              </div>

              {/* Select All Checkbox */}
              <div className="p-[0.75rem] border-b border-[#2A2A2A] px-[1.35rem]">
                <Checkbox
                  checked={selectAll}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                  className="AntCheckbox flex items-center"
                >
                  <Text_14_400_EEEEEE>Select All</Text_14_400_EEEEEE>
                </Checkbox>
              </div>

              {/* Rules List - ModelListCard Style */}
              <div className="max-h-[400px] overflow-y-auto">
                {isLoadingRules ? (
                  <div className="flex justify-center py-[3rem]">
                    <Spin size="large" />
                  </div>
                ) : (
                  filteredRules.map((ruleWithProbe) => {
                    const rule = ruleWithProbe.rule;
                    const ruleKey = `${ruleWithProbe.probeId}-${rule.id}`;
                    const isHovered = hoveredRule === ruleKey;
                    const isSelected = selectedRules.some(
                      s => s.probeId === ruleWithProbe.probeId && s.ruleId === rule.id
                    );

                    return (
                      <div
                        key={ruleKey}
                        onMouseEnter={() => setHoveredRule(ruleKey)}
                        onMouseLeave={() => setHoveredRule(null)}
                        onClick={() => toggleRuleSelection(rule.id, ruleWithProbe.probeId)}
                        className={`pt-[1.05rem] pb-[0.8rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] border-y-[#1F1F1F] hover:border-[#757575] flex-row flex border-box hover:bg-[#FFFFFF08] transition-all ${
                          isSelected ? "bg-[#FFFFFF08] border-[#965CDE]" : ""
                        }`}
                      >
                        {/* Icon Section */}
                        <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center mr-[1.3rem] shrink-0 grow-0">
                          <span className="text-[1.5rem]">
                            {getRuleIcon(rule.name)}
                          </span>
                        </div>

                        {/* Content Section */}
                        <div className="flex justify-between flex-col w-full max-w-[85%]">
                          <div className="flex items-center justify-between">
                            <div
                              className="flex flex-col flex-grow max-w-[90%]"
                              style={{
                                width:
                                  isHovered || isSelected ? "12rem" : "90%",
                              }}
                            >
                              <CustomPopover title={rule.name}>
                                <div className="text-[#EEEEEE] mr-2 pb-[0.3em] text-[0.875rem] truncate overflow-hidden whitespace-nowrap">
                                  {rule.name}
                                </div>
                              </CustomPopover>
                              {probesArray.length > 1 && (
                                <div className="text-[#965CDE] text-[0.625rem] mt-[0.2rem]">
                                  {ruleWithProbe.probeName}
                                </div>
                              )}
                            </div>

                            {/* Actions Section */}
                            <div
                              style={{
                                display:
                                  isHovered || isSelected ? "flex" : "none",
                              }}
                              className="justify-end items-center"
                            >
                              <CustomPopover
                                Placement="topRight"
                                title={
                                  isSelected ? "Deselect rule" : "Select rule"
                                }
                              >
                                <Checkbox
                                  checked={isSelected}
                                  className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] flex justify-center items-center"
                                  onClick={(e) => e.stopPropagation()}
                                  onChange={(e) => {
                                    e.stopPropagation();
                                    toggleRuleSelection(rule.id, ruleWithProbe.probeId);
                                  }}
                                />
                              </CustomPopover>
                            </div>
                          </div>

                          {/* Description */}
                          <CustomPopover title={rule.description}>
                            <div className="text-[#757575] w-full overflow-hidden text-ellipsis text-xs line-clamp-2 leading-[150%]">
                              {rule.description || "-"}
                            </div>
                          </CustomPopover>
                        </div>
                      </div>
                    );
                  })
                )}

                {!isLoadingRules && filteredRules.length === 0 && (
                  <div className="text-center py-[2rem]">
                    <Text_12_400_757575>
                      No rules found matching your search
                    </Text_12_400_757575>
                  </div>
                )}
              </div>

              {/* Selected Count */}
              {selectedRules.length > 0 && (
                <div className="mt-[1.5rem] p-[0.75rem] bg-[#965CDE10] border border-[#965CDE] rounded-[6px]">
                  <Text_12_400_757575 className="text-[#965CDE]">
                    {selectedRules.length} rule
                    {selectedRules.length > 1 ? "s" : ""} selected
                  </Text_12_400_757575>
                </div>
              )}
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
