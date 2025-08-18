import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Button, Checkbox } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { ChevronRight } from "lucide-react";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
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

  const probes: Probe[] = [
    // PII Category
    { id: "pii-1", name: "PII Detection", category: "PII" },
    { id: "pii-2", name: "Email Detection", category: "PII" },
    { id: "pii-3", name: "Phone Number Detection", category: "PII" },
    { id: "pii-4", name: "SSN Detection", category: "PII" },
    { id: "pii-5", name: "Credit Card Detection", category: "PII" },

    // Bias Category
    { id: "bias-1", name: "Gender Bias Detection", category: "Bias" },
    { id: "bias-2", name: "Racial Bias Detection", category: "Bias" },
    { id: "bias-3", name: "Age Bias Detection", category: "Bias" },
    { id: "bias-4", name: "Politeness detection", category: "Bias" },

    // Other Categories
    { id: "prof-1", name: "Profanity Detection", category: "Content" },
    { id: "tox-1", name: "Toxicity Detection", category: "Content" },
    { id: "hate-1", name: "Hate Speech Detection", category: "Content" },
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

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Search Bar */}
            <div className="mb-[1.5rem]">
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
            <div className="flex gap-[0.75rem] mb-[2rem]">
              <Button
                onClick={() => setActiveFilter("pii")}
                className={`!bg-transparent ${
                  activeFilter === "pii"
                    ? "!border-[#965CDE] !text-[#965CDE]"
                    : "!border-[#757575] !text-[#757575]"
                } hover:!border-[#965CDE] hover:!text-[#965CDE]`}
                style={{ backgroundColor: "transparent" }}
              >
                PII
              </Button>
              <Button
                onClick={() => setActiveFilter("bias")}
                className={`!bg-transparent ${
                  activeFilter === "bias"
                    ? "!border-[#965CDE] !text-[#965CDE]"
                    : "!border-[#757575] !text-[#757575]"
                } hover:!border-[#965CDE] hover:!text-[#965CDE]`}
                style={{ backgroundColor: "transparent" }}
              >
                Bias
              </Button>
              <Button
                onClick={() => setActiveFilter("all")}
                className={`!bg-transparent ${
                  activeFilter === "all"
                    ? "!border-[#965CDE] !text-[#965CDE]"
                    : "!border-[#757575] !text-[#757575]"
                } hover:!border-[#965CDE] hover:!text-[#965CDE]`}
                style={{ backgroundColor: "transparent" }}
              >
                All
              </Button>
            </div>

            {/* Probes List */}
            <div className="space-y-[1.5rem]">
              {Object.entries(groupedProbes).map(([category, categoryProbes]) => (
                <div key={category}>
                  {/* Category Header */}
                  <div className="mb-[0.75rem]">
                    <Text_14_600_FFFFFF>{category}</Text_14_600_FFFFFF>
                  </div>

                  {/* Probe Items */}
                  <div className="space-y-[0.5rem]">
                    {categoryProbes.map((probe) => (
                      <div
                        key={probe.id}
                        onClick={() => toggleProbeSelection(probe.id)}
                        className={`p-[1rem] border rounded-[6px] cursor-pointer transition-all flex items-center justify-between ${
                          selectedProbes.includes(probe.id)
                            ? "border-[#965CDE] bg-[#965CDE10]"
                            : "border-[#757575] hover:border-[#965CDE] hover:bg-[#965CDE05]"
                        }`}
                      >
                        <div className="flex items-center gap-[0.75rem]">
                          <Checkbox
                            checked={selectedProbes.includes(probe.id)}
                            className="AntCheckbox"
                            onChange={(e) => {
                              e.stopPropagation();
                              toggleProbeSelection(probe.id);
                            }}
                          />
                          <Text_14_400_EEEEEE>{probe.name}</Text_14_400_EEEEEE>
                        </div>
                        <div
                          className="items-center text-[0.75rem] cursor-pointer text-[#757575] hover:text-[#EEEEEE] flex whitespace-nowrap"
                          onClick={(e) => handleSeeMore(probe, e)}
                        >
                          See More <ChevronRight className="h-[1rem]" />
                        </div>
                      </div>
                    ))}
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
