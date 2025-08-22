import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Tag } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
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

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Probe Type and Guard Type */}
            <div className="mb-[2rem] grid grid-cols-2 gap-[1rem]">
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
              <Text_14_600_FFFFFF className="mb-[1rem]">Supported Rules</Text_14_600_FFFFFF>

              {/* Search Bar */}
              <div className="mb-[1rem]">
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
              <div className="mb-[1rem] p-[0.75rem] border-b border-[#2A2A2A]">
                <Checkbox
                  checked={selectAll}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                  className="AntCheckbox flex items-center"
                >
                  <Text_14_400_EEEEEE>Select All</Text_14_400_EEEEEE>
                </Checkbox>
              </div>

              {/* Rules List */}
              <div className="space-y-[0.5rem] max-h-[400px] overflow-y-auto">
                {filteredRules.map((rule) => (
                  <div
                    key={rule.id}
                    onClick={() => toggleRuleSelection(rule.id)}
                    className={`p-[1rem] border rounded-[6px] cursor-pointer transition-all ${
                      selectedRules.includes(rule.id)
                        ? "border-[#965CDE] bg-[#965CDE10]"
                        : "border-[#2A2A2A] hover:border-[#757575] bg-[#1A1A1A]"
                    }`}
                  >
                    <div className="flex items-start gap-[0.75rem]">
                      <Checkbox
                        checked={selectedRules.includes(rule.id)}
                        className="AntCheckbox mt-[2px] pointer-events-none"
                      />
                      <div className="flex-1">
                        <Text_14_400_EEEEEE className="mb-[0.25rem]">
                          {rule.name}
                        </Text_14_400_EEEEEE>
                        <Text_12_400_757575>
                          {rule.description}
                        </Text_12_400_757575>
                      </div>
                    </div>
                  </div>
                ))}

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
