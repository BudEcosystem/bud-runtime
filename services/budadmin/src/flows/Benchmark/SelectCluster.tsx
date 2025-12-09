import React, { useEffect, useState } from "react";

import { Input } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { useCluster } from "src/hooks/useCluster";
import { useDeployModel } from "src/stores/useDeployModel";
import BudStepAlert from "src/flows/components/BudStepAlert";
import {
  Text_14_400_EEEEEE,
  Text_12_400_757575,
  Text_12_600_EEEEEE,
} from "@/components/ui/text";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import ClusterList from "../components/AvailableClusterList";
import { useDrawer } from "src/hooks/useDrawer";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";

const SelectCluster: React.FC = (props: {}) => {
  const list = {
    clusters: [
      {
        id: "4d945f5b-a63b-4d36-b2ce-b5790c1e1c24",
        cluster_id: "fe60be3f-8223-450e-a27a-b8a0b8ace1bd",
        name: "Dev Cluster",
        cost_per_token: 0.270178787700196,
        total_resources: 1,
        resources_used: 0,
        resource_details: [
          {
            type: "CPU",
            available: 1,
            total: 1,
          },
        ],
        required_devices: [
          {
            device_type: "cpu",
            num_replicas: 1,
            concurrency: 100,
            cost_per_million_tokens: 0.270178787700196,
          },
        ],
        benchmarks: {
          replicas: 1,
          concurrency: {
            label: "Better",
            value: 100,
          },
          ttft: null,
          e2e_latency: null,
          per_session_tokens_per_sec: null,
          over_all_throughput: null,
        },
      },
      {
        id: "c8babaf4-ddc4-4361-bdee-cb8e492852e1",
        cluster_id: "a12a48ac-22ef-4161-9581-629116b105e4",
        name: "SPR",
        cost_per_token: 0.4590258467128041,
        total_resources: 16,
        resources_used: 0,
        resource_details: [
          {
            type: "CPU",
            available: 16,
            total: 16,
          },
        ],
        required_devices: [
          {
            device_type: "cpu",
            num_replicas: 1,
            concurrency: 100,
            cost_per_million_tokens: 0.4590258467128041,
          },
        ],
        benchmarks: {
          replicas: 1,
          concurrency: {
            label: "Better",
            value: 100,
          },
          ttft: null,
          e2e_latency: null,
          per_session_tokens_per_sec: null,
          over_all_throughput: null,
        },
      },
    ],
    status: "success",
    workflow_id: "4e8e755e-395c-4d9e-b453-714bb7927526",
  };
  const {
    currentWorkflow,
    currentWorkflowId,
    stepThree,
    setSelectedCluster,
    selectedCluster,
    evalWith,
  } = usePerfomanceBenchmark();

  const { openDrawerWithStep, openDrawer, setPreviousStep, currentFlow, step } =
    useDrawer();
  const [search, setSearch] = useState<string>("");
  const { clusters, getClusters } = useCluster();
  const [openDetails, setOpenDetails] = useState<number | null>(null); // State to track which cluster's detail is open
  const toggleDetail = (index: number) => {
    setOpenDetails(openDetails === index ? null : index);
  };

  useEffect(() => {
    getClusters({ page: 1, limit: 1000 });
  }, []);

  useEffect(() => {
    console.log("selectedCluster", selectedCluster);
  }, [selectedCluster]);

  // const filteredClusters = clusters?.filter((cluster) => cluster.name.toLowerCase().includes(search.toLowerCase()));
  const filteredClusters = clusters?.filter(
    (cluster) =>
      cluster.name.toLowerCase().includes(search.toLowerCase()) &&
      cluster.status == "available",
  );

  // const filteredClusters = recommendedCluster?.clusters?.filter((cluster) => cluster.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <BudForm
      data={{}}
      backText="Back"
      nextText="Next"
      onBack={() => {
        if (evalWith == "dataset") {
          openDrawerWithStep("add-Datasets");
        } else if (evalWith == "configuration") {
          openDrawerWithStep("add-Configuration");
        }
      }}
      onNext={() => {
        stepThree().then((result) => {
          if (result) {
            openDrawerWithStep("Select-Hardware-Mode");
          }
        });
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Cluster"
            description="Pick the cluster you want to perform the benchmark"
            descriptionClass="pt-[.3rem]"
            classNames="pt-[.8rem] pb-[.9rem]"
          />
          <div className="flex flex-col	justify-start items-center w-full">
            {/* <div className="w-full p-[1.35rem] pb-[1.1rem] border-b border-[#1F1F1F]">
              <Text_14_400_EEEEEE>Select Cluster</Text_14_400_EEEEEE>
              <Text_12_400_757575 className="mt-[.7rem]">Description</Text_12_400_757575>
            </div> */}
            <div className="p-[1.35rem] pt-[1.05rem] pb-[.7rem] w-full">
              <div className="w-full">
                <Input
                  placeholder="Search"
                  prefix={
                    <SearchOutlined
                      style={{ color: "#757575", marginRight: 8 }}
                    />
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
              <div className="flex justify-start items-center mt-[1.45rem]">
                <Text_12_400_757575 className="mr-[.3rem] ">
                  Clusters Available&nbsp;
                </Text_12_400_757575>
                <Text_12_600_EEEEEE>
                  {filteredClusters.length}
                </Text_12_600_EEEEEE>
                {/* <Text_12_600_EEEEEE>{recommendedCluster?.clusters?.length}</Text_12_600_EEEEEE> */}
              </div>
            </div>
            <div className="clusterCardWrap w-full ">
              <div className="clusterCard w-full mt-[0rem]">
                {/* {recommendedCluster?.clusters?.length > 0 ? */}
                {list?.clusters?.length > 0 ? (
                  <ClusterList
                    clusters={filteredClusters}
                    handleClusterSelection={(cluster) => {
                      setSelectedCluster(cluster);
                    }}
                    selectedCluster={selectedCluster}
                  />
                ) : (
                  <>
                    <div className="mt-[1.5rem]" />
                    <BudStepAlert
                      type="warining"
                      title="Cluster Not Found? Let’s Tweak Things!"
                      description='"Oops! It seems we couldn’t find any clusters that match your deployment settings. Try going BACK and tweaking a few things like concurrent requests, context length, tokens per second, or time to first token. Let’s get this deployment on the road!"'
                    />
                  </>
                )}
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

export default SelectCluster;
