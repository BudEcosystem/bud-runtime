import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import ChooseCluster from "@/components/ui/bud/deploymentDrawer/ChooseCluster";
import DeployModelSpecificationInfo from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import QuantizationSpecificationCard from "./QuantizationSpecificationCard";


export default function QuantizationSelectCluster() {
    const { openDrawerWithStep } = useDrawer();
  const { updateQuantizationCluster, quantizationWorkflow, setQuantizationWorkflow } = useDeployModel();

    const handleNext = async () => {
        const result = await updateQuantizationCluster(quantizationWorkflow.clusterId);
        if (result.status === 200) {
            openDrawerWithStep("quantization-deployment-status");
        }
    }

    const handleClusterSelected = (cluster: any) => {
        setQuantizationWorkflow({...quantizationWorkflow, clusterId: cluster.cluster_id})
    }

    return <BudForm
    data={quantizationWorkflow}
    onBack={() => {
        openDrawerWithStep("advanced-settings");
    }}
    disableNext={!quantizationWorkflow?.clusterId}
    onNext={handleNext}
    >
        <BudWraperBox>
            <QuantizationSpecificationCard />
            <BudDrawerLayout>
                <ChooseCluster onClusterSelected={handleClusterSelected} hidePerformance={true} hideRank={true} />
            </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
}