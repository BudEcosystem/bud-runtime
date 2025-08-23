import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { ChevronRight } from "lucide-react";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import CustomPopover from "src/flows/components/customPopover";
import Tags from "src/flows/components/DrawerTags";
import {
  Text_10_400_757575,
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

interface Probe {
  id: string;
  name: string;
  category: string;
  description?: string;
}

export default function BudSentinelProbes() {
  const { openDrawerWithStep, openDrawerWithExpandedStep } = useDrawer();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedProbes, setSelectedProbes] = useState<string[]>([]);
  const [activeFilter, setActiveFilter] = useState<"all" | "pii" | "bias">("all");
  const [hoveredProbe, setHoveredProbe] = useState<string | null>(null);

  const getCategoryIcon = (category: string) => {
    switch (category.toLowerCase()) {
      case 'pii':
        return '🔒';
      case 'bias':
        return '⚖️';
      case 'content':
        return '🛡️';
      default:
        return '📋';
    }
  };

  const probes: Probe[] = [
    // PII Category
    { id: "pii-1", name: "PII Detection", category: "PII", description: "Detects and masks personal identifiable information in text" },
    { id: "pii-2", name: "Email Detection", category: "PII", description: "Identifies and redacts email addresses from content" },
    { id: "pii-3", name: "Phone Number Detection", category: "PII", description: "Finds and masks phone numbers in various formats" },
    { id: "pii-4", name: "SSN Detection", category: "PII", description: "Detects Social Security Numbers for compliance" },
    { id: "pii-5", name: "Credit Card Detection", category: "PII", description: "Identifies credit card numbers for PCI compliance" },

    // Bias Category
    { id: "bias-1", name: "Gender Bias Detection", category: "Bias", description: "Analyzes content for gender-based biases" },
    { id: "bias-2", name: "Racial Bias Detection", category: "Bias", description: "Identifies potential racial biases in text" },
    { id: "bias-3", name: "Age Bias Detection", category: "Bias", description: "Detects age-related discriminatory language" },
    { id: "bias-4", name: "Politeness detection", category: "Bias", description: "Evaluates tone and politeness levels" },

    // Other Categories
    { id: "prof-1", name: "Profanity Detection", category: "Content", description: "Filters profane and offensive language" },
    { id: "tox-1", name: "Toxicity Detection", category: "Content", description: "Identifies toxic and harmful content" },
    { id: "hate-1", name: "Hate Speech Detection", category: "Content", description: "Detects hate speech and discriminatory content" },
  ];

  const handleBack = () => {
    openDrawerWithStep("select-provider");
  };

  const handleNext = () => {
    if (selectedProbes.length === 0) {
      return;
    }

    // Navigate to specific configuration page based on selection
    if (selectedProbes.includes("pii-1")) {
      // PII Detection selected - go to PII configuration page
      openDrawerWithStep("pii-detection-config");
    } else {
      // For other selections, go directly to details
      openDrawerWithStep("guardrail-details");
    }
  };

  const toggleProbeSelection = (probeId: string) => {
    setSelectedProbes(prev =>
      prev.includes(probeId)
        ? prev.filter(id => id !== probeId)
        : [...prev, probeId]
    );
  };

  const handleSeeMore = (probe: Probe, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent probe selection when clicking "See more"

    // Store probe data in a state/store if needed or pass through drawer context
    // For now, we'll use the drawer step system
    openDrawerWithExpandedStep("probe-details");
  };

  const getFilteredProbes = () => {
    let filtered = probes;

    // Apply search filter
    if (searchTerm) {
      filtered = filtered.filter(probe =>
        probe.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        probe.category.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Apply category filter
    if (activeFilter !== "all") {
      filtered = filtered.filter(probe =>
        probe.category.toLowerCase() === activeFilter.toLowerCase()
      );
    }

    return filtered;
  };

  const groupedProbes = getFilteredProbes().reduce((acc, probe) => {
    if (!acc[probe.category]) {
      acc[probe.category] = [];
    }
    acc[probe.category].push(probe);
    return acc;
  }, {} as Record<string, Probe[]>);

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Next"
      disableNext={selectedProbes.length === 0}
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
              {Object.entries(groupedProbes).map(([category, categoryProbes]) => (
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
                          onClick={() => toggleProbeSelection(probe.id)}
                          className={`pt-[1.05rem] pb-[0.8rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] border-y-[#1F1F1F] hover:border-[#757575] flex-row flex border-box hover:bg-[#FFFFFF08] transition-all ${isSelected ? "bg-[#FFFFFF08] border-[#965CDE]" : ""
                            }`}
                        >
                          {/* Icon Section */}
                          <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center mr-[1.3rem] shrink-0 grow-0">
                            <span className="text-[1.5rem]">{getCategoryIcon(probe.category)}</span>
                          </div>

                          {/* Content Section */}
                          <div className="flex justify-between flex-col w-full max-w-[85%]">
                            <div className="flex items-center justify-between">
                              <div className="flex flex-grow max-w-[90%]"
                                style={{
                                  width: isHovered || isSelected ? "12rem" : "90%",
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
                                  display: (isHovered || isSelected) ? "flex" : "none",
                                }}
                                className="justify-end items-center"
                              >
                                <div
                                  className="items-center text-[0.75rem] cursor-pointer text-[#757575] hover:text-[#EEEEEE] flex mr-[0.6rem] whitespace-nowrap"
                                  onClick={(e) => handleSeeMore(probe, e)}
                                >
                                  See More <ChevronRight className="h-[1rem]" />
                                </div>
                                <CustomPopover
                                  Placement="topRight"
                                  title={isSelected ? "Deselect probe" : "Select probe"}
                                >
                                  <Checkbox
                                    checked={isSelected}
                                    className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] flex justify-center items-center"
                                    onClick={(e) => e.stopPropagation()}
                                    onChange={(e) => {
                                      e.stopPropagation();
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
              ))}

              {Object.keys(groupedProbes).length === 0 && (
                <div className="text-center py-[2rem]">
                  <Text_12_400_757575>No probes found matching your search</Text_12_400_757575>
                </div>
              )}
            </div>

            {/* Selected Count */}
            {selectedProbes.length > 0 && (
              <div className="mt-[2rem] p-[0.75rem] bg-[#965CDE10] border border-[#965CDE] rounded-[6px]">
                <Text_12_400_757575 className="text-[#965CDE]">
                  {selectedProbes.length} probe{selectedProbes.length > 1 ? 's' : ''} selected
                </Text_12_400_757575>
              </div>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
