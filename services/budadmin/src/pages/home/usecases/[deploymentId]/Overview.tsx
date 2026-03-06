import React, { useEffect, useState } from "react";
import { Tag, Segmented } from "antd";
import {
  Deployment,
} from "@/lib/budusecases";
import {
  Text_11_400_808080,
  Text_12_400_EEEEEE,
  Text_13_400_757575,
  Text_19_600_EEEEEE,
  Text_16_400_757575,
} from "@/components/ui/text";
import { formatDate } from "src/utils/formatDate";
import { useCluster } from "src/hooks/useCluster";
import NoChartData from "@/components/ui/noChartData";

// ---------------------------------------------------------------------------
// Analytics placeholder card
// ---------------------------------------------------------------------------

const AnalyticsPlaceholderCard = ({ title }: { title: string }) => (
  <div className="bg-[#101010] p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] flex-1 min-w-0 h-[23.664375rem] flex items-center justify-between flex-col">
    <div className="flex items-center justify-start w-full flex-col">
      <div className="flex items-start justify-start flex-row w-full">
        <div className="flex items-center justify-start w-full flex-col">
          <Text_19_600_EEEEEE className="mb-[.2rem] w-full">
            {title}
          </Text_19_600_EEEEEE>
          <Text_13_400_757575 className="w-full">Over time</Text_13_400_757575>
        </div>
        <div className="flex items-start justify-end w-full mt-[0.1rem]">
          <Segmented
            options={["24hrs", "7d", "30d"]}
            disabled
            className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
          />
        </div>
      </div>
    </div>
    <NoChartData image="/images/dashboard/noData.png" classNames="w-full" classNamesInner="w-full" classNamesInnerTwo="w-full" />
  </div>
);

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const GeneralTab = ({ deployment }: { deployment?: Deployment }) => {
  const { clusters, getClusters } = useCluster();
  const [clusterName, setClusterName] = useState<string>("-");

  const uiEnabled = deployment?.access_config?.ui?.enabled === true;
  const apiEnabled = deployment?.access_config?.api?.enabled === true;

  useEffect(() => {
    if (!clusters || clusters.length === 0) {
      getClusters({ page: 1, limit: 50 });
    }
  }, []);

  useEffect(() => {
    if (clusters && deployment?.cluster_id) {
      const match = clusters.find((c: any) => c.id === deployment.cluster_id || c.cluster_id === deployment.cluster_id);
      if (match) setClusterName(match.name);
    }
  }, [clusters, deployment?.cluster_id]);

  if (!deployment) return null;

  return (
    <div className="mt-[1.1rem] pl-[.15rem] relative">
      {/* ---- Single info card with 3 columns ---- */}
      <div className="flex border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] bg-[#101010]">
        <div className="flex gap-[3rem] w-full">
          {/* Column 1 */}
          <div className="flex flex-col gap-[.75rem] flex-1">
            <div>
              <Text_11_400_808080 className="mb-[.2rem]">
                Template
              </Text_11_400_808080>
              <Text_12_400_EEEEEE>
                {deployment.template_name ?? "-"}
              </Text_12_400_EEEEEE>
            </div>
            <div>
              <Text_11_400_808080 className="mb-[.2rem]">
                Created
              </Text_11_400_808080>
              <Text_12_400_EEEEEE>
                {deployment.created_at
                  ? formatDate(deployment.created_at)
                  : "-"}
              </Text_12_400_EEEEEE>
            </div>
          </div>

          {/* Column 2 */}
          <div className="flex flex-col gap-[.75rem] flex-1">
            <div>
              <Text_11_400_808080 className="mb-[.2rem]">
                Cluster
              </Text_11_400_808080>
              <Text_12_400_EEEEEE>
                {clusterName}
              </Text_12_400_EEEEEE>
            </div>
          </div>

          {/* Column 3 */}
          <div className="flex flex-col gap-[.75rem] flex-1">
            <div>
              <Text_11_400_808080 className="mb-[.2rem]">
                UI Access
              </Text_11_400_808080>
              <Tag
                className="border-0 rounded-[5px] px-2 py-0.5 text-[0.625rem] font-[500] leading-[100%] m-0"
                style={{
                  backgroundColor: uiEnabled ? "#52c41a20" : "#ff4d4f20",
                  color: uiEnabled ? "#52c41a" : "#ff4d4f",
                }}
              >
                {uiEnabled ? "Enabled" : "Disabled"}
              </Tag>
            </div>
            <div>
              <Text_11_400_808080 className="mb-[.2rem]">
                API Access
              </Text_11_400_808080>
              <Tag
                className="border-0 rounded-[5px] px-2 py-0.5 text-[0.625rem] font-[500] leading-[100%] m-0"
                style={{
                  backgroundColor: apiEnabled ? "#52c41a20" : "#ff4d4f20",
                  color: apiEnabled ? "#52c41a" : "#ff4d4f",
                }}
              >
                {apiEnabled ? "Enabled" : "Disabled"}
              </Tag>
            </div>
          </div>
        </div>
      </div>

      {/* ---- Deployment Analytics ---- */}
      <div className="hR mt-[1.6rem]" />
      <div className="mt-[1rem]">
        <div className="flex flex-col gap-[.75rem] p-[.25rem] px-[0rem] pb-[0]">
          <div>
            <Text_19_600_EEEEEE className="w-full mb-[.1rem] tracking-[.025rem]">
              Deployment Analytics
            </Text_19_600_EEEEEE>
            <Text_16_400_757575>
              Monitor performance metrics for this use case deployment
            </Text_16_400_757575>
          </div>

          <div className="flex gap-[.8rem]">
            <AnalyticsPlaceholderCard title="API Calls" />
            <AnalyticsPlaceholderCard title="Latency" />
          </div>
          <div className="flex gap-[.8rem]">
            <AnalyticsPlaceholderCard title="Throughput" />
            <AnalyticsPlaceholderCard title="Token Metrics" />
          </div>
        </div>
      </div>

      <div className="h-[4rem]" />
    </div>
  );
};

export default GeneralTab;
