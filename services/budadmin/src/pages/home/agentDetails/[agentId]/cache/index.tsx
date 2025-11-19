import React from "react";
import { Switch, Button, InputNumber } from "antd";
import {
  Text_14_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_600_EEEEEE,
} from "@/components/ui/text";

interface CacheStatistics {
  hitRate: number;
  totalHits: number;
  totalMisses: number;
}

interface CacheConfiguration {
  enabled: boolean;
  ttl: number;
}

interface AgentCacheData {
  cache?: CacheConfiguration;
  statistics?: CacheStatistics;
}

interface CacheTabProps {
  agentData?: AgentCacheData;
  onSave?: (config: CacheConfiguration) => void | Promise<void>;
}

const CacheTab: React.FC<CacheTabProps> = ({ agentData, onSave }) => {
  // Initialize state from agentData with fallback to defaults
  const [cacheEnabled, setCacheEnabled] = React.useState(
    agentData?.cache?.enabled ?? true
  );
  const [cacheTTL, setCacheTTL] = React.useState(
    agentData?.cache?.ttl ?? 3600
  );
  const [isSaving, setIsSaving] = React.useState(false);

  // Sync state when agentData changes
  React.useEffect(() => {
    if (agentData?.cache) {
      setCacheEnabled(agentData.cache.enabled ?? true);
      setCacheTTL(agentData.cache.ttl ?? 3600);
    }
  }, [agentData]);

  // Extract statistics from agentData with fallback to placeholder values
  const statistics: CacheStatistics = {
    hitRate: agentData?.statistics?.hitRate ?? 78.5,
    totalHits: agentData?.statistics?.totalHits ?? 1247,
    totalMisses: agentData?.statistics?.totalMisses ?? 342,
  };

  // Handle save changes
  const handleSaveChanges = async () => {
    if (!onSave) {
      console.warn("No onSave handler provided to CacheTab");
      return;
    }

    setIsSaving(true);
    try {
      const config: CacheConfiguration = {
        enabled: cacheEnabled,
        ttl: cacheTTL,
      };
      await onSave(config);
    } catch (error) {
      console.error("Error saving cache configuration:", error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="mt-[1rem] pb-8">
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
                <div className="text-[1.5rem] font-semibold text-[#22C55E]">
                  {statistics.hitRate.toFixed(1)}%
                </div>
              </div>
              <div className="bg-[#1A1A1A] border border-[#2F2F2F] rounded p-4">
                <Text_12_400_B3B3B3 className="block mb-2">Total Hits</Text_12_400_B3B3B3>
                <div className="text-[1.5rem] font-semibold text-[#3B82F6]">
                  {statistics.totalHits.toLocaleString()}
                </div>
              </div>
              <div className="bg-[#1A1A1A] border border-[#2F2F2F] rounded p-4">
                <Text_12_400_B3B3B3 className="block mb-2">Total Misses</Text_12_400_B3B3B3>
                <div className="text-[1.5rem] font-semibold text-[#EF4444]">
                  {statistics.totalMisses.toLocaleString()}
                </div>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end pt-4">
            <Button
              type="primary"
              onClick={handleSaveChanges}
              loading={isSaving}
              disabled={!onSave}
            >
              Save Changes
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CacheTab;
export type { CacheStatistics, CacheConfiguration, AgentCacheData, CacheTabProps };
