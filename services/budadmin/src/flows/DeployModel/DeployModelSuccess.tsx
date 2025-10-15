import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSpecificationInfo from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import BudStepAlert from "../components/BudStepAlert";
import { useRouter } from "next/router";
import { useProjects } from "src/hooks/useProjects";
import { useEndPoints } from "src/hooks/useEndPoint";

export default function DeployModelSuccess() {
  const {
    currentWorkflow,
    updateCredentials,
    selectedCredentials,
    selectedModel,
    deploymentCluster,
    getWorkflow,
    getWorkflowCloud,
  } = useDeployModel();
  const { getEndPoints } = useEndPoints();
  const [searchValue, setSearchValue] = useState("");
  const [order, setOrder] = useState<"-" | "">("");
  const [orderBy, setOrderBy] = useState<string>("created_at");
  const { selectedProject, getProject } = useProjects();
  const { openDrawer, closeDrawer } = useDrawer();
  const router = useRouter();
  const { projectId } = router.query;
  const page = 1;
  const limit = 1000;
  const getData = async () => {
    await getProject(projectId as string);
    await getEndPoints({
      id: projectId,
      page: page,
      limit: limit,
      name: searchValue,
      order_by: `${order}${orderBy}`,
    });
  };

  useEffect(() => {
    if (currentWorkflow.workflow_steps.model.provider_type === "cloud_model") {
      getWorkflowCloud();
    } else {
      getWorkflow();
    }
  }, []);

  return (
    <BudForm
      data={{}}
      nextText="View Deployment"
      onNext={() => {
        getData();
        router.push(`/projects/${selectedProject?.id}`);
        closeDrawer();
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <BudStepAlert
            type="success"
            title="Deployment successful"
            description={`${selectedModel?.name} has been successfully deployed on ${deploymentCluster?.name}. You can starting using the deployed model for your project.`}
          />
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DeployModelSpecificationInfo />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
