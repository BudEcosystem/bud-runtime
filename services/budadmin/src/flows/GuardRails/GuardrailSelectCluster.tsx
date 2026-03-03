import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Input, Spin } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import React, { useEffect, useMemo, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import useGuardrails from "src/hooks/useGuardrails";
import { errorToast } from "@/components/toast";
import {
  Text_14_400_EEEEEE,
  Text_12_400_757575,
  Text_12_600_EEEEEE,
} from "@/components/ui/text";
import BudStepAlert from "src/flows/components/BudStepAlert";
import GuardrailClusterList from "./GuardrailClusterList";

export default function GuardrailSelectCluster() {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const {
    recommendedClusters,
    selectedCluster,
    setSelectedCluster,
    updateWorkflow,
    workflowLoading,
    getWorkflow,
    currentWorkflow,
  } = useGuardrails();

  const [localSelected, setLocalSelected] = useState<string | null>(
    selectedCluster?.cluster_id || null
  );
  const [fetchingClusters, setFetchingClusters] = useState(true);
  const [search, setSearch] = useState<string>("");

  // Fetch the latest workflow data on mount to get recommended_clusters
  useEffect(() => {
    const fetchWorkflowData = async () => {
      setFetchingClusters(true);
      await getWorkflow(currentWorkflow?.workflow_id);
      setFetchingClusters(false);
    };
    fetchWorkflowData();
  }, []);

  const hasClusters = recommendedClusters.length > 0;

  const filteredClusters = useMemo(
    () =>
      recommendedClusters.filter((cluster: any) => {
        const name = (cluster.name || cluster.cluster_name || "").toLowerCase();
        return name.includes(search.toLowerCase());
      }),
    [recommendedClusters, search]
  );

  const handleBack = () => {
    openDrawerWithStep("guardrail-deploy-specs");
  };

  const handleNext = async () => {
    const cluster = recommendedClusters.find(
      (c: any) => (c.cluster_id || c.id) === localSelected
    );

    if (!cluster) {
      errorToast("Please select a cluster");
      return;
    }

    setSelectedCluster(cluster);

    const success = await updateWorkflow({
      step_number: 10,
      cluster_id: cluster.cluster_id || cluster.id,
      trigger_workflow: true,
    });

    if (success) {
      openDrawerWithStep("guardrail-deployment-status");
    }
  };

  const handleClusterSelect = (cluster: any) => {
    const id = cluster.cluster_id || cluster.id;
    if (id === localSelected) {
      setLocalSelected(null);
      return;
    }
    setLocalSelected(id);
  };

  return (
    <BudForm
      data={{}}
      onBack={fetchingClusters ? undefined : hasClusters ? handleBack : closeDrawer}
      onNext={hasClusters ? handleNext : undefined}
      backText={hasClusters ? "Back" : "Close"}
      showBack={!fetchingClusters}
      nextText="Deploy"
      disableNext={!localSelected || workflowLoading || fetchingClusters}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex flex-col justify-start items-center w-full">
            <div className="w-full p-[1.35rem] pb-[1.1rem] border-b border-[#1F1F1F]">
              <Text_14_400_EEEEEE>Select Cluster</Text_14_400_EEEEEE>
              <Text_12_400_757575 className="mt-[.7rem]">
                {hasClusters || fetchingClusters
                  ? "Clusters are listed in best fit order. Select a suitable cluster for deploying the guardrail models."
                  : "No cluster recommendations were found from the simulation."}
              </Text_12_400_757575>
            </div>

            {fetchingClusters ? (
              <div className="flex items-center justify-center py-[4rem] w-full">
                <Spin />
              </div>
            ) : hasClusters ? (
              <>
                <div className="p-[1.35rem] pt-[1.05rem] w-full">
                  <div className="w-full">
                    <Input
                      placeholder="Search Clusters"
                      prefix={
                        <SearchOutlined style={{ color: "#757575", marginRight: 8 }} />
                      }
                      style={{
                        backgroundColor: "transparent",
                        color: "#EEEEEE",
                      }}
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      className="custom-search bg-transparent text-[#EEEEEE] font-[400] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full"
                    />
                  </div>
                  <div className="flex justify-start items-center mt-4">
                    <Text_12_400_757575 className="mr-[.3rem]">
                      Clusters Available
                    </Text_12_400_757575>
                    <Text_12_600_EEEEEE>
                      {recommendedClusters.length}
                    </Text_12_600_EEEEEE>
                  </div>
                </div>
                <div className="clusterCardWrap w-full">
                  <div className="clusterCard w-full">
                    <GuardrailClusterList
                      clusters={filteredClusters}
                      handleClusterSelection={handleClusterSelect}
                      selectedClusterId={localSelected}
                    />
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="mt-[1.5rem]" />
                <BudStepAlert
                  type="warning"
                  title="No Clusters Found"
                  description="No cluster recommendations available. Please try running the simulation again with different specifications."
                />
              </>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
