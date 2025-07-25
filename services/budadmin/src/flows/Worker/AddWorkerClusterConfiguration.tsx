import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect } from "react";
import { Cluster, useCluster } from "src/hooks/useCluster";
import { useDrawer } from "src/hooks/useDrawer";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useDeployModel } from "src/stores/useDeployModel";
import AddWorkerInfoCard from "../components/AddWorkerInfoCard";
import ClusterList from "../components/ClusterList";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { useRouter } from "next/router";


export default function AddWorkerClusterConfiguration() {
  const [selectedCluster, setSelectedCluster] = React.useState<Cluster>();
  const { submittable, values } = useContext(BudFormContext);
  const [formData, setFormData] = React.useState<FormData>(new FormData());
  const { createClusterWorkflow } = useCluster();
  const { openDrawerWithStep } = useDrawer();

  const { getWorkflow, workerDetails, completeCreateWorkerFlow } = useDeployModel();
  const { currentWorkflow } = useDeployModel();
  const { getRecommendedClusterById, recommendedCluster } = useCluster();
  const router = useRouter();
  const projectId = router.query.projectId as string;

  useEffect(() => {
    if (currentWorkflow?.workflow_id) {
      getRecommendedClusterById(currentWorkflow?.workflow_id)
    }
  }, [currentWorkflow?.workflow_id])


  return (
    <BudForm
      data={{
        additonal_concurrency: 0,
        ...workerDetails,
      }}
      disableNext={recommendedCluster?.clusters?.length === 0}
      onNext={async (values) => {
        const result = await completeCreateWorkerFlow(currentWorkflow?.workflow_id, projectId);
        if (result) {
          openDrawerWithStep("add-worker-deploy-status");
        }
        // add to form data
        // const result = await createClusterWorkflow(formData);
        // if (result) {
        //   await getWorkflow(result.workflow_id);
        //   openDrawerWithStep("create-cluster-status");
        // } else {
        //   errorToast("Error creating cluster");
        // }

      }}
    >
      <BudWraperBox classNames="mt-[1.6rem]">
        <AddWorkerInfoCard />
        <BudDrawerLayout>
          <DrawerTitleCard title="Cluster Configuration" description="Best configuration is generated based on the required concurrency" />
          <div className="clusterCardWrap w-full ">
            <div className="clusterCard w-full">
              <ClusterList clusters={recommendedCluster?.clusters} handleClusterSelection={(cluster) => { }} selectedCluster={selectedCluster} hideRank hideSelection />
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
