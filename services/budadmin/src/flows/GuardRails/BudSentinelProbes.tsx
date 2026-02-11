import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Spin } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { ChevronRight } from "lucide-react";
import React, { useState, useEffect, useRef, useCallback } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import CustomPopover from "src/flows/components/customPopover";
import Tags from "src/flows/components/DrawerTags";
import useGuardrails from "src/hooks/useGuardrails";
import {
  Text_10_400_757575,
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

export default function BudSentinelProbes() {
  const { openDrawerWithStep, openDrawerWithExpandedStep } = useDrawer();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedProbes, setSelectedProbes] = useState<string[]>([]);
  const [activeFilter, setActiveFilter] = useState<"all" | "pii" | "bias">(
    "all",
  );
  const [hoveredProbe, setHoveredProbe] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const isLoadingMore = useRef(false);

  // Use the guardrails hook
  const {
    probes,
    probesLoading,
    fetchProbes,
    totalProbes,
    totalPages,
    fetchProbeById,
    setSelectedProbe: setSelectedProbeInStore,
    setSelectedProbes: setSelectedProbesInStore,
    updateWorkflow,
    workflowLoading,
    selectedProvider,
    currentWorkflow,
  } = useGuardrails();

  // Fetch probes on component mount and when search changes
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      setPage(1);

      const filterPayload: any = {
        page: 1,
        limit: 10,
      };

      if (searchTerm) {
        filterPayload.search = true;
        filterPayload.name = searchTerm;
      }

      fetchProbes(filterPayload);
    }, 300);

    return () => clearTimeout(delayDebounceFn);
  }, [searchTerm, selectedProvider?.id]);

  // Load more probes for infinite scroll
  const loadMore = useCallback(async () => {
    if (isLoadingMore.current || page >= totalPages) return;
    isLoadingMore.current = true;

    const nextPage = page + 1;
    const filterPayload: any = {
      page: nextPage,
      limit: 10,
      append: true,
    };

    if (searchTerm) {
      filterPayload.search = true;
      filterPayload.name = searchTerm;
    }

    await fetchProbes(filterPayload);
    setPage(nextPage);
    isLoadingMore.current = false;
  }, [page, totalPages, searchTerm, fetchProbes]);

  // Scroll handler for infinite scroll
  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      const target = e.currentTarget;
      const isNearBottom =
        target.scrollTop + target.clientHeight >= target.scrollHeight - 100;

      if (isNearBottom && !isLoadingMore.current && page < totalPages) {
        loadMore();
      }
    },
    [loadMore, page, totalPages],
  );

  const getCategoryIcon = (category: string) => {
    switch (category.toLowerCase()) {
      case "pii":
      case "personal identifier information":
      case "data loss prevention (dlp)":
        return "🔒";
      case "bias":
        return "⚖️";
      case "content":
      case "secrets & credentials":
        return "🛡️";
      default:
        return "📋";
    }
  };

  const handleBack = () => {
    openDrawerWithStep("select-provider");
  };

  const handleNext = async () => {
    if (selectedProbes.length === 0) {
      return;
    }

    // Get the selected probe objects
    const selectedProbeObjects = probes.filter((p) => selectedProbes.includes(p.id));

    if (selectedProbeObjects.length > 0) {
      // Save the first selected probe to the store (for backward compatibility)
      setSelectedProbeInStore(selectedProbeObjects[0]);
      // Save all selected probes for the PIIDetectionConfig
      setSelectedProbesInStore(selectedProbeObjects);

      try {
        // Build the payload with data from previous step
        const payload: any = {
          step_number: 2,
          probe_selections: selectedProbes.map(probeId => ({
            id: probeId,
          })),
          trigger_workflow: false,
        };

        // Include workflow_id if available
        if (currentWorkflow?.workflow_id) {
          payload.workflow_id = currentWorkflow.workflow_id;
        }

        // Include provider data from previous step
        if (selectedProvider?.id) {
          payload.provider_id = selectedProvider.id;
        }
        if (selectedProvider?.provider_type) {
          payload.provider_type = selectedProvider.provider_type;
        }

        // Update workflow with selected probes and provider data
        await updateWorkflow(payload);

        // Check if any selected probe is a PII probe
        const hasPIIProbe = selectedProbeObjects.some(probe =>
          probe.name
            ?.toLowerCase()
            .includes("personal identifier") ||
          probe.name?.toLowerCase().includes("pii") ||
          probe.tags?.some(
            (tag) =>
              tag.name.toLowerCase().includes("dlp") ||
              tag.name.toLowerCase().includes("personal"),
          )
        );

        // Navigate to specific configuration page based on selection
        if (hasPIIProbe) {
          // PII Detection selected - go to PII configuration page
          openDrawerWithStep("pii-detection-config");
        } else {
          // For other selections, skip PII config and go to project selection
          openDrawerWithStep("select-project");
        }
      } catch (error) {
        console.error("Failed to update workflow:", error);
      }
    }
  };

  const toggleProbeSelection = (probeId: string) => {
    setSelectedProbes((prev) => {
      if (prev.includes(probeId)) {
        return prev.filter((id) => id !== probeId);
      } else {
        return [...prev, probeId];
      }
    });
  };

  const handleSeeMore = async (probe: any, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent probe selection when clicking "See more"

    // Fetch full probe details if needed
    if (probe.id) {
      await fetchProbeById(probe.id);
    }

    // Open the expanded drawer with probe details
    openDrawerWithExpandedStep("probe-details");
  };

  const getFilteredProbes = () => {
    let filtered = probes || [];

    // Apply category filter based on tags
    if (activeFilter !== "all") {
      filtered = filtered.filter((probe) => {
        // Check if probe has tags matching the filter
        if (activeFilter === "pii") {
          return probe.tags?.some(
            (tag) =>
              tag.name.toLowerCase().includes("pii") ||
              tag.name.toLowerCase().includes("personal") ||
              tag.name.toLowerCase().includes("dlp"),
          );
        } else if (activeFilter === "bias") {
          return probe.tags?.some((tag) =>
            tag.name.toLowerCase().includes("bias"),
          );
        }
        return false;
      });
    }

    return filtered;
  };

  // Group probes by their first tag or provider type
  const groupedProbes = getFilteredProbes().reduce(
    (acc, probe) => {
      // Use the first tag name as category, or provider_type as fallback
      const category = probe.tags?.[0]?.name || probe.provider_type || "Other";
      if (!acc[category]) {
        acc[category] = [];
      }
      acc[category].push(probe);
      return acc;
    },
    {} as Record<string, any[]>,
  );

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Next"
      disableNext={selectedProbes.length === 0 || workflowLoading}
    >
      <BudWraperBox onScroll={handleScroll}>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Probes List"
            description="Description of What probes are"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="pb-[1.35rem]">
            {/* Search Bar */}
            <div className="mb-[1.5rem] px-[1.35rem] mt-[1.5rem]">
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

            {/* Filter Buttons */}
            <div className="flex gap-[0.75rem] mb-[2rem] px-[1.35rem] hidden">
              <Tags
                name="PII"
                color={activeFilter === "pii" ? "#D1B854" : "#757575"}
                classNames={`cursor-pointer px-[1rem] py-[0.5rem] rounded-[6px] transition-all ${
                  activeFilter === "pii"
                    ? "!bg-[#D1B85420]"
                    : "!bg-transparent border-[0.5px] border-[#757575] hover:border-[#D1B854]"
                }`}
                onTagClick={() => setActiveFilter("pii")}
              />
              <Tags
                name="Bias"
                color={activeFilter === "bias" ? "#D1B854" : "#757575"}
                classNames={`cursor-pointer px-[1rem] py-[0.5rem] rounded-[6px] transition-all ${
                  activeFilter === "bias"
                    ? "!bg-[#D1B85420]"
                    : "!bg-transparent border-[0.5px] border-[#757575] hover:border-[#D1B854]"
                }`}
                onTagClick={() => setActiveFilter("bias")}
              />
              <Tags
                name="All"
                color={activeFilter === "all" ? "#D1B854" : "#757575"}
                classNames={`cursor-pointer px-[1rem] py-[0.5rem] rounded-[6px] transition-all ${
                  activeFilter === "all"
                    ? "!bg-[#D1B85420]"
                    : "!bg-transparent border-[0.5px] border-[#757575] hover:border-[#D1B854]"
                }`}
                onTagClick={() => setActiveFilter("all")}
              />
            </div>

            {/* Probes List */}
            <div className="space-y-[1.5rem]">
              {probesLoading ? (
                <div className="flex justify-center py-[3rem]">
                  <Spin size="large" />
                </div>
              ) : (
                Object.entries(groupedProbes).map(
                  ([category, categoryProbes]) => (
                    <div key={category}>
                      {/* Category Header */}
                      <div className="mb-[0.75rem] px-[1.35rem]">
                        <Text_14_600_FFFFFF>{category}</Text_14_600_FFFFFF>
                      </div>

                      {/* Probe Items - ModelListCard Style */}
                      <div>
                        {categoryProbes.map((probe) => {
                          const isHovered = hoveredProbe === probe.id;
                          const isSelected = selectedProbes.includes(probe.id);

                          return (
                            <div
                              key={probe.id}
                              onMouseEnter={() => setHoveredProbe(probe.id)}
                              onMouseLeave={() => setHoveredProbe(null)}
                              onClick={(e) => {
                                // Only toggle selection if not clicking on checkbox or "See More"
                                const target = e.target as HTMLElement;
                                if (
                                  !target.closest(".ant-checkbox-wrapper") &&
                                  !target.closest("[data-see-more]")
                                ) {
                                  toggleProbeSelection(probe.id);
                                }
                              }}
                              className={`pt-[1.05rem] pb-[0.8rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] border-y-[#1F1F1F] hover:border-[#757575] flex-row flex border-box hover:bg-[#FFFFFF08] transition-all ${
                                isSelected
                                  ? "bg-[#FFFFFF08] border-[#965CDE]"
                                  : ""
                              }`}
                            >
                              {/* Icon Section */}
                              <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center mr-[1.3rem] shrink-0 grow-0">
                                <span className="text-[1.5rem]">
                                  {getCategoryIcon(
                                    probe.name ||
                                      probe.tags?.[0]?.name ||
                                      category,
                                  )}
                                </span>
                              </div>

                              {/* Content Section */}
                              <div className="flex justify-between flex-col w-full max-w-[85%]">
                                <div className="flex items-center justify-between">
                                  <div
                                    className="flex flex-grow max-w-[90%]"
                                    style={{
                                      width:
                                        isHovered || isSelected
                                          ? "12rem"
                                          : "90%",
                                    }}
                                  >
                                    <CustomPopover title={probe.name}>
                                      <div className="text-[#EEEEEE] mr-2 pb-[0.3em] text-[0.875rem] truncate overflow-hidden whitespace-nowrap">
                                        {probe.name}
                                      </div>
                                    </CustomPopover>
                                  </div>

                                  {/* Actions Section */}
                                  <div
                                    style={{
                                      display:
                                        isHovered || isSelected
                                          ? "flex"
                                          : "none",
                                    }}
                                    className="justify-end items-center"
                                  >
                                    <div
                                      className="items-center text-[0.75rem] cursor-pointer text-[#757575] hover:text-[#EEEEEE] flex mr-[0.6rem] whitespace-nowrap"
                                      data-see-more="true"
                                      onClick={(e) => handleSeeMore(probe, e)}
                                    >
                                      See More{" "}
                                      <ChevronRight className="h-[1rem]" />
                                    </div>
                                    <CustomPopover
                                      Placement="topRight"
                                      title={
                                        isSelected
                                          ? "Deselect probe"
                                          : "Select probe"
                                      }
                                    >
                                      <Checkbox
                                        checked={isSelected}
                                        className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] flex justify-center items-center"
                                        onClick={(e) => e.stopPropagation()}
                                        onChange={() => {
                                          toggleProbeSelection(probe.id);
                                        }}
                                      />
                                    </CustomPopover>
                                  </div>
                                </div>

                                {/* Description */}
                                <CustomPopover title={probe.description}>
                                  <div className="text-[#757575] w-full overflow-hidden text-ellipsis text-xs line-clamp-2 leading-[150%]">
                                    {probe.description || "-"}
                                  </div>
                                </CustomPopover>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ),
                )
              )}

              {!probesLoading && page < totalPages && (
                <div className="flex justify-center py-[1rem]">
                  <Spin size="small" />
                </div>
              )}

              {!probesLoading && Object.keys(groupedProbes).length === 0 && (
                <div className="text-center py-[2rem]">
                  <Text_12_400_757575>
                    No probes found matching your search
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
