import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import {
  Text_12_400_B3B3B3,
  Text_13_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_17_600_FFFFFF,
  Text_11_400_808080,
} from "@/components/ui/text";
import React, { useEffect } from "react";
import { Spin } from "antd";
import { useVirtualServers } from "src/stores/useVirtualServers";
import { formatDate } from "src/utils/formatDate";

interface Tool {
  id: string;
  name: string;
  displayName?: string;
  description?: string;
  integrationType?: string;
  requestType?: string;
}

export default function ViewVirtualServerDetails() {
  const {
    selectedVirtualServer,
    virtualServerDetail,
    isLoadingDetail,
    getVirtualServerById,
  } = useVirtualServers();

  useEffect(() => {
    if (selectedVirtualServer?.id) {
      getVirtualServerById(selectedVirtualServer.id);
    }
  }, [selectedVirtualServer?.id]);

  const tools: Tool[] = virtualServerDetail?.tools || [];

  return (
    <BudWraperBox>
      <BudDrawerLayout>
        {/* Header Section */}
        <div className="flex items-start justify-between w-full p-[1.35rem] border-b border-[#1F1F1F]">
          <div className="flex items-start justify-start max-w-[90%]">
            <div className="p-[.6rem] w-[2.8rem] h-[2.8rem] bg-[#1F1F1F] rounded-[6px] mr-[1.05rem] shrink-0 grow-0 flex items-center justify-center">
              <div className="w-[1.75rem] h-[1.75rem] text-[1.5rem] flex items-center justify-center">
                {"🖥️"}
              </div>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-[0.4rem]">
                <Text_14_400_EEEEEE className="leading-[140%]">
                  {selectedVirtualServer?.name || "Virtual Server"}
                </Text_14_400_EEEEEE>
                <span
                  className={`px-2 py-0.5 text-[0.625rem] rounded ${
                    selectedVirtualServer?.visibility === "public"
                      ? "bg-[#22C55E]/20 text-[#22C55E]"
                      : "bg-[#F59E0B]/20 text-[#F59E0B]"
                  }`}
                >
                  {selectedVirtualServer?.visibility || "public"}
                </span>
              </div>
              {selectedVirtualServer?.created_at && (
                <Text_11_400_808080 className="mb-[0.4rem]">
                  Created: {formatDate(selectedVirtualServer.created_at)}
                </Text_11_400_808080>
              )}
              {selectedVirtualServer?.description && (
                <Text_13_400_B3B3B3 className="leading-[150%]">
                  {selectedVirtualServer.description}
                </Text_13_400_B3B3B3>
              )}
            </div>
          </div>
        </div>

        {/* Tools Section */}
        <div className="p-[1.35rem]">
          <div className="flex items-center justify-between mb-[1rem]">
            <Text_17_600_FFFFFF>
              Tools ({isLoadingDetail ? "..." : tools.length})
            </Text_17_600_FFFFFF>
          </div>

          {/* Loading State */}
          {isLoadingDetail && (
            <div className="flex items-center justify-center py-8">
              <Spin size="default" />
              <Text_13_400_B3B3B3 className="ml-3">
                Loading tools...
              </Text_13_400_B3B3B3>
            </div>
          )}

          {/* Empty State */}
          {!isLoadingDetail && tools.length === 0 && (
            <div className="flex items-center justify-center py-8">
              <Text_13_400_B3B3B3>
                No tools in this virtual server
              </Text_13_400_B3B3B3>
            </div>
          )}

          {/* Tools List */}
          {!isLoadingDetail && tools.length > 0 && (
            <div className="max-h-[500px] overflow-y-auto">
              {tools.map((tool) => (
                <div
                  key={tool.id}
                  className="flex items-start gap-[0.75rem] py-[1rem] border-b border-[#1F1F1F] px-[0.25rem] -mx-[0.25rem] rounded"
                >
                  <div className="p-[.4rem] w-[2rem] h-[2rem] bg-[#1F1F1F] rounded-[4px] shrink-0 flex items-center justify-center">
                    <div className="text-[1rem]">{"🔧"}</div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-[0.25rem]">
                      <Text_14_400_EEEEEE className="truncate">
                        {tool.displayName || tool.name}
                      </Text_14_400_EEEEEE>
                      {tool.requestType && (
                        <span className="px-1.5 py-0.5 text-[0.5625rem] rounded bg-[#3B82F6]/20 text-[#3B82F6] uppercase shrink-0">
                          {tool.requestType}
                        </span>
                      )}
                    </div>
                    {tool.description && (
                      <Text_12_400_B3B3B3 className="leading-[150%] line-clamp-2">
                        {tool.description}
                      </Text_12_400_B3B3B3>
                    )}
                    {tool.integrationType && (
                      <Text_11_400_808080 className="mt-[0.25rem]">
                        Type: {tool.integrationType}
                      </Text_11_400_808080>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </BudDrawerLayout>
    </BudWraperBox>
  );
}
