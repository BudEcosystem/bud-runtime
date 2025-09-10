import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Spin } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { ChevronRight } from "lucide-react";
import React, { useState, useEffect } from "react";
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
  const [selectedProbe, setSelectedProbe] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<"all" | "pii" | "bias">(
    "all",
  );
  const [hoveredProbe, setHoveredProbe] = useState<string | null>(null);

  // Use the guardrails hook
  const {
    probes,
    probesLoading,
    fetchProbes,
    totalProbes,
    fetchProbeById,
    setSelectedProbe: setSelectedProbeInStore,
    updateWorkflow,
    workflowLoading,
    currentWorkflow,
    getWorkflow,
  } = useGuardrails();

  // Fetch workflow if not available on mount
  useEffect(() => {
    if (!currentWorkflow) {
      console.log("No currentWorkflow found, attempting to fetch...");
      // If there's a workflow ID stored somewhere (e.g., in localStorage or session), fetch it
      // For now, we'll just log this issue
    }
  }, []);

  // Fetch probes on component mount and when search changes
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      // Debug: Log the current workflow to see what data we have
      console.log("Current workflow in BudSentinelProbes:", currentWorkflow);

      // Build filter payload with provider_id from workflow
      const filterPayload: any = {
        page: 1,
        page_size: 100, // Fetch all probes for now
      };

      // Add search filter if present
      if (searchTerm) {
        filterPayload.search = searchTerm;
      }

      // Add provider_id filter from the current workflow if available
      if (currentWorkflow?.provider_id) {
        filterPayload.provider_id = currentWorkflow.provider_id;
        console.log("Adding provider_id to filter:", currentWorkflow.provider_id);
      } else {
        console.log("No provider_id found in currentWorkflow");
      }

      console.log("Final filterPayload:", filterPayload);
      fetchProbes(filterPayload);
    }, 300); // Debounce search

    return () => clearTimeout(delayDebounceFn);
  }, [searchTerm, currentWorkflow?.provider_id]);

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
    if (!selectedProbe) {
      return;
    }

    // Check if selected probe is a PII probe
    const selectedProbeObject = probes.find((p) => p.id === selectedProbe);

    if (selectedProbeObject) {
      // Save the selected probe to the store
      setSelectedProbeInStore(selectedProbeObject);

      try {
        // Update workflow with selected probe
        await updateWorkflow({
          step_number: 2,
          workflow_total_steps: 6,
          probe_selections: [
            {
              probe_id: selectedProbe,
              enabled: true,
            },
          ],
          trigger_workflow: false,
        });

        const isPIIProbe =
          selectedProbeObject.name
            ?.toLowerCase()
            .includes("personal identifier") ||
          selectedProbeObject.name?.toLowerCase().includes("pii") ||
          selectedProbeObject.tags?.some(
            (tag) =>
              tag.name.toLowerCase().includes("dlp") ||
              tag.name.toLowerCase().includes("personal"),
          );

        // Navigate to specific configuration page based on selection
        if (isPIIProbe) {
          // PII Detection selected - go to PII configuration page
          openDrawerWithStep("pii-detection-config");
        } else {
          // For other selections, skip PII config and go to deployment types
          openDrawerWithStep("deployment-types");
        }
      } catch (error) {
        console.error("Failed to update workflow:", error);
      }
    }
  };

  const toggleProbeSelection = (probeId: string) => {
    setSelectedProbe((prev) => (prev === probeId ? null : probeId));
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

    // Apply search filter
    if (searchTerm) {
      filtered = filtered.filter(
        (probe) =>
          probe.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          probe.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
          probe.tags?.some((tag) =>
            tag.name.toLowerCase().includes(searchTerm.toLowerCase()),
          ),
      );
    }

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
      disableNext={!selectedProbe || workflowLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Probes List"
            description="Description of What probes are"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="pb-[1.35rem]">
            {/* Search Bar */}
            <div className="mb-[1.5rem] px-[1.35rem]">
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
            <div className="flex gap-[0.75rem] mb-[2rem] px-[1.35rem]">
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
                          const isSelected = selectedProbe === probe.id;

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
