import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import DeployModelSpecificationInfo from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import router, { useRouter } from "next/router";
import BudStepAlert from "../components/BudStepAlert";
import { useDrawer } from "src/hooks/useDrawer";
import { useProjects } from "src/hooks/useProjects";
import { useDeployModel } from "src/stores/useDeployModel";
import { useEndPoints } from "src/hooks/useEndPoint";
import { useContext, useEffect } from "react";

export const AdapterResult = () => {
  const router = useRouter();
  const { selectedProject, getProject } = useProjects();
  const { openDrawer, closeDrawer } = useDrawer();
  const { adapterWorkflow, currentWorkflow, setAdapterWorkflow } =
    useDeployModel();
  const { getAdapters } = useEndPoints();
  const { form } = useContext(BudFormContext);
  const projectId = router.query.projectId as string;
  useEffect(() => {
    if (!currentWorkflow) {
      return;
    }
    setAdapterWorkflow({
      adapterModelId:
        currentWorkflow.workflow_steps.adapter_config?.adapter_model_id,
      adapterName: currentWorkflow.workflow_steps.adapter_config?.adapter_name,
      endpointId: currentWorkflow.workflow_steps.adapter_config?.endpoint_id,
      adapterId: currentWorkflow.workflow_steps.adapter_config?.adapter_id,
    });
  }, [currentWorkflow]);

  return (
    <BudForm
      data={{}}
      nextText="View Deployment"
      onNext={() => {
        // getData();
        const payload = {
          endpointId: adapterWorkflow?.endpointId,
          page: 1,
          limit: 20,
        };
        getAdapters(payload, projectId);
        router.push(
          `/projects/${selectedProject?.id}/deployments/${adapterWorkflow?.endpointId}`,
        );
        form.resetFields();
        closeDrawer();
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <BudStepAlert
            type="success"
            title="Adapter deployment successful"
            description={`${adapterWorkflow?.adapterName} has been successfully deployed. You can starting using the deployed adapater for your deployment.`}
          />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};
