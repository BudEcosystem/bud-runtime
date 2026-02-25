import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import useGuardrails from "src/hooks/useGuardrails";
import { AppRequest } from "src/pages/api/requests";
import { formatDate } from "src/utils/formatDate";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";
import { Spin, Tag } from "antd";

interface ProbeDetailsProps {
  probeName?: string;
  probeData?: {
    name: string;
    description: string;
    modality: string[];
    scannerType: string;
    guardType: string[];
    provider_name?: string | null;
    rule_count?: number;
    is_custom?: boolean;
    examples?: Array<{
      id: string;
      title: string;
      content: string;
    }>;
  };
}

interface ProbeDetailResponse {
  id: string;
  name: string;
  description: string;
  tags: Array<{ name: string; color: string }>;
  provider_id: string;
  provider_type: string;
  provider: {
    id: string;
    name: string;
    description: string;
    type: string;
    icon: string;
    is_active: boolean;
    configuration_schema?: any;
    object: string;
  };
  is_custom: boolean;
  created_by?: string;
  user_id?: string;
  project_id?: string;
  created_at: string;
  modified_at: string;
  rules?: any[];
  object: string;
}

export default function ProbeDetails({ probeData }: ProbeDetailsProps) {
  const { isExpandedViewOpen } = useContext(BudFormContext);
  const { closeExpandedStep, closeDrawer } = useDrawer();
  const { selectedProbe, clearSelectedProbe } = useGuardrails();
  const [loading, setLoading] = useState(false);
  const [probeDetails, setProbeDetails] = useState<ProbeDetailResponse | null>(
    null,
  );

  // Fetch probe details when component mounts
  useEffect(() => {
    if (selectedProbe?.id) {
      fetchProbeDetails(selectedProbe.id);
    }
  }, [selectedProbe?.id]);

  const fetchProbeDetails = async (probeId: string) => {
    setLoading(true);
    try {
      const response = await AppRequest.Get(`/guardrails/probe/${probeId}`, {
        params: { include_rules: false },
      });
      if (response.data) {
        setProbeDetails(response.data.probe || response.data);
      }
    } catch (error) {
      console.error("Failed to fetch probe details:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Clear selected probe when drawer closes
    return () => {
      clearSelectedProbe();
      setProbeDetails(null);
    };
  }, [clearSelectedProbe]);

  // Also clear when expanded view closes
  useEffect(() => {
    if (!isExpandedViewOpen && selectedProbe) {
      clearSelectedProbe();
      setProbeDetails(null);
    }
  }, [isExpandedViewOpen, selectedProbe, clearSelectedProbe]);

  // Use fetched probe details if available, otherwise use selectedProbe or default
  const data = probeDetails
    ? {
        name: probeDetails.name,
        description: probeDetails.description,
        tags: probeDetails.tags || [],
        provider: probeDetails.provider,
        provider_type: probeDetails.provider_type,
        is_custom: probeDetails.is_custom,
        created_at: probeDetails.created_at,
        modified_at: probeDetails.modified_at,
        rules: probeDetails.rules || [],
      }
    : selectedProbe
      ? {
          name: selectedProbe.name,
          description: selectedProbe.description,
          tags: selectedProbe.tags || [],
          provider: null,
          provider_type: selectedProbe.provider_type,
          is_custom: selectedProbe.is_custom,
          created_at: null,
          modified_at: null,
          rules: [],
        }
      : {
          name: "Loading...",
          description: "Loading probe details...",
          tags: [],
          provider: null,
          provider_type: "",
          is_custom: false,
          created_at: null,
          modified_at: null,
          rules: [],
        };

  const handleClose = () => {
    // Clear the selected probe data when closing
    clearSelectedProbe();

    if (isExpandedViewOpen) {
      closeExpandedStep();
    } else {
      closeDrawer();
    }
  };

  return (
    <BudForm data={{}} onNext={handleClose} nextText="Close" showBack={false}>
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={data.name}
            description={data.description}
            classNames="pt-[.8rem]"
          />

          {loading ? (
            <div className="flex justify-center items-center py-[4rem]">
              <Spin size="large" />
            </div>
          ) : (
            <div className="px-[1.35rem] pb-[1.35rem]">
              {/* Tags Section */}
              {data.tags && data.tags.length > 0 && (
                <div className="mb-[1.5rem]">
                  <Text_14_600_FFFFFF className="mb-[0.75rem]">
                    Tags
                  </Text_14_600_FFFFFF>
                  <div className="flex flex-wrap gap-[0.5rem]">
                    {data.tags.map((tag, index) => (
                      <Tag
                        key={index}
                        className="text-[#EEEEEE] border-[0] rounded-[6px] px-[0.75rem] py-[0.25rem]"
                        style={{
                          backgroundColor: tag.color
                            ? tag.color + "20"
                            : "#1F1F1F",
                          color: tag.color || "#B3B3B3",
                        }}
                      >
                        {tag.name}
                      </Tag>
                    ))}
                  </div>
                </div>
              )}

              {/* Provider Section */}
              {data.provider && (
                <div className="mb-[1.5rem] p-[1rem] bg-[#1F1F1F] rounded-[8px] mt-[1.5rem]">
                  <Text_14_600_FFFFFF className="mb-[0.75rem]">
                    Provider Details
                  </Text_14_600_FFFFFF>
                  <div className="space-y-[0.5rem]">
                    <div className="flex items-center gap-[0.5rem]">
                      <Text_12_400_757575 className="min-w-[5.5rem]">Name:</Text_12_400_757575>
                      <Text_14_400_EEEEEE>
                        {data.provider.name}
                      </Text_14_400_EEEEEE>
                    </div>
                    <div className="flex items-center gap-[0.5rem]">
                      <Text_12_400_757575 className="min-w-[5.5rem]">Type:</Text_12_400_757575>
                      <Text_14_400_EEEEEE>
                        {data.provider.type}
                      </Text_14_400_EEEEEE>
                    </div>
                    {data.provider.description && (
                      <div className="flex items-start gap-[0.5rem]">
                        <Text_12_400_757575 className="min-w-[5.5rem]">Description:</Text_12_400_757575>
                        <Text_14_400_EEEEEE className="flex-1">
                          {data.provider.description}
                        </Text_14_400_EEEEEE>
                      </div>
                    )}
                    <div className="flex items-center gap-[0.5rem]">
                      <Text_12_400_757575 className="min-w-[5.5rem]">Status:</Text_12_400_757575>
                      <span
                        className={`px-[0.5rem] py-[0.125rem] rounded-[4px] text-[12px] ${
                          data.provider.is_active
                            ? "bg-[#52C41A20] text-[#52C41A]"
                            : "bg-[#75757520] text-[#757575]"
                        }`}
                      >
                        {data.provider.is_active ? "Active" : "Inactive"}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Provider Type Section */}
              <div className="mb-[1.5rem]">
                <div className="flex items-center gap-[0.5rem]">
                  <Text_14_600_FFFFFF>Provider Type:</Text_14_600_FFFFFF>
                  <Text_14_400_EEEEEE className="text-[#B3B3B3] capitalize">
                    {data.provider_type?.replace(/_/g, " ")}
                  </Text_14_400_EEEEEE>
                </div>
              </div>

              {/* Custom Badge */}
              {data.is_custom && (
                <div className="mb-[1.5rem]">
                  <span className="bg-[#965CDE20] text-[#965CDE] px-[0.75rem] py-[0.25rem] rounded-[4px] text-[12px]">
                    Custom Probe
                  </span>
                </div>
              )}

              {/* Rules Section */}
              {data.rules && data.rules.length > 0 && (
                <div className="mb-[1.5rem]">
                  <div className="flex items-center justify-between mb-[0.75rem]">
                    <Text_14_600_FFFFFF>Rules</Text_14_600_FFFFFF>
                    <Text_12_400_757575>
                      {data.rules.length} configured
                    </Text_12_400_757575>
                  </div>
                  <div className="space-y-[0.5rem]">
                    {data.rules.slice(0, 5).map((rule: any, index: number) => (
                      <div
                        key={index}
                        className="p-[0.75rem] bg-[#1F1F1F] rounded-[6px]"
                      >
                        <Text_14_400_EEEEEE>
                          {rule.name || `Rule ${index + 1}`}
                        </Text_14_400_EEEEEE>
                        {rule.description && (
                          <Text_12_400_757575 className="mt-[0.25rem]">
                            {rule.description}
                          </Text_12_400_757575>
                        )}
                      </div>
                    ))}
                    {data.rules.length > 5 && (
                      <Text_12_400_757575 className="text-center pt-[0.5rem]">
                        +{data.rules.length - 5} more rules
                      </Text_12_400_757575>
                    )}
                  </div>
                </div>
              )}

              {/* Timestamps Section */}
              {(data.created_at || data.modified_at) && (
                <div className="mt-[2rem] pt-[1rem] border-t border-[#1F1F1F]">
                  <div className="space-y-[0.5rem]">
                    {data.created_at && (
                      <div className="flex items-center gap-[0.5rem]">
                        <Text_12_400_757575>Created:</Text_12_400_757575>
                        <Text_12_400_757575>
                          {formatDate(data.created_at)}
                        </Text_12_400_757575>
                      </div>
                    )}
                    {data.modified_at && (
                      <div className="flex items-center gap-[0.5rem]">
                        <Text_12_400_757575>Last Modified:</Text_12_400_757575>
                        <Text_12_400_757575>
                          {formatDate(data.modified_at)}
                        </Text_12_400_757575>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
