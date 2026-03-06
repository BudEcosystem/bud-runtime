/**
 * SelectCluster - Step 3 of the Deploy Use Case wizard
 *
 * Displays available clusters for selection using the same UI pattern
 * as the deploy model cluster selection (ChooseCluster).
 */

import React, { useEffect, useState } from "react";
import { Checkbox, Input } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_10_400_B3B3B3,
  Text_12_400_757575,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import IconRender from "src/flows/components/BudIconRender";
import { useUseCases } from "src/stores/useUseCases";
import { useCluster, Cluster } from "src/hooks/useCluster";
import { useDrawer } from "src/hooks/useDrawer";

function ClusterRow({
  cluster,
  selected,
  onClick,
}: {
  cluster: Cluster;
  selected: boolean;
  onClick: () => void;
}) {
  const [hover, setHover] = useState(false);
  const gpuCount = cluster.gpu_count || cluster.gpu_total_workers || 0;
  const cpuCount = cluster.cpu_count || cluster.cpu_total_workers || 0;

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onClick}
      className={`py-[1.1rem] cursor-pointer px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex border-box hover:bg-[#FFFFFF03] hover:shadow-lg ${
        selected ? "bg-[#965CDE10] border-l-2 border-l-[#965CDE]" : ""
      }`}
    >
      <div className="mr-[.7rem] shrink-0 grow-0">
        <IconRender icon={cluster.icon} size={28} imageSize={18} />
      </div>
      <div className="flex justify-between w-full flex-col">
        <div className="flex items-center justify-between h-4">
          <div className="flex items-center gap-2">
            <Text_14_400_EEEEEE className="leading-[150%]">
              {cluster.name}
            </Text_14_400_EEEEEE>
            {cluster.status && (
              <span
                className="text-[0.525rem] font-[400] rounded-[6px] px-[.3rem] py-[.1rem]"
                style={{
                  backgroundColor: cluster.status.toLowerCase() === "active" ? "#14581340" : "#86541A33",
                  color: cluster.status.toLowerCase() === "active" ? "#3EC564" : "#ECAE75",
                }}
              >
                {cluster.status}
              </span>
            )}
          </div>
          <div style={{ display: hover || selected ? "flex" : "none" }}>
            <Checkbox
              checked={selected}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] mt-[.85rem]"
            />
          </div>
        </div>
        <Text_10_400_B3B3B3 className="overflow-hidden line-clamp-1 leading-[170%]">
          {gpuCount > 0 ? `${gpuCount} GPU` : ""}{gpuCount > 0 && cpuCount > 0 ? " · " : ""}{cpuCount > 0 ? `${cpuCount} CPU` : ""}{!gpuCount && !cpuCount ? "No resource info" : ""}
          {cluster.type ? ` · ${cluster.type}` : ""}
        </Text_10_400_B3B3B3>
      </div>
    </div>
  );
}

export default function SelectCluster() {
  const { selectedClusterId, setSelectedCluster } = useUseCases();
  const { clusters, getClusters } = useCluster();
  const { openDrawerWithStep } = useDrawer();
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!clusters || clusters.length === 0) {
      getClusters({ page: 1, limit: 50 });
    }
  }, []);

  const filteredClusters = clusters?.filter((c: Cluster) =>
    c.name?.toLowerCase().includes(search.toLowerCase())
  ) || [];

  return (
    <BudForm
      data={{}}
      onBack={() => openDrawerWithStep("deploy-usecase-name")}
      backText="Back"
      nextText="Next"
      disableNext={!selectedClusterId}
      onNext={() => openDrawerWithStep("deploy-usecase-configure")}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex flex-col justify-start items-center w-full">
            <div className="w-full p-[1.35rem] pb-[1.1rem] border-b border-[#1F1F1F]">
              <Text_14_400_EEEEEE>Choose a Cluster</Text_14_400_EEEEEE>
              <Text_12_400_757575 className="mt-[.7rem]">
                Select the cluster where the use case will be deployed.
              </Text_12_400_757575>
            </div>
            <div className="p-[1.35rem] pt-[1.05rem] w-full">
              <div className="w-full">
                <Input
                  placeholder="Search Clusters"
                  prefix={<SearchOutlined style={{ color: "#757575", marginRight: 8 }} />}
                  style={{ backgroundColor: "transparent", color: "#EEEEEE" }}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="custom-search bg-transparent text-[#EEEEEE] font-[400] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full"
                />
              </div>
              <div className="flex justify-start items-center mt-4">
                <Text_12_400_757575 className="mr-[.3rem]">
                  Clusters Available
                </Text_12_400_757575>
                <Text_12_600_EEEEEE>{filteredClusters.length}</Text_12_600_EEEEEE>
              </div>
            </div>
            <div className="w-full">
              {filteredClusters.length > 0 ? (
                filteredClusters.map((cluster: Cluster) => {
                  const clusterId = cluster.cluster_id || cluster.id;
                  return (
                    <ClusterRow
                      key={clusterId}
                      cluster={cluster}
                      selected={selectedClusterId === clusterId}
                      onClick={() => {
                        if (selectedClusterId === clusterId) {
                          setSelectedCluster(null);
                        } else {
                          setSelectedCluster(clusterId);
                        }
                      }}
                    />
                  );
                })
              ) : (
                <div className="py-8 text-center">
                  <Text_10_400_B3B3B3>
                    {search ? `No clusters found for "${search}"` : "No clusters available."}
                  </Text_10_400_B3B3B3>
                </div>
              )}
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
