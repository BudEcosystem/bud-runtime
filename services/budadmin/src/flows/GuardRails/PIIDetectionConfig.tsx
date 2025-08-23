import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Tag } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import CustomPopover from "src/flows/components/customPopover";
import { successToast } from "@/components/toast";
import {
  Text_10_400_757575,
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

interface SupportedRule {
  id: string;
  name: string;
  description: string;
  category?: string;
}

export default function PIIDetectionConfig() {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedRules, setSelectedRules] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [hoveredRule, setHoveredRule] = useState<string | null>(null);

  const getRuleIcon = (ruleId: string) => {
    const iconMap: Record<string, string> = {
      'email': '📧',
      'phone': '📱',
      'ssn': '🔢',
      'credit-card': '💳',
      'passport': '📘',
      'driver-license': '🚗',
      'ip-address': '🌐',
      'mac-address': '🖥️',
      'iban': '🏦',
      'swift': '💸',
      'date-of-birth': '📅',
      'address': '🏠',
      'medical-record': '🏥',
      'tax-id': '📋',
    };
    return iconMap[ruleId] || '🔒';
  };

  // Configuration data - would typically come from previous selection
  const probeTypes = ["Semantic", "Text", "RegEx"];
  const guardTypes = ["Input", "Output", "Retrieval", "Agent"];

  const supportedRules: SupportedRule[] = [
    { id: "email", name: "Email Address", description: "Detects email addresses in various formats" },
    { id: "phone", name: "Phone Number", description: "Identifies phone numbers including international formats" },
    { id: "ssn", name: "Social Security Number", description: "Detects SSN patterns (XXX-XX-XXXX)" },
    { id: "credit-card", name: "Credit Card", description: "Identifies credit card numbers with validation" },
    { id: "passport", name: "Passport Number", description: "Detects passport number patterns" },
    { id: "driver-license", name: "Driver's License", description: "Identifies driver's license numbers" },
    { id: "ip-address", name: "IP Address", description: "Detects IPv4 and IPv6 addresses" },
    { id: "mac-address", name: "MAC Address", description: "Identifies MAC addresses" },
    { id: "iban", name: "IBAN", description: "International Bank Account Numbers" },
    { id: "swift", name: "SWIFT/BIC Code", description: "Bank identification codes" },
    { id: "date-of-birth", name: "Date of Birth", description: "Detects various date formats" },
    { id: "address", name: "Physical Address", description: "Identifies street addresses" },
    { id: "medical-record", name: "Medical Record Number", description: "Healthcare record identifiers" },
    { id: "tax-id", name: "Tax ID", description: "Tax identification numbers" },
  ];

  const handleBack = () => {
    openDrawerWithStep("bud-sentinel-probes");
  };

  const handleNext = () => {
    if (selectedRules.length === 0) {
      return;
    }
    // Move to deployment types selection
    openDrawerWithStep("deployment-types");
  };

  const toggleRuleSelection = (ruleId: string) => {
    setSelectedRules(prev =>
      prev.includes(ruleId)
        ? prev.filter(id => id !== ruleId)
        : [...prev, ruleId]
    );
  };

  const handleSelectAll = (checked: boolean) => {
    setSelectAll(checked);
    if (checked) {
      setSelectedRules(getFilteredRules().map(rule => rule.id));
    } else {
      setSelectedRules([]);
    }
  };

  const getFilteredRules = () => {
    if (!searchTerm) return supportedRules;

    return supportedRules.filter(rule =>
      rule.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      rule.description.toLowerCase().includes(searchTerm.toLowerCase())
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
      disableNext={selectedRules.length === 0}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="PII Detection"
            description="Configure PII detection rules to identify and protect sensitive personal information"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="pb-[1.35rem]">
            {/* Probe Type and Guard Type */}
            <div className="mb-[2rem] grid grid-cols-2 gap-[1rem] px-[1.35rem]">
              <div>
                <Text_12_400_757575 className="mb-[0.5rem]">Probe type:</Text_12_400_757575>
                <div className="flex gap-[5px]">
                  {probeTypes.map((type) => (
                    <Tag key={type} className="bg-[#d1b85420] border-[#d1b854] text-[#d1b854] m-0">
                      {type}
                    </Tag>
                  ))}
                </div>
              </div>
              <div>
                <Text_12_400_757575 className="mb-[0.5rem]">Guard type:</Text_12_400_757575>
                <div className="flex gap-[5px] flex-wrap">
                  {guardTypes.map((type) => (
                    <Tag key={type} className="bg-[#d1b85420] border-[#d1b854] text-[#d1b854] m-0">
                      {type}
                    </Tag>
                  ))}
                </div>
              </div>
            </div>

            {/* Supported Rules Section */}
            <div>
              <Text_14_600_FFFFFF className="mb-[1rem] px-[1.35rem]">Supported Rules</Text_14_600_FFFFFF>

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
                {filteredRules.map((rule) => {
                  const isHovered = hoveredRule === rule.id;
                  const isSelected = selectedRules.includes(rule.id);

                  return (
                    <div
                      key={rule.id}
                      onMouseEnter={() => setHoveredRule(rule.id)}
                      onMouseLeave={() => setHoveredRule(null)}
                      onClick={() => toggleRuleSelection(rule.id)}
                      className={`pt-[1.05rem] pb-[0.8rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] border-y-[#1F1F1F] hover:border-[#757575] flex-row flex border-box hover:bg-[#FFFFFF08] transition-all ${
                        isSelected ? "bg-[#FFFFFF08] border-[#965CDE]" : ""
                      }`}
                    >
                      {/* Icon Section */}
                      <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center mr-[1.3rem] shrink-0 grow-0">
                        <span className="text-[1.5rem]">{getRuleIcon(rule.id)}</span>
                      </div>

                      {/* Content Section */}
                      <div className="flex justify-between flex-col w-full max-w-[85%]">
                        <div className="flex items-center justify-between">
                          <div className="flex flex-grow max-w-[90%]"
                            style={{
                              width: isHovered || isSelected ? "12rem" : "90%",
                            }}
                          >
                            <CustomPopover title={rule.name}>
                              <div className="text-[#EEEEEE] mr-2 pb-[0.3em] text-[0.875rem] truncate overflow-hidden whitespace-nowrap">
                                {rule.name}
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
                            <CustomPopover
                              Placement="topRight"
                              title={isSelected ? "Deselect rule" : "Select rule"}
                            >
                              <Checkbox
                                checked={isSelected}
                                className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] flex justify-center items-center"
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) => {
                                  e.stopPropagation();
                                  toggleRuleSelection(rule.id);
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
                })}

                {filteredRules.length === 0 && (
                  <div className="text-center py-[2rem]">
                    <Text_12_400_757575>No rules found matching your search</Text_12_400_757575>
                  </div>
                )}
              </div>

              {/* Selected Count */}
              {selectedRules.length > 0 && (
                <div className="mt-[1.5rem] p-[0.75rem] bg-[#965CDE10] border border-[#965CDE] rounded-[6px]">
                  <Text_12_400_757575 className="text-[#965CDE]">
                    {selectedRules.length} rule{selectedRules.length > 1 ? 's' : ''} selected
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
