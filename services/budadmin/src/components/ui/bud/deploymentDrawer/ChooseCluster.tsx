import React, { useEffect, useState } from "react";

import {
  Text_14_400_EEEEEE,
  Text_12_400_757575,
  Text_12_600_EEEEEE,
} from "../../text";

import { Input } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { useCluster } from "src/hooks/useCluster";
import { useDeployModel } from "src/stores/useDeployModel";
import BudStepAlert from "src/flows/components/BudStepAlert";
import ClusterList from "src/flows/components/ClusterList";

const ChooseCluster: React.FC<{
  onClusterSelected?: (cluster: any) => void;
  hidePerformance?: boolean;
  hideRank?: boolean;
}> = (props) => {
  const [search, setSearch] = useState<string>("");
  const { deploymentCluster, setDeploymentCluster } = useDeployModel();
  const { recommendedCluster, getRecommendedClusterById, currentProcessId } =
    useCluster();
  const [openDetails, setOpenDetails] = useState<number | null>(null); // State to track which cluster's detail is open
  const toggleDetail = (index: number) => {
    setOpenDetails(openDetails === index ? null : index);
  };

  useEffect(() => {
    if (currentProcessId !== "") {
      getRecommendedClusterById(currentProcessId);
    }
  }, [currentProcessId]);

  const filteredClusters = recommendedCluster?.clusters?.filter((cluster) =>
    cluster.name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="flex flex-col	justify-start items-center w-full">
      <div className="w-full p-[1.35rem] pb-[1.1rem] border-b border-[#1F1F1F]">
        <Text_14_400_EEEEEE>Choose a Cluster</Text_14_400_EEEEEE>
        <Text_12_400_757575 className="mt-[.7rem]">
          Clusters are listed in best fit order. Select suitable cluster from
          the list
        </Text_12_400_757575>
      </div>
      <div className="p-[1.35rem] pt[1.05rem] w-full">
        <div className="w-full">
          <Input
            placeholder="Search Clusters"
            prefix={
              <SearchOutlined style={{ color: "#757575", marginRight: 8 }} />
            }
            style={{
              backgroundColor: "transparent",
              color: "#EEEEEE", // Text color
            }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="custom-search bg-transparent text-[#EEEEEE] font-[400] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full"
          />
        </div>
        <div className="flex justify-start items-center mt-4">
          <Text_12_400_757575 className="mr-[.3rem] ">
            Clusters Available
          </Text_12_400_757575>
          <Text_12_600_EEEEEE>
            {recommendedCluster?.clusters?.length}
          </Text_12_600_EEEEEE>
        </div>
      </div>
      <div className="clusterCardWrap w-full ">
        <div className="clusterCard w-full">
          {recommendedCluster?.clusters?.length > 0 ? (
            <ClusterList
              clusters={filteredClusters}
              handleClusterSelection={(cluster) => {
                if (cluster.id === deploymentCluster?.id) {
                  return setDeploymentCluster(null);
                }
                setDeploymentCluster(cluster);
                props.onClusterSelected?.(cluster);
              }}
              hidePerformance={props.hidePerformance}
              hideRank={props.hideRank}
              selectedCluster={deploymentCluster}
            />
          ) : (
            <>
              <div className="mt-[1.5rem]" />
              <BudStepAlert
                type="warning"
                title="Cluster Not Found? Let’s Tweak Things!"
                description='"Oops! It seems we couldn’t find any clusters that match your deployment settings. Try going BACK and tweaking a few things like concurrent requests, context length, tokens per second, or time to first token. Let’s get this deployment on the road!"'
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChooseCluster;
