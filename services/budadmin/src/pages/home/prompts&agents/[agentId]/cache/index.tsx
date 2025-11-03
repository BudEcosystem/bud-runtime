import React from "react";
import { Switch, Button, InputNumber } from "antd";
import {
  Text_14_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_600_EEEEEE,
} from "@/components/ui/text";

interface CacheTabProps {
  agentData: any;
}

const CacheTab: React.FC<CacheTabProps> = ({ agentData }) => {
  const [cacheEnabled, setCacheEnabled] = React.useState(true);
  const [cacheTTL, setCacheTTL] = React.useState(3600);

  return (
    <div className="px-[3.5rem] pb-8">
      <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
        <Text_14_600_EEEEEE className="mb-6 block">Cache Configuration</Text_14_600_EEEEEE>

        <div className="space-y-6">
          {/* Enable Cache */}
          <div className="flex justify-between items-center pb-4 border-b border-[#1F1F1F]">
            <div>
              <Text_12_600_EEEEEE className="block mb-1">Enable Cache</Text_12_600_EEEEEE>
              <Text_12_400_B3B3B3>
                Cache responses to improve performance and reduce costs
              </Text_12_400_B3B3B3>
            </div>
            <Switch checked={cacheEnabled} onChange={setCacheEnabled} />
          </div>

          {/* Cache TTL */}
          <div className="flex justify-between items-center pb-4 border-b border-[#1F1F1F]">
            <div>
              <Text_12_600_EEEEEE className="block mb-1">Cache TTL (seconds)</Text_12_600_EEEEEE>
              <Text_12_400_B3B3B3>
                How long to keep cached responses
              </Text_12_400_B3B3B3>
            </div>
            <InputNumber
              value={cacheTTL}
              onChange={(value) => setCacheTTL(value || 3600)}
              min={60}
              max={86400}
              disabled={!cacheEnabled}
            />
          </div>

          {/* Cache Statistics */}
          <div className="pt-4">
            <Text_12_600_EEEEEE className="block mb-4">Cache Statistics</Text_12_600_EEEEEE>
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-[#1A1A1A] border border-[#2F2F2F] rounded p-4">
                <Text_12_400_B3B3B3 className="block mb-2">Hit Rate</Text_12_400_B3B3B3>
                <div className="text-[1.5rem] font-semibold text-[#22C55E]">78.5%</div>
              </div>
              <div className="bg-[#1A1A1A] border border-[#2F2F2F] rounded p-4">
                <Text_12_400_B3B3B3 className="block mb-2">Total Hits</Text_12_400_B3B3B3>
                <div className="text-[1.5rem] font-semibold text-[#3B82F6]">1,247</div>
              </div>
              <div className="bg-[#1A1A1A] border border-[#2F2F2F] rounded p-4">
                <Text_12_400_B3B3B3 className="block mb-2">Total Misses</Text_12_400_B3B3B3>
                <div className="text-[1.5rem] font-semibold text-[#EF4444]">342</div>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end pt-4">
            <Button type="primary">Save Changes</Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CacheTab;
